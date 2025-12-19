"""
Trusted Domain Whitelist
Domains that should never be flagged as phishing.
"""

# Trusted domains that are always legitimate
TRUSTED_DOMAINS = {
    # Microsoft (official domains only - not user-facing email domains)
    'microsoft.com',
    # 'outlook.com',  # Commented out - allows testing with outlook.com accounts
    # 'live.com',     # Commented out - allows testing
    # 'hotmail.com',  # Commented out - allows testing
    'office.com',
    'office365.com',
    'microsoftonline.com',
    'accountprotection.microsoft.com',
    
    # Google (official domains only - not user-facing email domains)
    'google.com',
    # 'gmail.com',      # Commented out - allows testing with gmail accounts
    # 'googlemail.com', # Commented out - allows testing
    'accounts.google.com',
    
    # Apple
    'apple.com',
    'icloud.com',
    'me.com',
    'mac.com',
    
    # Amazon
    'amazon.com',
    'amazon.co.uk',
    'amazonses.com',
    
    # PayPal
    'paypal.com',
    'paypal.co.uk',
    
    # Banking (add your banks here)
    'chase.com',
    'bankofamerica.com',
    'wellsfargo.com',
    
    # Social Media
    'facebook.com',
    'twitter.com',
    'linkedin.com',
    'instagram.com',
    
    # Other Common Services
    'netflix.com',
    'spotify.com',
    'dropbox.com',
    'slack.com',
}

def is_trusted_domain(email_address: str) -> bool:
    """
    Check if an email address is from a trusted domain.
    
    Args:
        email_address: Email address to check
        
    Returns:
        bool: True if from trusted domain
    """
    if not email_address or '@' not in email_address:
        return False
    
    # Extract domain
    domain = email_address.split('@')[1].lower()
    
    # Check exact match
    if domain in TRUSTED_DOMAINS:
        return True
    
    # Check if subdomain of trusted domain
    # e.g., member_services@outlook.com or no-reply@microsoft.com
    for trusted in TRUSTED_DOMAINS:
        if domain.endswith('.' + trusted) or domain == trusted:
            return True
    
    return False


def get_trusted_domains():
    """Get list of all trusted domains."""
    return sorted(TRUSTED_DOMAINS)
