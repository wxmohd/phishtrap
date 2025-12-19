"""
Admin notification service.
Sends email notifications to admin for uncertain emails requiring review.
"""
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional


def send_admin_notification(email_record, dashboard_url: str = "http://127.0.0.1:5000") -> bool:
    """
    Send email notification to admin for uncertain email.
    
    Args:
        email_record: Email database record
        dashboard_url: Base URL for dashboard links
        
    Returns:
        bool: True if sent successfully
    """
    admin_email = os.getenv('ADMIN_EMAIL', 'admin@ncsc.gov.bh')
    smtp_host = os.getenv('SMTP_HOST', 'localhost')
    smtp_port = int(os.getenv('SMTP_PORT', '1025'))
    
    # Email subject
    subject = f"[PhishTrap] Uncertain Email Requires Review"
    
    # Email body
    body = f"""⚠️ AI Uncertainty Detected

An email has been flagged as uncertain and requires your review.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📧 Email Details:

From: {email_record.sender}
To: {email_record.recipient}
Subject: {email_record.subject}

AI Classification: {email_record.ai_label}
AI Confidence: {email_record.ai_score}% (Uncertain)

Reason for uncertainty:
{email_record.ai_explanation or 'Mixed signals detected'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 Actions Required:

1. Approve Auto-Reply - If this is phishing, approve sending engagement reply
2. Mark as Legitimate - If this is a safe email, mark it as legitimate
3. Blocklist Sender - If this is spam/phishing, blocklist the sender

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 Review in Dashboard:
{dashboard_url}/review/{email_record.id}

Or view all pending reviews:
{dashboard_url}/#pending-reviews

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This is an automated notification from PhishTrap.
Do not reply to this email.
"""
    
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = 'noreply@phishtrap.local'
        msg['To'] = admin_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        # Send via SMTP
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.send_message(msg)
        server.quit()
        
        print(f"[ADMIN_NOTIFIER] ✓ Notification sent to {admin_email} for email ID {email_record.id}")
        return True
        
    except Exception as e:
        print(f"[ADMIN_NOTIFIER] ✗ Failed to send notification: {e}")
        return False


def send_batch_notification(pending_count: int, dashboard_url: str = "http://127.0.0.1:5000") -> bool:
    """
    Send batch notification when multiple emails are pending review.
    
    Args:
        pending_count: Number of pending emails
        dashboard_url: Base URL for dashboard
        
    Returns:
        bool: True if sent successfully
    """
    admin_email = os.getenv('ADMIN_EMAIL', 'admin@ncsc.gov.bh')
    smtp_host = os.getenv('SMTP_HOST', 'localhost')
    smtp_port = int(os.getenv('SMTP_PORT', '1025'))
    
    subject = f"[PhishTrap] {pending_count} Emails Pending Review"
    
    body = f"""⚠️ Multiple Emails Require Review

You have {pending_count} uncertain emails waiting for your review.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 Review Queue Status:

Pending Reviews: {pending_count}

These emails have been flagged by the AI as uncertain and require
human oversight before auto-reply can be sent.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 Action Required:

Please review these emails in the dashboard and take appropriate action.

Review pending emails:
{dashboard_url}/#pending-reviews

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This is an automated notification from PhishTrap.
Do not reply to this email.
"""
    
    try:
        msg = MIMEMultipart()
        msg['From'] = 'noreply@phishtrap.local'
        msg['To'] = admin_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.send_message(msg)
        server.quit()
        
        print(f"[ADMIN_NOTIFIER] ✓ Batch notification sent to {admin_email}")
        return True
        
    except Exception as e:
        print(f"[ADMIN_NOTIFIER] ✗ Failed to send batch notification: {e}")
        return False
