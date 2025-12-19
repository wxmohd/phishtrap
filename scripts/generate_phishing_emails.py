#!/usr/bin/env python3
"""
Phishing Email Generator for PhishTrap Demo
Generates realistic phishing emails and sends them to MailHog or Gmail SMTP.

Supports two modes:
1. MailHog mode: Send to local MailHog sandbox (default)
2. Gmail mode: Send to real Gmail inbox for realistic demo
"""
import smtplib
import random
import argparse
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime


# Phishing email templates
PHISHING_TEMPLATES = [
    {
        "subject": "URGENT: Your PayPal Account Has Been Limited",
        "sender": "security@paypa1-secure.com",
        "body": """Dear Valued Customer,

We have detected unusual activity on your PayPal account. For your security, we have temporarily limited your account access.

To restore full access, please verify your identity immediately:
http://bit.ly/paypal-verify-2024

This link will expire in 24 hours. Failure to verify will result in permanent account suspension.

Thank you for your prompt attention.
PayPal Security Team""",
        "type": "phishing"
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
http://amazon-support.net/cancel

Thank you for shopping with Amazon!""",
        "type": "phishing"
    },
    {
        "subject": "Your Bank Account Requires Immediate Verification",
        "sender": "alerts@secure-banking.com",
        "body": """IMPORTANT SECURITY ALERT

We have detected suspicious login attempts to your online banking account from an unrecognized device.

Location: Lagos, Nigeria
IP Address: 197.210.xxx.xxx
Time: Today at 3:42 AM

To protect your account, please verify your identity:
https://secure-bank-verify.com/login

If you do not verify within 12 hours, your account will be locked for security purposes.

National Bank Security Department""",
        "type": "phishing"
    },
    {
        "subject": "Congratulations! You've Won $500,000 in the International Lottery",
        "sender": "claims@intl-lottery-board.org",
        "body": """OFFICIAL LOTTERY NOTIFICATION

Congratulations! Your email address has been randomly selected as a winner in our International Email Lottery Program.

Prize Amount: $500,000.00 USD
Claim Number: ILP-2024-7849
Batch: 23/UK/2024

To claim your prize, please provide the following information:
- Full Name
- Address
- Phone Number
- Date of Birth

Submit your claim here: http://lottery-claims.org/winner/7849

You must claim within 7 days or the prize will be forfeited.

International Lottery Board""",
        "type": "phishing"
    },
    {
        "subject": "Your Microsoft Account Security Code",
        "sender": "account-security@microsoft-services.com",
        "body": """Microsoft Account Security

Someone tried to sign in to your Microsoft account from a new device.

If this was you, please enter this security code: 847392

If this wasn't you, your account may be compromised. Please secure your account immediately:
https://microsoft-account-security.com/verify

Location: Unknown
Device: Windows PC
Time: 15 minutes ago

Microsoft Account Team""",
        "type": "phishing"
    },
    {
        "subject": "IRS Tax Refund Notification - Action Required",
        "sender": "refunds@irs-treasury.gov",
        "body": """Internal Revenue Service

You are eligible for a tax refund of $2,847.00

Refund Amount: $2,847.00
Tax Year: 2023
Reference: IRS-REF-2024-9384

To receive your refund via direct deposit, please verify your banking information:
https://irs-refund-portal.com/claim/9384

This refund will expire if not claimed within 30 days.

Internal Revenue Service
U.S. Department of Treasury""",
        "type": "phishing"
    },
    {
        "subject": "Your Package Delivery Failed - Rescheduling Required",
        "sender": "delivery@dhl-express.net",
        "body": """DHL Express Delivery Notice

We attempted to deliver your package but no one was available to sign.

Tracking Number: DHL-9847-2847-US
Delivery Attempts: 2
Status: Awaiting Rescheduling

To reschedule delivery, please confirm your address and preferred time:
http://dhl-tracking.net/reschedule/9847

Your package will be returned to sender if not rescheduled within 48 hours.

DHL Express Customer Service""",
        "type": "phishing"
    },
    {
        "subject": "LinkedIn: You appeared in 15 searches this week",
        "sender": "notifications@linkedin-network.com",
        "body": """Hi there,

Your profile has been getting attention! You appeared in 15 searches this week.

See who's viewing your profile:
https://linkedin-profile-views.com/dashboard

Premium members can see:
- Full names of profile viewers
- Their job titles and companies
- When they viewed your profile

Upgrade to Premium: https://linkedin-premium.com/upgrade

LinkedIn Notifications""",
        "type": "suspicious"
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

Netflix Billing Team""",
        "type": "phishing"
    },
    {
        "subject": "Apple ID: Your account has been locked",
        "sender": "support@apple-id-security.com",
        "body": """Your Apple ID has been locked for security reasons.

Apple ID: user@example.com
Locked: Today at 2:15 PM
Reason: Suspicious activity detected

To unlock your account, please verify your identity:
https://appleid-unlock.com/verify

You will need to:
1. Confirm your email address
2. Answer security questions
3. Verify payment method

If you do not unlock within 24 hours, your account will be permanently disabled.

Apple Support Team""",
        "type": "phishing"
    },
]

