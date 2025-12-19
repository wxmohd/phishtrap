"""
Outlook-specific pipeline for syncing user emails.
Fetches from Microsoft Graph API instead of MailHog or Gmail.
"""
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy import select, and_
from database.models import SessionLocal, Email, Link, ConnectedUser
from services.microsoft_client import fetch_user_emails, send_reply, refresh_access_token
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
    """
    Find original phishing email in conversation thread.
    Returns the original email if it was classified as phishing/suspicious.
    """
    thread_subject = extract_thread_subject(subject)
    if not thread_subject:
        return None
    
    # Look for emails sent TO this sender (they're replying to us)
    cutoff_date = datetime.utcnow() - timedelta(days=30)
    
    original = session.execute(
        select(Email).where(
            and_(
                Email.sender == recipient,  # We sent it
                Email.recipient == sender,  # To them
                Email.received_at >= cutoff_date,
                Email.ai_label.in_(['phishing', 'suspicious'])  # Was phishing
            )
        ).order_by(Email.received_at.desc())
    ).scalars().first()
    
    return original


def sync_user_outlook(user_email: str, auto_reply: bool = False, after_timestamp=None) -> Dict[str, any]:
    """
    Sync emails from a specific user's Outlook account.
    
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
                ConnectedUser.provider == "microsoft",
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
                "error_message": f"User {user_email} not found or revoked (Microsoft)",
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
    
    # Fetch emails from Outlook (inbox only, no junk folder)
    try:
        messages = fetch_user_emails(access_token, max_results=100, include_spam=False)
        print(f"[OUTLOOK_PIPELINE] Fetching from inbox only (excluding junk folder)")
    except Exception as e:
        # Check if it's a 401 Unauthorized error (expired token)
        if "401" in str(e) or "Unauthorized" in str(e):
            print(f"[OUTLOOK_PIPELINE] Token expired, attempting refresh...")
            
            # Try to refresh the token
            refresh_token = token_data.get("refresh_token")
            if refresh_token:
                new_token_data = refresh_access_token(refresh_token)
                if new_token_data:
                    # Update database with new tokens
                    with SessionLocal() as session:
                        user = session.execute(
                            select(ConnectedUser).where(ConnectedUser.email == user_email)
                        ).scalar_one_or_none()
                        
                        if user:
                            user.meta = json.dumps(new_token_data)
                            session.commit()
                            print(f"[OUTLOOK_PIPELINE] ✓ Token refreshed and saved to database")
                            
                            # Retry fetching emails with new token
                            access_token = new_token_data.get("access_token")
                            try:
                                messages = fetch_user_emails(access_token, max_results=50, include_spam=False)
                                print(f"[OUTLOOK_PIPELINE] ✓ Successfully fetched emails after token refresh")
                            except Exception as retry_error:
                                print(f"[OUTLOOK_PIPELINE] ✗ Still failed after token refresh: {retry_error}")
                                return {
                                    "imported": 0,
                                    "updated": 0,
                                    "errors": 1,
                                    "total_links": 0,
                                    "replies_sent": 0,
                                    "error_message": f"Failed after token refresh: {retry_error}",
                                }
                        else:
                            print(f"[OUTLOOK_PIPELINE] ✗ User not found for token update")
                            return {
                                "imported": 0,
                                "updated": 0,
                                "errors": 1,
                                "total_links": 0,
                                "replies_sent": 0,
                                "error_message": "User not found for token update",
                            }
                else:
                    print(f"[OUTLOOK_PIPELINE] ✗ Token refresh failed")
                    return {
                        "imported": 0,
                        "updated": 0,
                        "errors": 1,
                        "total_links": 0,
                        "replies_sent": 0,
                        "error_message": "Token refresh failed - please reconnect account",
                    }
            else:
                print(f"[OUTLOOK_PIPELINE] ✗ No refresh token available")
                return {
                    "imported": 0,
                    "updated": 0,
                    "errors": 1,
                    "total_links": 0,
                    "replies_sent": 0,
                    "error_message": "No refresh token - please reconnect account",
                }
        else:
            print(f"[OUTLOOK_PIPELINE] Error fetching emails: {e}")
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
            "message": "No messages found in Outlook",
        }
    
    # Process each message
    if after_timestamp:
        print(f"[OUTLOOK_PIPELINE] ⏰ Filtering: Only emails after {after_timestamp}")
    
    with SessionLocal() as session:
        for msg in messages:
            ext_id = msg.get("ext_id")
            sender = msg.get("sender", "")
            recipient = msg.get("recipient", "")
            
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
                    print(f"[OUTLOOK_PIPELINE] ⏭️ Skipping old email from {msg.get('received_at')}")
                    continue
            
            # Check if email already exists (with fresh query)
            session.expire_all()  # Clear cache
            existing = session.execute(
                select(Email).where(Email.ext_id == ext_id)
            ).scalar_one_or_none()
            
            if existing:
                # Email already imported, skip completely
                if existing.replied:
                    print(f"[OUTLOOK_PIPELINE] ⏭️  Skipping duplicate (already replied): {ext_id[:30]}...")
                else:
                    print(f"[OUTLOOK_PIPELINE] ⏭️  Skipping duplicate: {ext_id[:30]}...")
                continue
            
            # Skip emails from self (user's own account)
            print(f"[OUTLOOK_PIPELINE] 📋 Checking: sender='{sender}' | recipient='{recipient}'")
            if sender.lower() == recipient.lower():
                print(f"[OUTLOOK_PIPELINE] ⏭️  Skipping email from self: {sender}")
                continue
            
            # Additional check: Skip if sender is the connected user
            if sender.lower() == user_email.lower():
                print(f"[OUTLOOK_PIPELINE] ⏭️  Skipping email from connected user: {sender}")
                continue
            
            # Check blocklist
            if is_blocked(sender, recipient):
                print(f"[OUTLOOK_PIPELINE] ✗ Blocked sender: {sender}")
                # Still store but mark as blocked
                email_record = Email(
                    ext_id=ext_id,
                    subject=msg.get("subject", ""),
                    sender=sender,
                    recipient=recipient,
                    body_text=msg.get("body_text", ""),
                    body_html=msg.get("body_html", ""),
                    received_at=msg.get("received_at", datetime.utcnow()),
                    replied=False,
                    blocked=True,
                    review_status='auto_processed',
                    ai_label='blocked',
                    ai_score=0,
                    ai_explanation='Sender is blocklisted',
                )
                session.add(email_record)
                session.flush()
                imported += 1
                continue
            
            # Initialize parent_email_id (for threading)
            parent_email_id = None
            
            # Check if sender is from trusted domain FIRST (before thread detection)
            if is_trusted_domain(sender):
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
                print(f"[OUTLOOK_PIPELINE] ✓ Trusted domain: {sender}")
            # Check if this is a reply to an existing email thread
            elif msg.get("subject", "").lower().startswith("re:"):
                # This is a reply - try to find the original email
                original_email = find_original_phishing_email(sender, recipient, msg.get("subject", ""), session)
                
                if original_email:
                    # Found original email - this is a reply to our conversation
                    # Store as a reply linked to the original, don't send to pending review
                    ai_label = 'phishing'  # Keep original classification
                    ai_score_percent = original_email.ai_score
                    review_status = 'auto_processed'  # Don't send to pending review
                    admin_notified = False
                    parent_email_id = original_email.id  # Link to original thread
                    classification = {
                        "label": "phishing",
                        "score": original_email.ai_score / 100.0,
                        "explanation": f"Reply to conversation thread (original: {original_email.subject})"
                    }
                    print(f"[OUTLOOK_PIPELINE] 💬 Reply to thread: {sender} → {original_email.subject}")
                else:
                    # Reply but can't find original - classify normally
                    classification = classify_email(
                        subject=msg.get("subject"),
                        body=msg.get("body_text") or msg.get("body_html"),
                        urls=msg.get("urls", []),
                        sender=sender
                    )
                    ai_label = classification.get("label")
                    ai_score = classification.get("score", 0)
                    ai_score_percent = int(ai_score * 100) if isinstance(ai_score, float) else ai_score
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
            else:
                # Classify email with AI
                classification = classify_email(
                    subject=msg.get("subject"),
                    body=msg.get("body_text") or msg.get("body_html"),
                    urls=msg.get("urls", []),
                    sender=sender
                )
                ai_label = classification.get("label")
                ai_score = classification.get("score", 0)
                ai_score_percent = int(ai_score * 100) if isinstance(ai_score, float) else ai_score
                
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
            
            # Create Email record
            email_record = Email(
                ext_id=ext_id,
                subject=msg.get("subject", ""),
                sender=sender,
                recipient=recipient,
                body_text=msg.get("body_text", ""),
                body_html=msg.get("body_html", ""),
                received_at=msg.get("received_at", datetime.utcnow()),
                replied=False,
                ai_label=ai_label,
                ai_score=ai_score_percent,
                ai_explanation=classification.get("explanation"),
                review_status=review_status,
                admin_notified_at=datetime.utcnow() if admin_notified else None,
                blocked=False,
                parent_email_id=parent_email_id,  # Link to original thread if this is a reply
            )
            session.add(email_record)
            session.flush()  # Get email_record.id
            
            imported += 1
            
            # Emit real-time WebSocket event for new email
            try:
                emit_new_email({
                    'id': email_record.id,
                    'subject': email_record.subject,
                    'sender': email_record.sender,
                    'recipient': email_record.recipient,
                    'ai_label': email_record.ai_label,
                    'ai_score': email_record.ai_score,
                    'received_at': email_record.received_at.isoformat() if email_record.received_at else None
                })
            except Exception as ws_error:
                print(f"[OUTLOOK_PIPELINE] ⚠️ WebSocket emit failed: {ws_error}")
            
            # Analyze sender intelligence automatically
            try:
                sender_ip = msg.get("sender_ip")
                analyze_sender(email_record, session, sender_ip_from_headers=sender_ip)
                if sender_ip:
                    print(f"[OUTLOOK_PIPELINE] 📍 Extracted sender IP: {sender_ip}")
            except Exception as e:
                print(f"[OUTLOOK_PIPELINE] ⚠️ Sender intel analysis failed: {e}")
            
            # Send admin notification if uncertain
            if admin_notified:
                print(f"[OUTLOOK_PIPELINE] ⚠️ Uncertain email - notifying admin: {sender}")
                send_admin_notification(email_record)
                continue  # Don't auto-reply, wait for admin
            
            # Extract and store URLs (check for duplicates first)
            urls = msg.get("urls", [])
            stored_links = []
            
            # Get existing URLs for this email to avoid duplicates
            existing_links = session.execute(
                select(Link).where(Link.email_id == email_record.id)
            ).scalars().all()
            existing_urls = {link.url for link in existing_links}
            
            for url in urls:
                if url not in existing_urls:
                    link = Link(
                        email_id=email_record.id,
                        url=url,
                        status="pending",
                        fetched_at=None,
                        analysis_complete=False,
                    )
                    session.add(link)
                    session.flush()  # Get link ID
                    stored_links.append(link)
                    total_links += 1
                else:
                    print(f"[OUTLOOK_PIPELINE] ⏭️ Skipping duplicate link: {url[:50]}")
            
            # Analyze links automatically in background
            if stored_links:
                try:
                    from services.link_analyzer import analyze_link
                    print(f"[OUTLOOK_PIPELINE] 🔗 Analyzing {len(stored_links)} link(s)...")
                    for link in stored_links:
                        try:
                            analyze_link(link, session)
                            print(f"[OUTLOOK_PIPELINE]   ✓ Link #{link.id} analyzed")
                        except Exception as link_error:
                            print(f"[OUTLOOK_PIPELINE]   ✗ Link #{link.id} failed: {link_error}")
                            import traceback
                            traceback.print_exc()
                except Exception as e:
                    print(f"[OUTLOOK_PIPELINE] ⚠️ Link analysis import failed: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Auto-reply logic
            if auto_reply and ai_label == 'phishing':
                # STRICT CHECK: Never reply to self
                if sender.lower() == recipient.lower():
                    print(f"[OUTLOOK_PIPELINE] ⚠️ BLOCKED: Cannot reply to self ({sender})")
                    continue
                
                # Auto-reply for all phishing emails (≥80% confidence)
                if ai_score_percent >= 80:
                    print(f"[OUTLOOK_PIPELINE] 🤖 Preparing auto-reply to: {sender}")
                    print(f"[OUTLOOK_PIPELINE]    Subject: {msg.get('subject', '')[:50]}")
                    print(f"[OUTLOOK_PIPELINE]    Confidence: {ai_score_percent}%")
                    
                    # Generate reply
                    reply_body = generate_reply(msg, ai_label)
                    reply_subject = create_reply_subject(msg.get("subject", ""))
                    
                    if reply_body:
                        # Send reply via Microsoft Graph API
                        success = send_reply(
                            access_token=access_token,
                            message_id=ext_id,
                            reply_body=reply_body,
                            reply_subject=reply_subject
                        )
                        
                        if success:
                            email_record.replied = True
                            email_record.ai_reply_text = reply_body
                            email_record.replied_at = datetime.now()
                            session.flush()  # Ensure reply data is saved
                            replies_sent += 1
                            print(f"[OUTLOOK_PIPELINE] ✓ Auto-replied to {sender} (confidence: {ai_score_percent}%)")
                            print(f"[OUTLOOK_PIPELINE] ✓ Reply stored in database (ID: {email_record.id})")
                        else:
                            print(f"[OUTLOOK_PIPELINE] ✗ Failed to send reply to {sender}")
        
        session.commit()
        
        # Emit WebSocket event AFTER commit to ensure data is available
        if imported > 0:
            try:
                from services.websocket_events import emit_sync_complete
                emit_sync_complete({
                    'imported': imported,
                    'timestamp': datetime.utcnow().isoformat()
                })
            except Exception as e:
                print(f"[OUTLOOK_PIPELINE] ⚠️ WebSocket emit failed: {e}")
    
    return {
        "imported": imported,
        "updated": updated,
        "errors": errors,
        "total_links": total_links,
        "replies_sent": replies_sent,
    }
