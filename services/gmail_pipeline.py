"""
Gmail-specific pipeline for syncing user emails.
Fetches from Gmail API instead of MailHog.
"""
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy import select, and_
from database.models import SessionLocal, Email, Link, ConnectedUser
from services.gmail_client import fetch_user_emails, send_reply
from services.ai_classifier import classify_email
from services.auto_responder import generate_reply, should_auto_reply, create_reply_subject
from services.blocklist import is_blocked
from services.admin_notifier import send_admin_notification
from services.sender_intel import analyze_sender
from services.domain_whitelist import is_trusted_domain
from services.reply_detector import is_reply_to_bot, should_escalate_reply
from services.websocket_events import emit_new_email


def extract_thread_subject(subject: str) -> Optional[str]:
    """Extract normalized subject for thread matching (removes RE:, FW:, etc.)"""
    if not subject:
        return None
    normalized = re.sub(r'^(re|fw|fwd):\s*', '', subject, flags=re.IGNORECASE)
    return normalized.strip().lower()


def find_original_phishing_email(sender: str, recipient: str, subject: str, session) -> Optional[Email]:
    """Find original phishing email in conversation thread."""
    thread_subject = extract_thread_subject(subject)
    if not thread_subject:
        return None
    
    cutoff_date = datetime.utcnow() - timedelta(days=30)
    
    original = session.execute(
        select(Email).where(
            and_(
                Email.sender == recipient,
                Email.recipient == sender,
                Email.received_at >= cutoff_date,
                Email.ai_label.in_(['phishing', 'suspicious'])
            )
        ).order_by(Email.received_at.desc())
    ).scalars().first()
    
    return original


