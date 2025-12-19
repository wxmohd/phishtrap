"""
Reply Detection
Detects if an email is a reply to our AI bot's phishing warning.
"""

import re

def is_reply_to_bot(subject: str, body: str = "") -> bool:
    """
    Check if email is a reply to our AI bot's warning.
    
    Args:
        subject: Email subject line
        body: Email body (optional)
        
    Returns:
        bool: True if this is a reply to our bot
    """
    if not subject:
        return False
    
    subject_lower = subject.lower()
    
    # Check for RE: or FW: patterns
    if not (subject_lower.startswith('re:') or subject_lower.startswith('fw:')):
        return False
    
    # Check if subject contains our bot's warning keywords
    bot_keywords = [
        'phishing attempt detected',
        'security warning',
        'suspicious email',
        'automated security response',
        'phishtrap',
    ]
    
    for keyword in bot_keywords:
        if keyword in subject_lower:
            return True
    
    # Check body for our signature
    if body:
        body_lower = body.lower()
        bot_signatures = [
            'phishtrap security system',
            'automated phishing detection',
            'this is an automated response',
        ]
        
        for signature in bot_signatures:
            if signature in body_lower:
                return True
    
    return False


def should_escalate_reply(sender: str, subject: str, body: str) -> bool:
    """
    Determine if a reply from a phisher should be escalated to admin.
    
    Args:
        sender: Email address of sender
        subject: Email subject
        body: Email body
        
    Returns:
        bool: True if should escalate to admin
    """
    # Always escalate replies to our bot
    if is_reply_to_bot(subject, body):
        return True
    
    # Check for aggressive/threatening language
    aggressive_patterns = [
        r'\b(fuck|shit|damn|hell)\b',
        r'\b(sue|lawsuit|legal action)\b',
        r'\b(threat|threaten|warning)\b',
        r'\b(scam|fraud|fake)\b',
        r'\b(report|police|authorities)\b',
    ]
    
    text = (subject + " " + body).lower()
    for pattern in aggressive_patterns:
        if re.search(pattern, text):
            return True
    
    return False
