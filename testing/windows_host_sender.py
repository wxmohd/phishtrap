"""
PhishTrap - Windows Host Email Sender
Sends email from Windows HOST machine with REAL IP exposed in headers.

INSTRUCTIONS:
1. Save this file to your Windows HOST machine (e.g., C:\phishtrap_sender.py)
2. Install Python on Windows irf not already installed
3. Run: python C:\phishtrap_sender.py
"""
import smtplib
import socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# Configuration
LOCALHOST_SMTP = "localhost"  # hMailServer on Windows
SMTP_PORT = 25
SENDER_EMAIL = "phishingtest@localhost.local"  # From hMailServer config
TARGET_EMAIL = "d3m01231@outlook.com"  # Your honeypot

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


def get_public_ip():
    """Get Windows HOST's public IP address."""
    try:
        # Method 1: Using external service
        import urllib.request
        external_ip = urllib.request.urlopen('https://api.ipify.org').read().decode('utf8')
        return external_ip
    except:
        return "Unable to detect"


def send_phishing_test(template_index=0):
    """
    Send test phishing email from Windows HOST.
    Email will contain HOST's real public IP in headers.
    """
    # Get template
    template = PHISHING_TEMPLATES[template_index]
    
    # Get public IP
    public_ip = get_public_ip()
    hostname = socket.gethostname()
    
    # Create message
    msg = MIMEMultipart()
    msg["Subject"] = template["subject"]
    msg["From"] = SENDER_EMAIL
    msg["To"] = TARGET_EMAIL
    msg["Date"] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")
    
    # Add body
    msg.attach(MIMEText(template["body"], "plain"))
    
    # Send email
    try:
        print("\n" + "="*70)
        print("🚀 Sending phishing test email from Windows HOST")
        print("="*70)
        print(f"\n📧 Subject: {template['subject']}")
        print(f"📤 From: {SENDER_EMAIL}")
        print(f"📥 To: {TARGET_EMAIL}")
        print(f"🖥️  Hostname: {hostname}")
        print(f"🌐 Your Public IP: {public_ip}")
        print(f"\n⚙️  Connecting to localhost SMTP (hMailServer)...")
        
        with smtplib.SMTP(LOCALHOST_SMTP, SMTP_PORT) as server:
            # No authentication needed for localhost
            server.sendmail(SENDER_EMAIL, TARGET_EMAIL, msg.as_string())
        
        print(f"\n✅ Email sent successfully!")
        print(f"\n📍 Expected Result:")
        print(f"   - Email headers will contain: {public_ip}")
        print(f"   - PhishTrap will geolocate this IP")
        print(f"   - Dashboard will show your real location")
        print(f"\n⏳ Check your PhishTrap dashboard in ~60 seconds")
        print("="*70 + "\n")
        
    except Exception as e:
        print(f"\n❌ Error sending email: {e}")
        print(f"\n🔧 Troubleshooting:")
        print(f"   1. Is hMailServer running? (Check Windows Services)")
        print(f"   2. Is SMTP enabled in hMailServer Administrator?")
        print(f"   3. Is Windows Firewall blocking port 25?")
        print(f"   4. Did you configure the domain and account?")


def interactive_mode():
    """Interactive CLI for sending test emails."""
    print("\n" + "="*70)
    print("🎣 PhishTrap - Windows Host Email Sender")
    print("="*70)
    
    # Show public IP
    public_ip = get_public_ip()
    hostname = socket.gethostname()
    print(f"\n🖥️  Your Hostname: {hostname}")
    print(f"🌐 Your Public IP: {public_ip}")
    
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
    send_phishing_test(template_idx)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        # Quick send mode: python script.py 1
        template_idx = int(sys.argv[1]) - 1
        send_phishing_test(template_idx)
    else:
        # Interactive mode
        interactive_mode()
