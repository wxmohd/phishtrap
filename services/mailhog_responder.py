"""
MailHog Auto-Responder Service
Sends auto-replies back to MailHog SMTP server for demo purposes.
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, Optional
import os


def send_reply_to_mailhog(
    to: str,
    subject: str,
    body: str,
    from_email: str = "aibot@phishtrap.local",
    smtp_host: str = None,
    smtp_port: int = None
) -> bool:
    """
    Send a reply email to MailHog SMTP server.
    
    Args:
        to: Recipient email address (original sender)
        subject: Reply subject (should start with "Re: ")
        body: Reply body text
        from_email: AI bot email address
        smtp_host: MailHog SMTP host (default from env or localhost)
        smtp_port: MailHog SMTP port (default 1025)
        
    Returns:
        True if sent successfully, False otherwise
    """
    if smtp_host is None:
        smtp_host = os.getenv("SMTP_HOST", "localhost")
    
    if smtp_port is None:
        smtp_port = int(os.getenv("SMTP_PORT", "1025"))
    
    try:
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = from_email
        msg['To'] = to
        msg['Date'] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")
        msg['In-Reply-To'] = f"<phishtrap-reply-{datetime.now().timestamp()}>"
        
        # Add body
        msg.attach(MIMEText(body, 'plain'))
        
        # Send via MailHog SMTP
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.send_message(msg)
        
        print(f"[MAILHOG_RESPONDER] ✓ Reply sent to {to}")
        return True
        
    except Exception as e:
        print(f"[MAILHOG_RESPONDER] ✗ Error sending reply to {to}: {e}")
        return False


def create_reply_subject(original_subject: str) -> str:
    """Create reply subject line."""
    if not original_subject:
        return "Re: Your message"
    
    if original_subject.startswith("Re: "):
        return original_subject
    
    return f"Re: {original_subject}"


def test_mailhog_connection(smtp_host: str = "localhost", smtp_port: int = 1025) -> bool:
    """
    Test connection to MailHog SMTP server.
    
    Returns:
        True if connection successful, False otherwise
    """
    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=5) as server:
            server.noop()
        print(f"[MAILHOG_RESPONDER] ✓ Connected to MailHog at {smtp_host}:{smtp_port}")
        return True
    except Exception as e:
        print(f"[MAILHOG_RESPONDER] ✗ Cannot connect to MailHog: {e}")
        return False
