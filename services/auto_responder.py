"""
Auto-responder service for replying to phishing emails.
Generates contextual replies based on email content and AI classification.
"""
import random
from typing import Dict, Optional


# Response templates based on phishing type
RESPONSE_TEMPLATES = {
    "phishing": [
        "Thank you for your email. I've reviewed the information and would like to proceed. Could you please provide more details about the verification process?",
        "I received your urgent notice. I'm concerned about my account security. What specific information do you need from me?",
        "Thanks for alerting me to this issue. I want to resolve this immediately. Please send me the verification link again.",
        "I appreciate you reaching out. I'm ready to update my account information. What are the next steps?",
    ],
    "suspicious": [
        "Thank you for your message. Could you clarify what action is required on my part?",
        "I received your email. Can you provide more information about this request?",
        "Thanks for contacting me. I'd like to learn more about this opportunity.",
    ],
    "legit": [
        "Thank you for your email. I'll review this and get back to you soon.",
        "I've received your message and will respond shortly.",
    ],
}


def generate_reply(email_data: Dict, ai_label: str) -> Optional[str]:
    """
    Generate an appropriate reply based on email content and AI classification.
    
    Args:
        email_data: Email dict with subject, sender, body
        ai_label: AI classification (phishing/suspicious/legit)
        
    Returns:
        Reply body text, or None if no reply should be sent
    """
    # Only reply to phishing and suspicious emails
    if ai_label not in ["phishing", "suspicious"]:
        return None
    
    # Select random template
    templates = RESPONSE_TEMPLATES.get(ai_label, [])
    if not templates:
        return None
    
    reply_body = random.choice(templates)
    
    # Add some personalization based on email content
    subject = email_data.get("subject", "").lower()
    
    if "paypal" in subject:
        reply_body += "\n\nI use PayPal frequently for my business transactions."
    elif "bank" in subject or "account" in subject:
        reply_body += "\n\nI want to ensure my account remains secure."
    elif "amazon" in subject:
        reply_body += "\n\nI'm a regular Amazon customer."
    elif "prize" in subject or "winner" in subject:
        reply_body += "\n\nThis is exciting news! I'd love to claim my prize."
    
    reply_body += "\n\nBest regards"
    
    return reply_body


def should_auto_reply(email_data: Dict, ai_label: str, ai_score: float) -> bool:
    """
    Determine if an email should receive an auto-reply.
    
    Args:
        email_data: Email dict
        ai_label: AI classification
        ai_score: AI confidence score (0-1)
        
    Returns:
        True if should reply, False otherwise
    """
    # Only reply to high-confidence phishing emails
    if ai_label == "phishing" and ai_score >= 0.7:
        return True
    
    # Optionally reply to suspicious emails with moderate confidence
    if ai_label == "suspicious" and ai_score >= 0.5:
        # Reply to 50% of suspicious emails (randomize engagement)
        return random.random() < 0.5
    
    return False


def create_reply_subject(original_subject: str) -> str:
    """Create reply subject line."""
    if not original_subject:
        return "Re: Your message"
    if original_subject.startswith("Re: "):
        return original_subject
    return f"Re: {original_subject}"