def sync_user_gmail(user_email: str, auto_reply: bool = False, after_timestamp=None) -> Dict[str, any]:
    """
    Sync emails from a specific user's Gmail account.
    
    Args:
        user_email: Email of the connected user
        auto_reply: Whether to send auto-replies to phishing emails
        after_timestamp: Only fetch emails received after this datetime (UTC)
        
    Returns:
        Dict with summary stats
    """
    imported = 0
    updated = 0
    errors = 0
    total_links = 0
    replies_sent = 0
    
    # Get user's OAuth tokens from database
    with SessionLocal() as session:
        user = session.execute(
            select(ConnectedUser).where(
                ConnectedUser.email == user_email,
                ConnectedUser.revoked_at.is_(None),
            )
        ).scalar_one_or_none()
        
        if not user:
            return {
                "imported": 0,
                "updated": 0,
                "errors": 1,
                "total_links": 0,
                "replies_sent": 0,
                "error_message": f"User {user_email} not found or revoked",
            }
        
        # Parse OAuth tokens
        try:
            token_data = json.loads(user.meta or "{}")
            access_token = token_data.get("access_token")
        except Exception as e:
            return {
                "imported": 0,
                "updated": 0,
                "errors": 1,
                "total_links": 0,
                "replies_sent": 0,
                "error_message": f"Invalid token data: {e}",
            }
    
    if not access_token:
        return {
            "imported": 0,
            "updated": 0,
            "errors": 1,
            "total_links": 0,
            "replies_sent": 0,
            "error_message": "No access token found",
        }
    
    # Fetch emails from Gmail (inbox only, no spam folder)
    try:
        messages = fetch_user_emails(access_token, max_results=50, include_spam=False)
        print(f"[GMAIL_PIPELINE] Fetching from inbox only (excluding spam folder)")
    except Exception as e:
        print(f"[GMAIL_PIPELINE] Error fetching emails: {e}")
        return {
            "imported": 0,
            "updated": 0,
            "errors": 1,
            "total_links": 0,
            "replies_sent": 0,
            "error_message": str(e),
        }
    
    if not messages:
        return {
            "imported": 0,
            "updated": 0,
            "errors": 0,
            "total_links": 0,
            "replies_sent": 0,
            "message": "No messages found in Gmail",
        }
    
    # Process each message
    if after_timestamp:
        print(f"[GMAIL_PIPELINE] ⏰ Filtering: Only emails after {after_timestamp}")
    
    with SessionLocal() as session:
        for msg in messages:
            try:
                # ⚡ FILTER: Skip emails received BEFORE user connected
                if after_timestamp and msg.get("received_at"):
                    msg_time = msg["received_at"]
                    compare_time = after_timestamp
                    
                    # Ensure both are timezone-aware for comparison
                    if msg_time.tzinfo is None:
                        msg_time = msg_time.replace(tzinfo=timezone.utc)
                    if compare_time.tzinfo is None:
                        compare_time = compare_time.replace(tzinfo=timezone.utc)
                    
                    if msg_time < compare_time:
                        print(f"[GMAIL_PIPELINE] ⏭️ Skipping old email from {msg.get('received_at')}")
                        continue
                
                # Check if email already exists (with fresh query)
                session.expire_all()  # Clear cache
                existing = session.execute(
                    select(Email).where(Email.ext_id == msg["ext_id"])
                ).scalar_one_or_none()
                
                # Skip if already processed
                if existing:
                    continue
                
                sender = msg.get("sender", "")
                recipient = msg.get("recipient", "")
                
                # Check blocklist
                if is_blocked(sender, recipient):
                    print(f"[GMAIL_PIPELINE] ✗ Blocked sender: {sender}")
                    # Still store but mark as blocked
                    email_obj = Email(
                        ext_id=msg["ext_id"],
                        subject=msg.get("subject"),
                        sender=sender,
                        recipient=recipient,
                        body_text=msg.get("body_text"),
                        body_html=msg.get("body_html"),
                        received_at=msg.get("received_at"),
                        replied=False,
                        blocked=True,
                        review_status='auto_processed',
                        ai_label='blocked',
                        ai_score=0,
                        ai_explanation='Sender is blocklisted',
                    )
                    session.add(email_obj)
                    session.flush()
                    imported += 1
                    continue
                
                # Check if this is a reply to a phishing conversation thread
                original_phishing = find_original_phishing_email(sender, recipient, msg.get("subject", ""), session)
                
                if original_phishing:
                    # This is a phisher replying to our conversation!
                    ai_label = 'phishing'
                    ai_score_percent = original_phishing.ai_score
                    review_status = 'auto_processed'
                    admin_notified = False
                    classification = {
                        "label": "phishing",
                        "score": original_phishing.ai_score / 100.0,
                        "explanation": f"🔗 Reply in phishing thread (original: {original_phishing.ai_score}%). Auto-replying immediately."
                    }
                    print(f"[GMAIL_PIPELINE] 🔗 Phisher reply detected: {sender} (thread from {original_phishing.received_at})")
                # Check if this is a reply to our AI bot
                elif is_reply_to_bot(msg.get("subject", ""), msg.get("body_text", "")):
                    # Phisher replied to our bot - escalate to admin immediately!
                    ai_label = 'phishing'
                    ai_score_percent = 95
                    review_status = 'pending_review'
                    admin_notified = True
                    classification = {
                        "label": "phishing",
                        "score": 0.95,
                        "explanation": "⚠️ PHISHER REPLIED TO BOT! This requires immediate admin attention."
                    }
                    print(f"[GMAIL_PIPELINE] 🚨 PHISHER REPLIED TO BOT: {sender}")
                # Check if sender is from trusted domain
                elif is_trusted_domain(sender):
                    # Trusted domain - skip AI classification
                    ai_label = 'legit'
                    ai_score_percent = 0
                    review_status = 'auto_processed'
                    admin_notified = False
                    classification = {
                        "label": "legit",
                        "score": 0.0,
                        "explanation": f"Trusted domain: {sender.split('@')[1]}"
                    }
                    print(f"[GMAIL_PIPELINE] ✓ Trusted domain: {sender}")
                else:
                    # Run AI classification
                    classification = classify_email(
                        subject=msg.get("subject"),
                        body=msg.get("body_text") or msg.get("body_html"),
                        urls=msg.get("urls", [])
                    )
                    
                    ai_label = classification["label"]
                    ai_score = classification["score"]
                    ai_score_percent = int(ai_score * 100)
                    
                    # Determine review status based on AI label
                    # legit (0-29%) = Auto-processed (dismiss silently)
                    # suspicious (30-69%) = ALL go to admin review
                    # phishing (70-100%) = High confidence phishing
                    #   - 70-79% = Admin review (uncertain)
                    #   - 80-100% = Auto-reply (high confidence)
                    review_status = 'auto_processed'
                    admin_notified = False
                    
                    # Send ALL suspicious emails to admin for review
                    if ai_label == 'suspicious':
                        review_status = 'pending_review'
                        admin_notified = True
                    # Also send uncertain phishing (70-79%) to admin
                    elif ai_label == 'phishing' and ai_score_percent < 80:
                        review_status = 'pending_review'
                        admin_notified = True
                
                # Create new email
                email_obj = Email(
                    ext_id=msg["ext_id"],
                    subject=msg.get("subject"),
                    sender=sender,
                    recipient=recipient,
                    body_text=msg.get("body_text"),
                    body_html=msg.get("body_html"),
                    received_at=msg.get("received_at"),
                    replied=False,
                    ai_label=ai_label,
                    ai_score=ai_score_percent,
                    ai_explanation=classification["explanation"],
                    review_status=review_status,
                    admin_notified_at=datetime.utcnow() if admin_notified else None,
                    blocked=False,
                )
                session.add(email_obj)
                session.flush()
                imported += 1
                
                # Emit real-time WebSocket event for new email
                try:
                    emit_new_email({
                        'id': email_obj.id,
                        'subject': email_obj.subject,
                        'sender': email_obj.sender,
                        'recipient': email_obj.recipient,
                        'ai_label': email_obj.ai_label,
                        'ai_score': email_obj.ai_score,
                        'received_at': email_obj.received_at.isoformat() if email_obj.received_at else None
                    })
                except Exception as ws_error:
                    print(f"[GMAIL_PIPELINE] ⚠️ WebSocket emit failed: {ws_error}")
                
                # Analyze sender intelligence automatically
                try:
                    analyze_sender(email_obj, session)
                except Exception as e:
                    print(f"[GMAIL_PIPELINE] ⚠️ Sender intel analysis failed: {e}")
                
                # Send admin notification if uncertain
                if admin_notified:
                    print(f"[GMAIL_PIPELINE] ⚠️ Uncertain email - notifying admin: {sender}")
                    send_admin_notification(email_obj)
                    continue  # Don't auto-reply, wait for admin
                
                # Process URLs
                urls = msg.get("urls", [])
                if urls:
                    existing_links = session.execute(
                        select(Link).where(Link.email_id == email_obj.id)
                    ).scalars().all()
                    
                    existing_urls = {link.url for link in existing_links}
                    
                    for url in urls:
                        if url not in existing_urls:
                            link = Link(
                                email_id=email_obj.id,
                                url=url,
                                status="observed",
                                fetched_at=datetime.utcnow(),
                            )
                            session.add(link)
                            total_links += 1
                
                # Auto-reply logic - send immediately for all high-confidence phishing
                if auto_reply and not email_obj.replied and ai_label == 'phishing':
                    # Send immediate reply for all phishing emails ≥80% confidence
                    if ai_score_percent >= 80:
                        reply_body = generate_reply(msg, ai_label)
                        if reply_body:
                            reply_subject = create_reply_subject(msg.get("subject", ""))
                            
                            # Send reply via Gmail API
                            success = send_reply(
                                access_token=access_token,
                                to=msg.get("sender"),
                                subject=reply_subject,
                                body=reply_body,
                            )
                            
                            if success:
                                email_obj.replied = True
                                replies_sent += 1
                                print(f"[GMAIL_PIPELINE] ✓ Auto-replied to {sender} (confidence: {ai_score_percent}%)")
                
                session.commit()
                
                # Emit WebSocket event immediately after each new email
                if imported > 0:
                    try:
                        from services.websocket_events import emit_sync_complete
                        emit_sync_complete({
                            'imported': 1,
                            'timestamp': datetime.utcnow().isoformat(),
                            'user': user_email
                        })
                        print(f"[GMAIL_PIPELINE] 📡 Emitted WebSocket event for new email")
                    except Exception as ws_error:
                        print(f"[GMAIL_PIPELINE] ⚠️ WebSocket emit failed: {ws_error}")
                
            except Exception as e:
                print(f"[GMAIL_PIPELINE] Error processing message {msg.get('ext_id')}: {e}")
                session.rollback()
                errors += 1
                continue
    
    return {
        "imported": imported,
        "updated": updated,
        "errors": errors,
        "total_links": total_links,
        "replies_sent": replies_sent,
    }


def sync_all_connected_users(auto_reply: bool = False) -> Dict[str, any]:
    """
    Sync emails for all connected (non-revoked) users.
    
    Args:
        auto_reply: Whether to send auto-replies
        
    Returns:
        Aggregated stats for all users
    """
    total_imported = 0
    total_updated = 0
    total_errors = 0
    total_links = 0
    total_replies = 0
    users_synced = 0
    
    # Get all active users
    with SessionLocal() as session:
        users = session.execute(
            select(ConnectedUser).where(
                ConnectedUser.revoked_at.is_(None),
            )
        ).scalars().all()
    
    for user in users:
        result = sync_user_gmail(user.email, auto_reply=auto_reply)
        
        total_imported += result.get("imported", 0)
        total_updated += result.get("updated", 0)
        total_errors += result.get("errors", 0)
        total_links += result.get("total_links", 0)
        total_replies += result.get("replies_sent", 0)
        users_synced += 1
    
    return {
        "users_synced": users_synced,
        "imported": total_imported,
        "updated": total_updated,
        "errors": total_errors,
        "total_links": total_links,
        "replies_sent": total_replies,
    }
