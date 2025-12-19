"""
PhishTrap - Outlook Graph API Email Sender
Uses existing Microsoft OAuth credentials to send emails via Graph API.
"""
import os
import sys
import requests
from datetime import datetime

# Add parent directory to path to import from services
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.models import SessionLocal, ConnectedUser
from services.microsoft_client import refresh_access_token

# Configuration
SENDER_EMAIL = "phishing_testt1@outlook.com"
TARGET_EMAIL = "d3m01231@outlook.com"
ATTACKER_IP = "109.161.188.136"  # Your public IP

# Phishing email templates
PHISHING_TEMPLATES = [
    {
        "subject": "Urgent: Your Account Will Be Suspended in 24 Hours",
        "body": """Dear User,

We detected unusual activity on your account and your access will be temporarily suspended 
if you do not verify your identity within the next 24 hours.

To continue using your services, please complete the security verification form:
👉 Verify your account here: https://secure-verify-support.com/update-info

Failure to complete this verification may lead to:
- Permanent account suspension
- Loss of stored data
- Restricted access to certain services

If you believe this was sent by mistake, please contact our support team immediately.

Thank you for your cooperation,
Account Security Department
secure-verify-support.com""",
    },
    {
        "subject": "Final Notice: Outstanding Invoice #84719",
        "body": """Dear Customer,

This is a final reminder that invoice #84719 remains unpaid. Your account will be 
suspended and sent to collections if payment is not received within 48 hours.

Amount Due: $1,247.99
Due Date: OVERDUE

Pay now to avoid additional fees:
👉 https://payment-portal-secure.com/invoice/84719

If you have already paid, please disregard this notice.

Billing Department
billing@payment-portal-secure.com""",
    },
    {
        "subject": "Action Required: Your Mailbox Is Almost Full",
        "body": """Dear User,

Your mailbox has reached 98% capacity (4.9GB of 5GB). To continue receiving emails, 
you must upgrade your storage immediately.

Click here to upgrade your storage:
👉 https://mail-storage-upgrade.com/expand

Failure to upgrade may result in:
- Inability to receive new emails
- Automatic deletion of old messages
- Service interruption

IT Support Team
support@mail-storage-upgrade.com""",
    },
]


def get_access_token_from_db(email):
    """Get access token for connected user from database."""
    session = SessionLocal()
    try:
        user = session.query(ConnectedUser).filter_by(
            email=email,
            provider='microsoft',
            revoked_at=None
        ).first()
        
        if not user:
            print(f"❌ User {email} not connected. Please connect via dashboard first.")
            return None
        
        # Check if token needs refresh
        from datetime import datetime, timezone
        if user.token_expires_at and user.token_expires_at <= datetime.now(timezone.utc):
            print("🔄 Token expired, refreshing...")
            new_token = refresh_access_token(user.refresh_token)
            if new_token:
                return new_token
            else:
                print("❌ Failed to refresh token")
                return None
        
        return user.access_token
        
    finally:
        session.close()


def send_email_via_graph(access_token, template_index=0):
    """Send email using Microsoft Graph API."""
    
    template = PHISHING_TEMPLATES[template_index]
    
    # Create email message
    message = {
        "message": {
            "subject": template["subject"],
            "body": {
                "contentType": "Text",
                "content": template["body"]
            },
            "toRecipients": [
                {
                    "emailAddress": {
                        "address": TARGET_EMAIL
                    }
                }
            ],
            "internetMessageHeaders": [
                {
                    "name": "X-Originating-IP",
                    "value": f"[{ATTACKER_IP}]"
                }
            ]
        },
        "saveToSentItems": "true"
    }
    
    # Send via Graph API
    url = "https://graph.microsoft.com/v1.0/me/sendMail"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    print(f"\n🚀 Sending phishing test email via Microsoft Graph API...")
    print(f"   📧 Subject: {template['subject']}")
    print(f"   📤 From: {SENDER_EMAIL}")
    print(f"   📥 To: {TARGET_EMAIL}")
    print(f"   📍 Injected IP: {ATTACKER_IP}")
    
    response = requests.post(url, headers=headers, json=message)
    
    if response.status_code == 202:
        print(f"\n   ✅ Email sent successfully!")
        print(f"\n   📍 Expected Result:")
        print(f"      - Email headers will contain: {ATTACKER_IP}")
        print(f"      - PhishTrap will geolocate this IP")
        print(f"      - Dashboard will show: Jordan 🇯🇴")
        print(f"\n   ⏳ Check your PhishTrap dashboard in ~60 seconds")
        return True
    else:
        print(f"\n   ❌ Error sending email:")
        print(f"      Status: {response.status_code}")
        print(f"      Response: {response.text}")
        return False


def interactive_mode():
    """Interactive CLI for sending test emails."""
    print("\n" + "="*70)
    print("🎣 PhishTrap - Outlook Graph API Email Sender")
    print("="*70)
    print(f"\n📧 Sender: {SENDER_EMAIL}")
    print(f"📍 Your Public IP: {ATTACKER_IP}")
    
    # Get access token
    print(f"\n🔐 Getting access token from database...")
    access_token = get_access_token_from_db(SENDER_EMAIL)
    
    if not access_token:
        print(f"\n❌ Could not get access token.")
        print(f"\n💡 Solution:")
        print(f"   1. Make sure PhishTrap dashboard is running")
        print(f"   2. Go to: http://localhost:5000")
        print(f"   3. Connect {SENDER_EMAIL} via OAuth")
        print(f"   4. Run this script again")
        return
    
    print(f"   ✅ Access token retrieved")
    
    # Select template
    print("\n📧 Select phishing template:")
    for i, template in enumerate(PHISHING_TEMPLATES, 1):
        print(f"   {i}. {template['subject']}")
    
    template_choice = input(f"\nEnter number (1-{len(PHISHING_TEMPLATES)}): ")
    try:
        template_idx = int(template_choice) - 1
        if template_idx < 0 or template_idx >= len(PHISHING_TEMPLATES):
            raise ValueError
    except:
        print("Invalid choice, using first template")
        template_idx = 0
    
    # Send email
    send_email_via_graph(access_token, template_idx)


if __name__ == "__main__":
    interactive_mode()
