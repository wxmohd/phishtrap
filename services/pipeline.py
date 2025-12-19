"""
ETL pipeline for ingesting emails from MailHog into the database.
Orchestrates: fetch -> parse -> classify -> persist -> [auto-reply].
"""
from datetime import datetime
from typing import Dict, List
from sqlalchemy import select

from database.models import SessionLocal, Email, Link
from services.mailhog_client import fetch_messages
from services.ai_classifier import classify_email
from services.auto_responder import generate_reply, should_auto_reply, create_reply_subject
from services.mailhog_responder import send_reply_to_mailhog


def sync_from_mailhog(limit: int = 50, auto_reply: bool = False) -> Dict[str, any]:
    """
    Run one ETL pass: fetch messages from MailHog, classify, persist to DB, and optionally auto-reply.
    
    Args:
        limit: Maximum number of messages to fetch
        auto_reply: If True, send auto-replies to phishing emails back to MailHog
        
    Returns:
        Dict with summary:
        - imported: number of new emails
        - updated: number of existing emails updated
        - errors: number of errors
        - total_links: total links extracted
        - replies_sent: number of auto-replies sent (if auto_reply=True)
    """
    imported = 0
    updated = 0
    errors = 0
    total_links = 0
    replies_sent = 0
    
    # Fetch messages from MailHog
    try:
        messages = fetch_messages(limit=limit)
    except Exception as e:
        print(f"[PIPELINE] Error fetching messages: {e}")
        return {
            "imported": 0,
            "updated": 0,
            "errors": 1,
            "total_links": 0,
            "error_message": str(e),
        }
    
    if not messages:
        return {
            "imported": 0,
            "updated": 0,
            "errors": 0,
            "total_links": 0,
            "message": "No messages found in MailHog",
        }
    
    # Process each message
    with SessionLocal() as session:
        for msg in messages:
            try:
                # Check if email already exists by ext_id
                existing = session.execute(
                    select(Email).where(Email.ext_id == msg["ext_id"])
                ).scalar_one_or_none()
                
                # Run AI classification
                classification = classify_email(
                    subject=msg.get("subject"),
                    body=msg.get("body_text") or msg.get("body_html"),
                    urls=msg.get("urls", [])
                )
                
                if existing:
                    # Update existing email
                    existing.subject = msg.get("subject")
                    existing.sender = msg.get("sender")
                    existing.recipient = msg.get("recipient")
                    existing.body_text = msg.get("body_text")
                    existing.body_html = msg.get("body_html")
                    existing.received_at = msg.get("received_at")
                    existing.ai_label = classification["label"]
                    existing.ai_score = int(classification["score"] * 100)  # Store as int 0-100
                    existing.ai_explanation = classification["explanation"]
                    
                    email_obj = existing
                    updated += 1
                else:
                    # Create new email
                    email_obj = Email(
                        ext_id=msg["ext_id"],
                        subject=msg.get("subject"),
                        sender=msg.get("sender"),
                        recipient=msg.get("recipient"),
                        body_text=msg.get("body_text"),
                        body_html=msg.get("body_html"),
                        received_at=msg.get("received_at"),
                        replied=False,
                        ai_label=classification["label"],
                        ai_score=int(classification["score"] * 100),
                        ai_explanation=classification["explanation"],
                    )
                    session.add(email_obj)
                    session.flush()  # Get the ID
                    imported += 1
                
                # Process URLs and create/update Link records
                urls = msg.get("urls", [])
                if urls:
                    # Get existing links for this email
                    existing_links = session.execute(
                        select(Link).where(Link.email_id == email_obj.id)
                    ).scalars().all()
                    
                    existing_urls = {link.url for link in existing_links}
                    
                    # Add new links
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
                
                # Auto-reply logic (if enabled and not already replied)
                if auto_reply and not email_obj.replied:
                    ai_label = classification["label"]
                    ai_score = classification["score"]
                    
                    if should_auto_reply(msg, ai_label, ai_score):
                        reply_body = generate_reply(msg, ai_label)
                        if reply_body:
                            reply_subject = create_reply_subject(msg.get("subject", ""))
                            
                            # Send reply back to MailHog
                            success = send_reply_to_mailhog(
                                to=msg.get("sender"),
                                subject=reply_subject,
                                body=reply_body,
                            )
                            
                            if success:
                                email_obj.replied = True
                                replies_sent += 1
                
                session.commit()
                
            except Exception as e:
                print(f"[PIPELINE] Error processing message {msg.get('ext_id')}: {e}")
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


def get_pipeline_stats() -> Dict[str, any]:
    """
    Get statistics about the pipeline and database state.
    
    Returns:
        Dict with counts and metrics
    """
    with SessionLocal() as session:
        from sqlalchemy import func
        
        total_emails = session.execute(
            select(func.count(Email.id))
        ).scalar_one()
        
        total_links = session.execute(
            select(func.count(Link.id))
        ).scalar_one()
        
        phishing_count = session.execute(
            select(func.count(Email.id)).where(Email.ai_label == "phishing")
        ).scalar_one()
        
        suspicious_count = session.execute(
            select(func.count(Email.id)).where(Email.ai_label == "suspicious")
        ).scalar_one()
        
        legit_count = session.execute(
            select(func.count(Email.id)).where(Email.ai_label == "legit")
        ).scalar_one()
        
        return {
            "total_emails": total_emails,
            "total_links": total_links,
            "phishing": phishing_count,
            "suspicious": suspicious_count,
            "legit": legit_count,
        }