# Legitimate email templates for comparison
LEGITIMATE_TEMPLATES = [
    {
        "subject": "Your Monthly Newsletter - PhishTrap Updates",
        "sender": "newsletter@phishtrap.local",
        "body": """Hello,

Here's what's new in PhishTrap this month:

- Improved AI classification accuracy
- New dashboard metrics
- Enhanced email parsing

Visit our blog for more details: https://phishtrap.local/blog

Best regards,
PhishTrap Team""",
        "type": "legit"
    },
    {
        "subject": "Meeting Reminder: Team Sync Tomorrow at 10 AM",
        "sender": "calendar@company.local",
        "body": """Hi Team,

This is a reminder about our weekly sync meeting tomorrow.

Time: 10:00 AM - 11:00 AM
Location: Conference Room B
Agenda: Sprint planning and retrospective

See you there!

Best,
Project Manager""",
        "type": "legit"
    },
]


def send_email_to_mailhog(subject, sender, body, smtp_host='localhost', smtp_port=1025, recipient='honeypot@phishtrap.local'):
    """Send email to MailHog SMTP (sandbox mode)."""
    try:
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = sender
        msg['To'] = recipient
        msg['Date'] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")
        
        msg.attach(MIMEText(body, 'plain'))
        
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.send_message(msg)
        
        return True
    except Exception as e:
        print(f"❌ Error sending email: {e}")
        return False


def send_email_to_gmail(subject, sender, body, target_email, gmail_user, gmail_password):
    """
    Send email to real Gmail account via Gmail SMTP.
    
    Args:
        subject: Email subject
        sender: Fake sender address (for From header)
        body: Email body
        target_email: Gmail address to send to (e.g., honeypot1@gmail.com)
        gmail_user: Your Gmail address for SMTP authentication
        gmail_password: Gmail app password (not regular password!)
    
    Returns:
        bool: True if sent successfully
    """
    msg = MIMEMultipart()
    msg['From'] = sender  # Fake sender (will show in Gmail)
    msg['To'] = target_email
    msg['Subject'] = subject
    msg['Date'] = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S +0000')
    
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        # Connect to Gmail SMTP
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        
        # Authenticate with your Gmail
        server.login(gmail_user, gmail_password)
        
        # Send email
        server.send_message(msg)
        server.quit()
        
        return True
    except smtplib.SMTPAuthenticationError:
        print(f"  ❌ Authentication failed. Check Gmail credentials.")
        print(f"     Make sure you're using an App Password, not your regular password.")
        return False
    except Exception as e:
        print(f"  ❌ Error sending email: {e}")
        return False


def send_email_to_outlook(subject, body, target_email, outlook_user, outlook_password):
    """
    Send email to Outlook account via Outlook SMTP.
    
    Args:
        subject: Email subject
        body: Email body
        target_email: Outlook address to send to (e.g., d3m01231@outlook.com)
        outlook_user: Your Outlook phishing account (e.g., phishing_testt1@outlook.com)
        outlook_password: Outlook account password
    
    Returns:
        bool: True if sent successfully
    """
    msg = MIMEMultipart()
    msg['From'] = outlook_user  # Real sender (your phishing account)
    msg['To'] = target_email
    msg['Subject'] = subject
    msg['Date'] = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S +0000')
    
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        # Connect to Outlook SMTP
        server = smtplib.SMTP('smtp-mail.outlook.com', 587)
        server.starttls()
        
        # Authenticate with Outlook
        server.login(outlook_user, outlook_password)
        
        # Send email
        server.send_message(msg)
        server.quit()
        
        return True
    except smtplib.SMTPAuthenticationError:
        print(f"  ❌ Authentication failed for {outlook_user}. Check password.")
        return False
    except Exception as e:
        print(f"  ❌ Error sending email: {e}")
        return False


