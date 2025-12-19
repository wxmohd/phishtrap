"""
PhishTrap Testing Tool - Phishing Email Simulator
Sends realistic phishing emails with controlled sender IPs for testing.
"""
import smtplib
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# Configuration
SMTP_SERVER = "smtp.office365.com"
SMTP_PORT = 587
SENDER_EMAIL = "phishing_testt1@outlook.com"  # Your test account
SENDER_PASSWORD = "asicsacsiqbyxwab"  # Use APP PASSWORD from Microsoft (not regular password)
TARGET_EMAIL = "d3m01231@outlook.com"  # Your honeypot account

# Simulated attacker IPs (for testing different geolocations)
ATTACKER_IPS = {
    "local": "109.161.188.136"      # Your actual IP (get from ipconfig/ifconfig)
}

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
    {
        "subject": "Congratulations! You've Won $50,000",
        "body": """Dear Lucky Winner,

Congratulations! Your email address has been randomly selected in our international 
lottery draw. You have won $50,000 USD!

To claim your prize, please verify your identity:
👉 https://lottery-claim-center.com/verify

You must claim within 7 days or the prize will be forfeited.

Prize Claim Reference: LC-2024-8471923

International Lottery Commission
claims@lottery-claim-center.com""",
    },
]


def send_phishing_test(attacker_location="local", template_index=0):
    """
    Send a test phishing email with simulated attacker IP.
    
    Args:
        attacker_location: Key from ATTACKER_IPS dict
        template_index: Index of template to use (0-3)
    """
    # Get template
    template = PHISHING_TEMPLATES[template_index]
    attacker_ip = ATTACKER_IPS.get(attacker_location, ATTACKER_IPS["local"])
    
    # Create message
    msg = MIMEMultipart()
    msg["Subject"] = template["subject"]
    msg["From"] = SENDER_EMAIL
    msg["To"] = TARGET_EMAIL
    msg["Date"] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")
    
    # CRITICAL: Add fake originating IP header
    # This simulates the attacker's real IP
    msg.add_header("X-Originating-IP", f"[{attacker_ip}]")
    
    # Add body
    msg.attach(MIMEText(template["body"], "plain"))
    
    # Send email
    try:
        print(f"\n🚀 Sending phishing test email...")
        print(f"   📧 Subject: {template['subject'][:50]}...")
        print(f"   🌍 Simulated Location: {attacker_location.upper()}")
        print(f"   📍 Attacker IP: {attacker_ip}")
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, TARGET_EMAIL, msg.as_string())
        
        print(f"   ✅ Email sent successfully!")
        print(f"   ⏳ Check your PhishTrap dashboard in ~60 seconds")
        
    except Exception as e:
        print(f"   ❌ Error sending email: {e}")


def interactive_mode():
    """Interactive CLI for sending test emails."""
    print("\n" + "="*60)
    print("🎣 PhishTrap Phishing Email Simulator")
    print("="*60)
    
    # Select location
    print("\n📍 Select attacker location:")
    locations = list(ATTACKER_IPS.keys())
    for i, loc in enumerate(locations, 1):
        print(f"   {i}. {loc.upper()}")
    
    loc_choice = input("\nEnter number (1-{}): ".format(len(locations)))
    try:
        location = locations[int(loc_choice) - 1]
    except:
        print("Invalid choice, using local IP")
        location = "local"
    
    # Select template
    print("\n📧 Select phishing template:")
    for i, template in enumerate(PHISHING_TEMPLATES, 1):
        print(f"   {i}. {template['subject'][:50]}...")
    
    template_choice = input("\nEnter number (1-{}): ".format(len(PHISHING_TEMPLATES)))
    try:
        template_idx = int(template_choice) - 1
    except:
        print("Invalid choice, using first template")
        template_idx = 0
    
    # Send email
    send_phishing_test(location, template_idx)


def batch_test():
    """Send multiple test emails from different locations."""
    print("\n🔥 Batch Test Mode - Sending 4 emails from different locations...")
    
    tests = [
        ("nigeria", 0),
        ("russia", 1),
        ("china", 2),
        ("india", 3),
    ]
    
    for location, template_idx in tests:
        send_phishing_test(location, template_idx)
        print()


if __name__ == "__main__":
    import sys
    
    print("\n" + "="*60)
    print("🎣 PhishTrap Phishing Email Simulator")
    print("="*60)
    print("\n⚠️  IMPORTANT: Update SENDER_PASSWORD in this file first!")
    print("   Line 16: SENDER_PASSWORD = 'your_password_here'\n")
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "batch":
            batch_test()
        else:
            print("Usage: python phishing_simulator.py [batch]")
    else:
        interactive_mode()
