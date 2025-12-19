#!/usr/bin/env python3
"""
Send fake phishing emails using already-connected OAuth accounts
No password needed - uses tokens from database!
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from database.models import SessionLocal, ConnectedUser
from services.gmail_client import send_reply as gmail_send
from services.microsoft_client import send_email as outlook_send
from sqlalchemy import select
import json
import random
from datetime import datetime

# Phishing email templates
TEMPLATES = [
    {
        "subject": "URGENT: Your PayPal Account Has Been Limited",
        "sender": "security@paypa1-secure.com",
        "body": """Dear Valued Customer,

We have detected unusual activity on your PayPal account. For your security, we have temporarily limited your account access.

To restore full access, please verify your identity immediately:
http://bit.ly/paypal-verify-2024

This link will expire in 24 hours. Failure to verify will result in permanent account suspension.

Thank you for your prompt attention.
PayPal Security Team"""
    },
    {
        "subject": "Your Amazon Order #4829-3847 Has Been Shipped",
        "sender": "orders@amazon-delivery.net",
        "body": """Hello,

Your recent order has been shipped and is on its way!

Order Number: #4829-3847
Total: $1,247.99
Delivery: 2-3 business days

Track your package: http://amzn.to/track-order-48293847

If you did not place this order, please contact us immediately to cancel:
http://amazon-support.net/cancel-order

Amazon Delivery Team"""
    },
    {
        "subject": "Apple ID: Your account has been locked",
        "sender": "support@apple-id-security.com",
        "body": """Dear Apple Customer,

Your Apple ID has been locked due to suspicious activity detected from an unknown device.

To unlock your account, please verify your identity:
https://appleid-verify.com/unlock

Device Details:
- Location: Unknown
- IP Address: 192.168.1.1
- Time: Today at 3:42 AM

If this wasn't you, secure your account immediately by clicking the link above.

Apple Security Team"""
    },
    {
        "subject": "Your Netflix Subscription Payment Failed",
        "sender": "billing@netflix-payments.com",
        "body": """Netflix Payment Update Required

We were unable to process your monthly subscription payment.

Account: user@example.com
Plan: Premium (4 screens)
Amount Due: $19.99

Your account will be suspended in 24 hours unless you update your payment method:
https://netflix-billing.net/update-payment

Update Payment Method: https://netflix-billing.net/update-payment

Netflix Billing Team"""
    },
    {
        "subject": "IRS Tax Refund Notification - Action Required",
        "sender": "refunds@irs-treasury.gov",
        "body": """Internal Revenue Service
Tax Refund Notification

Dear Taxpayer,

You are eligible for a tax refund of $1,847.00 for the 2024 tax year.

To claim your refund, please verify your information:
https://irs-refund-portal.gov/claim

Refund Details:
- Amount: $1,847.00
- Tax Year: 2024
- Processing Time: 3-5 business days

This notification expires in 72 hours. Unclaimed refunds will be forfeited.

Internal Revenue Service
Department of the Treasury"""
    },
    {
        "subject": "Your Package Delivery Failed - Rescheduling Required",
        "sender": "delivery@dhl-express.net",
        "body": """DHL Express Delivery Notice

We attempted to deliver your package but no one was available to receive it.

Tracking Number: DHL-8472-9384-2847
Delivery Attempts: 2
Next Attempt: Pending your confirmation

To reschedule delivery, please confirm your address:
https://dhl-tracking.net/reschedule/8472-9384-2847

If not rescheduled within 48 hours, your package will be returned to sender.

DHL Express Delivery Services"""
    },
    {
        "subject": "Microsoft Account Security Alert",
        "sender": "security@microsoft-account.com",
        "body": """Microsoft Account Team

We detected an unusual sign-in attempt to your Microsoft account.

Location: Russia
Device: Unknown Windows PC
Time: Today at 2:15 AM

If this was you, you can ignore this email.

If this wasn't you, please secure your account immediately:
https://account-microsoft.net/secure

Your account will be temporarily locked for your protection.

Microsoft Account Security"""
    },
    {
        "subject": "Bank of America: Suspicious Activity Detected",
        "sender": "alerts@bankofamerica-secure.com",
        "body": """Bank of America Security Alert

We have detected suspicious activity on your account ending in 4829.

Transaction Details:
- Amount: $2,847.99
- Merchant: Unknown
- Location: International
- Date: Today

If you did not authorize this transaction, please verify your account immediately:
https://bankofamerica-verify.net/secure

Your card has been temporarily suspended for your protection.