def generate_phishing_emails(count=10, include_legit=True, mode='mailhog', 
                            smtp_host='localhost', smtp_port=1025,
                            target_email=None, gmail_user=None, gmail_password=None,
                            outlook_accounts=None):
    """Generate and send phishing emails to MailHog, Gmail, or Outlook."""
    if mode == 'outlook':
        print("🎣 Generating {} phishing emails for Outlook demo...".format(count))
        print(f"📧 SMTP: Outlook (smtp-mail.outlook.com:587)")
        print(f"🎯 Target: {target_email}")
        print(f"🔐 Phishing Accounts: {len(outlook_accounts)} accounts")
        for acc in outlook_accounts:
            print(f"   - {acc['email']}")
    elif mode == 'gmail':
        print("🎣 Generating {} phishing emails for Gmail demo...".format(count))
        print(f"📧 SMTP: Gmail (smtp.gmail.com:587)")
        print(f"🎯 Target: {target_email}")
        print(f"🔐 Auth: {gmail_user}")
    else:
        print("🎣 Generating {} phishing emails for MailHog demo...".format(count))
        print(f"📧 SMTP: {smtp_host}:{smtp_port}")
        print(f"🎯 Target: honeypot@phishtrap.local")
    print()
    templates = PHISHING_TEMPLATES.copy()
    if include_legit:
        templates.extend(LEGITIMATE_TEMPLATES)
    
    sent = 0
    failed = 0
    
    for i in range(count):
        template = random.choice(templates)
        
        print(f"[{i+1}/{count}] Sending: {template['subject'][:50]}...")
        
        if mode == 'outlook':
            # Rotate between phishing accounts
            account = outlook_accounts[i % len(outlook_accounts)]
            print(f"  📤 From: {account['email']}")
            success = send_email_to_outlook(
                subject=template['subject'],
                body=template['body'],
                target_email=target_email,
                outlook_user=account['email'],
                outlook_password=account['password']
            )
        elif mode == 'gmail':
            success = send_email_to_gmail(
                subject=template['subject'],
                sender=template['sender'],
                body=template['body'],
                target_email=target_email,
                gmail_user=gmail_user,
                gmail_password=gmail_password
            )
        else:
            success = send_email_to_mailhog(
                subject=template['subject'],
                sender=template['sender'],
                body=template['body'],
                smtp_host=smtp_host,
                smtp_port=smtp_port
            )
        
        if success:
            sent += 1
            if mode == 'outlook':
                print(f"  ✓ Sent from {account['email']}")
            else:
                print(f"  ✓ Sent from {template['sender']}")
        else:
            failed += 1
        
        print()
    
    print(f"\n{'='*60}")
    print(f"📊 Summary:")
    print(f"  ✓ Sent: {sent}")
    print(f"  ✗ Failed: {failed}")
    
    if mode == 'outlook':
        print(f"\n🌐 View emails in Outlook: https://outlook.live.com")
        print(f"   Login as: {target_email}")
        print(f"🎯 Next: PhishTrap will auto-sync within 60 seconds!")
        print(f"   Dashboard: http://localhost:5000")
    elif mode == 'gmail':
        print(f"\n🌐 View emails in Gmail: https://mail.google.com")
        print(f"   Login as: {target_email}")
        print(f"🎯 Next: Connect Gmail account in PhishTrap dashboard")
        print(f"   Then click 'Sync Gmail' with auto-reply enabled")
    else:
        print(f"\n🌐 View emails in MailHog: http://localhost:8025")
        print(f"🎯 Next: Click 'Sync from MailHog' in PhishTrap dashboard")
    
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Generate phishing emails for PhishTrap demo (MailHog, Gmail, or Outlook)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Outlook mode (recommended - uses your 2 phishing accounts)
  python3 generate_phishing_emails.py --mode outlook --count 10
  
  # MailHog mode (default - safe sandbox)
  python3 generate_phishing_emails.py --count 10
  
  # Gmail mode (realistic demo)
  python3 generate_phishing_emails.py --mode gmail \
    --target honeypot1@gmail.com \
    --gmail-user phishtrap.sender@gmail.com \
    --gmail-password "your-app-password"
  
  # Generate only phishing (no legitimate emails)
  python3 generate_phishing_emails.py --mode outlook --no-legit --count 20
        """
    )
    
    # Mode selection
    parser.add_argument(
        '--mode', '-m',
        type=str,
        choices=['mailhog', 'gmail', 'outlook'],
        default='mailhog',
        help='Delivery mode: mailhog (sandbox), gmail (real inbox), or outlook (your phishing accounts)'
    )
    
    # General options
    parser.add_argument(
        '--count', '-c',
        type=int,
        default=10,
        help='Number of emails to generate (default: 10)'
    )
    
    parser.add_argument(
        '--no-legit',
        action='store_true',
        help='Generate only phishing emails (exclude legitimate ones)'
    )
    
    # MailHog options
    parser.add_argument(
        '--host',
        type=str,
        default='localhost',
        help='MailHog SMTP host (default: localhost)'
    )
    
    parser.add_argument(
        '--port',
        type=int,
        default=1025,
        help='MailHog SMTP port (default: 1025)'
    )
    
    # Gmail options
    parser.add_argument(
        '--target',
        type=str,
        help='Target Gmail address (e.g., honeypot1@gmail.com)'
    )
    
    parser.add_argument(
        '--gmail-user',
        type=str,
        help='Your Gmail address for SMTP authentication'
    )
    
    parser.add_argument(
        '--gmail-password',
        type=str,
        help='Gmail app password (not regular password!)'
    )
    
    args = parser.parse_args()
    
    # Outlook mode
    if args.mode == 'outlook':
        # Hardcoded phishing accounts and target
        outlook_accounts = [
            {
                'email': 'phishing_testt1@outlook.com',
                'password': os.getenv('OUTLOOK_PHISH1_PASSWORD', '')
            },
            {
                'email': 'phishing_testt2@outlook.com',
                'password': os.getenv('OUTLOOK_PHISH2_PASSWORD', '')
            }
        ]
        target_email = 'd3m01231@outlook.com'
        
        # Check if passwords are set
        if not outlook_accounts[0]['password'] or not outlook_accounts[1]['password']:
            print("❌ Error: Outlook mode requires passwords for phishing accounts")
            print("\n💡 Set environment variables:")
            print("   export OUTLOOK_PHISH1_PASSWORD='password_for_phishing_testt1'")
            print("   export OUTLOOK_PHISH2_PASSWORD='password_for_phishing_testt2'")
            print("\nOr edit the script to hardcode passwords (not recommended)")
            exit(1)
        
        generate_phishing_emails(
            count=args.count,
            include_legit=not args.no_legit,
            mode='outlook',
            target_email=target_email,
            outlook_accounts=outlook_accounts
        )
    
    # Gmail mode validation
    elif args.mode == 'gmail':
        # Try to get from environment variables if not provided
        target = args.target or os.getenv('GMAIL_TARGET')
        gmail_user = args.gmail_user or os.getenv('GMAIL_USER')
        gmail_password = args.gmail_password or os.getenv('GMAIL_APP_PASSWORD')
        
        if not all([target, gmail_user, gmail_password]):
            print("❌ Error: Gmail mode requires --target, --gmail-user, and --gmail-password")
            print("   Or set environment variables: GMAIL_TARGET, GMAIL_USER, GMAIL_APP_PASSWORD")
            print("\n💡 To get Gmail app password:")
            print("   1. Go to https://myaccount.google.com/security")
            print("   2. Enable 2-Step Verification")
            print("   3. Generate App Password for 'Mail'")
            print("   4. Use that 16-character password (not your regular password)")
            exit(1)
        
        generate_phishing_emails(
            count=args.count,
            include_legit=not args.no_legit,
            mode='gmail',
            target_email=target,
            gmail_user=gmail_user,
            gmail_password=gmail_password
        )
    else:
        # MailHog mode
        generate_phishing_emails(
            count=args.count,
            include_legit=not args.no_legit,
            mode='mailhog',
            smtp_host=args.host,
            smtp_port=args.port
        )


if __name__ == "__main__":
    main()
