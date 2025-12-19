#!/usr/bin/env python3
"""
Trigger auto-replies for existing high-confidence phishing emails.
This script finds phishing emails that haven't been replied to yet and sends auto-replies.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.models import SessionLocal, Email, ConnectedUser
from services.auto_responder import generate_reply, create_reply_subject
from services.gmail_client import send_reply as send_gmail_reply
from services.outlook_pipeline import send_reply as send_outlook_reply
from services.microsoft_client import refresh_access_token
import time
import random

def trigger_auto_replies():
    """
    Find high-confidence phishing emails (≥80%) that haven't been replied to
    and send auto-replies.
    """
    with SessionLocal() as session:
        # Find phishing emails that need replies
        phishing_emails = session.query(Email).filter(
            Email.ai_label == 'phishing',
            Email.ai_score >= 80.0,
            Email.replied == False
        ).order_by(Email.received_at.desc()).all()
        
        if not phishing_emails:
            print("✅ No phishing emails need auto-replies")
            return
        
        print(f"\n🎯 Found {len(phishing_emails)} phishing email(s) that need auto-replies\n")
        
        for email in phishing_emails:
            print(f"📧 Email ID {email.id}: {email.subject}")
            print(f"   From: {email.sender}")
            print(f"   Score: {email.ai_score}% phishing")
            print(f"   Received: {email.received_at}")
            
            # Find the connected user for this email
            user = session.query(ConnectedUser).filter(
                ConnectedUser.email == email.recipient,
                ConnectedUser.revoked_at.is_(None)
            ).first()
            
            if not user:
                print(f"   ⚠️  No active user found for {email.recipient}")
                print()
                continue
            
            # Generate reply
            msg_dict = {
                'subject': email.subject,
                'body': email.body_text or email.body_html or '',
                'sender': email.sender
            }
            
            reply_body = generate_reply(msg_dict, 'phishing')
            reply_subject = create_reply_subject(email.subject)
            
            if not reply_body:
                print(f"   ⚠️  Could not generate reply")
                print()
                continue
            
            print(f"   🤖 Generated reply: {reply_body[:100]}...")
            
            # Add humanized delay (5-10 minutes)
            delay_seconds = random.randint(5, 10) * 60
            delay_minutes = delay_seconds // 60
            
            print(f"   ⏰ Waiting {delay_minutes} minutes for humanized delay...")
            time.sleep(delay_seconds)
            
            # Send reply based on provider
            success = False
            if user.provider == 'google':
                print(f"   📧 Sending via Gmail...")
                # Gmail reply logic
                # Note: This requires the message_id from Gmail API
                print(f"   ⚠️  Gmail auto-reply not fully implemented yet")
                
            elif user.provider == 'microsoft':
                print(f"   📨 Sending via Outlook...")
                # Refresh token if needed
                access_token = user.access_token
                if user.token_expires_at:
                    from datetime import datetime, timezone
                    if datetime.now(timezone.utc) >= user.token_expires_at:
                        print(f"   🔄 Refreshing access token...")
                        new_token, new_refresh, new_expires = refresh_access_token(user.refresh_token)
                        if new_token:
                            access_token = new_token
                            user.access_token = new_token
                            user.refresh_token = new_refresh
                            user.token_expires_at = new_expires
                            session.commit()
                
                # Send reply
                success = send_outlook_reply(
                    access_token=access_token,
                    message_id=email.external_id,
                    reply_body=reply_body,
                    reply_subject=reply_subject
                )
            
            if success:
                email.replied = True
                session.commit()
                print(f"   ✅ Auto-reply sent successfully!")
            else:
                print(f"   ❌ Failed to send auto-reply")
            
            print()

if __name__ == '__main__':
    print("=" * 70)
    print("🤖 PhishTrap Auto-Reply Trigger")
    print("=" * 70)
    print()
    print("This script will:")
    print("  1. Find phishing emails (≥80% confidence) that haven't been replied to")
    print("  2. Generate humanized auto-replies")
    print("  3. Wait 5-10 minutes per email (realistic delay)")
    print("  4. Send the replies")
    print()
    
    try:
        trigger_auto_replies()
        print("=" * 70)
        print("✅ Auto-reply trigger complete!")
        print("=" * 70)
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