Bank of America Security Team"""
    }
]

def get_connected_users():
    """Get all connected users from database"""
    with SessionLocal() as session:
        users = session.query(ConnectedUser).filter(
            ConnectedUser.revoked_at.is_(None)
        ).all()
        return [(u.email, u.provider, u.meta) for u in users]

def send_via_gmail(to_email, subject, body, token_data, from_email="noreply@phishing-demo.local"):
    """Send email using Gmail API"""
    try:
        tokens = json.loads(token_data)
        # Use Gmail API to send with custom from address
        gmail_send(tokens['access_token'], to_email, subject, body, from_email=from_email)
        return True
    except Exception as e:
        print(f"  ❌ Gmail send error: {e}")
        return False

def send_via_outlook(to_email, subject, body, token_data):
    """Send email using Microsoft Graph API"""
    try:
        # Handle both string and dict token_data
        if isinstance(token_data, str):
            tokens = json.loads(token_data)
        else:
            tokens = token_data
        # Use Microsoft Graph to send (access_token, to_email, subject, body)
        return outlook_send(tokens['access_token'], to_email, subject, body)
    except Exception as e:
        print(f"  ❌ Outlook send error: {e}")
        return False

def main():
    print("🎬 PhishTrap Demo - Fake Email Sender")
    print("=" * 60)
    print()
    
    # Get connected users
    users = get_connected_users()
    
    if not users:
        print("❌ No connected accounts found!")
        print()
        print("Please connect an account first:")
        print("1. Start PhishTrap: python3 main.py")
        print("2. Go to: http://127.0.0.1:5000/login")
        print("3. Login with Google or Microsoft")
        print("4. Run this script again")
        return
    
    print("📧 Connected accounts:")
    for i, (email, provider, _) in enumerate(users, 1):
        print(f"{i}. {email} ({provider})")
    print()
    
    # Select account
    if len(users) == 1:
        choice = 1
        print(f"✓ Using: {users[0][0]}")
    else:
        try:
            choice = int(input(f"Choose account [1-{len(users)}]: "))
            if choice < 1 or choice > len(users):
                print("❌ Invalid choice")
                return
        except ValueError:
            print("❌ Invalid input")
            return
    
    target_email, provider, token_data = users[choice - 1]
    print()
    
    # Refresh Microsoft token if needed
    if provider == "microsoft":
        from services.microsoft_client import refresh_access_token
        print("🔄 Refreshing Microsoft token...")
        
        try:
            token_dict = json.loads(token_data) if isinstance(token_data, str) else token_data
            refresh_token = token_dict.get('refresh_token')
            
            if refresh_token:
                new_token_data = refresh_access_token(refresh_token)
                if new_token_data:
                    # Update token in database
                    with SessionLocal() as session:
                        user = session.execute(
                            select(ConnectedUser).where(ConnectedUser.email == target_email)
                        ).scalar_one_or_none()
                        
                        if user:
                            user.meta = json.dumps(new_token_data)
                            session.commit()
                            token_data = new_token_data
                            print("✓ Token refreshed successfully!")
                        else:
                            print("⚠️ Could not update token in database")
                else:
                    print("⚠️ Token refresh failed - you may need to reconnect")
            else:
                print("⚠️ No refresh token found - you may need to reconnect")
        except Exception as e:
            print(f"⚠️ Token refresh error: {e}")
        
        print()
    
    # Get count
    try:
        count = int(input("📊 How many fake emails to send? [10]: ") or "10")
    except ValueError:
        count = 10
    
    print()
    print(f"🚀 Sending {count} fake phishing emails to {target_email}...")
    print()
    
    # Send emails
    sent = 0
    failed = 0
    
    for i in range(count):
        template = random.choice(TEMPLATES)
        
        print(f"[{i+1}/{count}] Sending: {template['subject'][:50]}...")
        
        # Send based on provider
        if provider == "google":
            success = send_via_gmail(target_email, template['subject'], template['body'], token_data, from_email=template['sender'])
        elif provider == "microsoft":
            success = send_via_outlook(target_email, template['subject'], template['body'], token_data)
        else:
            print(f"  ❌ Unknown provider: {provider}")
            failed += 1
            continue
        
        if success:
            print(f"  ✓ Sent from {template['sender']}")
            sent += 1
        else:
            failed += 1
    
    print()
    print("=" * 60)
    print("📊 Summary:")
    print(f"  ✓ Sent: {sent}")
    print(f"  ✗ Failed: {failed}")
    print()
    print("📝 Next steps:")
    print("1. Wait 10-30 seconds for emails to arrive")
    print("2. Open dashboard: http://127.0.0.1:5000")
    print("3. Check 'Auto-reply' and click 'Sync Emails'")
    print()

if __name__ == "__main__":
    main()
