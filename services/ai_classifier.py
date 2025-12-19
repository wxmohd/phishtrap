"""
AI-powered email classifier for phishing detection.
Uses ML model if available, falls back to heuristics.
"""
import re
import os
from typing import Dict, List, Optional

# Try to load ML model
_ml_model = None
_use_ml = False

def _load_ml_model():
    """Load ML model if available."""
    global _ml_model, _use_ml
    
    if _ml_model is not None:
        return _ml_model
    
    try:
        import joblib
        model_path = os.path.join(os.path.dirname(__file__), '..', 'ai', 'model.pkl')
        
        if os.path.exists(model_path) and os.path.getsize(model_path) > 0:
            _ml_model = joblib.load(model_path)
            _use_ml = True
            print("[AI_CLASSIFIER] ✓ ML model loaded successfully")
            return _ml_model
        else:
            print("[AI_CLASSIFIER] ⚠ ML model not found or empty, using heuristics")
            return None
    except Exception as e:
        print(f"[AI_CLASSIFIER] ⚠ Could not load ML model: {e}, using heuristics")
        return None


# Phishing indicator keywords
PHISHING_KEYWORDS = [
    "verify", "suspend", "urgent", "account", "confirm", "click here",
    "update", "security", "alert", "locked", "unusual activity",
    "reset password", "verify identity", "confirm identity",
    "limited time", "act now", "immediate action", "expire",
    "prize", "winner", "congratulations", "claim", "reward",
    "refund", "tax", "payment", "invoice", "debt",
]

# Legitimate brand spoofing patterns
BRAND_PATTERNS = [
    r'\bpaypal\b', r'\bbank\b', r'\bamazon\b', r'\bapple\b',
    r'\bmicrosoft\b', r'\bgoogle\b', r'\bfacebook\b', r'\bnetflix\b',
    r'\blinkedin\b', r'\btwitter\b', r'\binstagram\b',
]

# Suspicious URL patterns
SUSPICIOUS_URL_PATTERNS = [
    r'bit\.ly', r'tinyurl', r'goo\.gl',  # URL shorteners
    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}',  # IP addresses
    r'[a-z0-9]{20,}',  # Long random strings
]

# Suspicious domain keywords (phishing domains often contain these)
SUSPICIOUS_DOMAIN_KEYWORDS = [
    'verify', 'secure', 'account', 'login', 'signin', 'update',
    'confirm', 'validation', 'security', 'support', 'service',
    'password', 'billing', 'payment', 'alert', 'notification'
]

# Trusted email addresses - only these specific addresses are whitelisted
TRUSTED_DOMAINS = [
    'account-security-noreply@accountprotection.microsoft.com',
    'member_services@outlook.com',
]


def is_from_trusted_domain(sender_email: Optional[str]) -> bool:
    """
    Check if sender email is from a trusted domain.
    
    Args:
        sender_email: Email address of sender
        
    Returns:
        True if from trusted domain, False otherwise
    """
    if not sender_email:
        return False
    
    sender_email = sender_email.lower()
    
    # Extract domain from email
    if '@' in sender_email:
        domain = sender_email.split('@')[1]
        
        # Check exact match or subdomain match
        for trusted in TRUSTED_DOMAINS:
            if domain == trusted or domain.endswith('.' + trusted):
                return True
    
    return False


def _classify_with_ml(
    subject: Optional[str],
    body: Optional[str],
    urls: Optional[List[str]],
    sender: Optional[str],
    model
) -> Dict[str, any]:
    """Classify email using ML model."""
    
    # Combine text for ML model
    text_parts = []
    if subject:
        text_parts.append(f"subject: {subject}")
    if sender:
        text_parts.append(f"from: {sender}")
    if body:
        text_parts.append(body)
    if urls:
        text_parts.append(f"urls: {' '.join(urls)}")
    
    text = " ".join(text_parts)
    
    # Predict
    label = model.predict([text])[0]
    
    # Get probability if available
    score = 1.0
    if hasattr(model, "predict_proba"):
        proba = model.predict_proba([text])[0]
        # Get probability of phishing class
        if label == "phishing":
            score = float(max(proba))
        else:
            score = float(min(proba))
    
    # Build explanation
    if label == "phishing":
        explanation = "ML model: content matches phishing patterns (trained on dataset)"
    else:
        explanation = "ML model: content appears legitimate (trained on dataset)"
    
    return {
        "label": label,
        "score": round(score, 3),
        "explanation": explanation
    }


def classify_email(
    subject: Optional[str],
    body: Optional[str],
    urls: Optional[List[str]] = None,
    sender: Optional[str] = None
) -> Dict[str, any]:
    """
    Classify an email as phishing, suspicious, or legitimate.
    Uses ML model if available, otherwise uses heuristics.
    
    Args:
        subject: Email subject line
        body: Email body (text or HTML)
        urls: List of URLs found in email
        sender: Email address of sender
        
    Returns:
        Dict with:
        - label: 'phishing' | 'suspicious' | 'legit'
        - score: float in [0, 1] (probability of phishing)
        - explanation: human-readable reasoning
    """
    # Check if sender is from trusted domain first
    if sender and is_from_trusted_domain(sender):
        return {
            "label": "legit",
            "score": 0.0,
            "explanation": "from trusted domain (whitelisted)"
        }
    
    # DISABLED: ML model is less accurate than heuristics
    # Using pure heuristic-based classification for better accuracy
    # try:
    #     from services.ml_classifier import classify_email_ml
    #     ml_result = classify_email_ml(subject, body, urls, sender)
    #     if ml_result is not None:
    #         print(f"[AI_CLASSIFIER] ✓ ML classification: {ml_result['label']} ({ml_result['score']*100:.1f}%)")
    #         return ml_result
    # except Exception as e:
    #     print(f"[AI_CLASSIFIER] ⚠ ML classification failed: {e}, falling back to heuristics")
    
    print(f"[AI_CLASSIFIER] Using heuristic classification")
    
    # Combine text for analysis
    text = f"{subject or ''} {body or ''}".lower()
    urls = urls or []
    
    # Initialize scoring
    phishing_score = 0.0
    reasons = []
    
    # 1. Keyword analysis (increased weight)
    # Use word boundary matching to avoid false positives (e.g., "verify" shouldn't match "verification")
    keyword_count = 0
    for kw in PHISHING_KEYWORDS:
        # Match whole words/phrases only
        pattern = r'\b' + re.escape(kw) + r'\b'
        if re.search(pattern, text, re.IGNORECASE):
            keyword_count += 1
    
    if keyword_count > 0:
        # More keywords = higher confidence
        if keyword_count >= 5:
            keyword_weight = 0.6  # Very high confidence
        elif keyword_count >= 3:
            keyword_weight = 0.4  # High confidence
        else:
            keyword_weight = keyword_count * 0.15  # Moderate
        
        phishing_score += keyword_weight
        reasons.append(f"{keyword_count} phishing keyword(s)")
    
    # 2. Brand spoofing detection
    brand_mentions = sum(1 for pattern in BRAND_PATTERNS if re.search(pattern, text, re.IGNORECASE))
    if brand_mentions > 0:
        # Brand mentions + urgency keywords = likely phishing
        urgency_words = ["urgent", "suspend", "locked", "expire", "act now"]
        has_urgency = any(word in text for word in urgency_words)
        if has_urgency:
            phishing_score += 0.3
            reasons.append("brand mention + urgency")
        else:
            phishing_score += 0.1
            reasons.append("brand mention")
    
    # 3. URL analysis
    if len(urls) > 5:
        phishing_score += 0.2
        reasons.append(f"{len(urls)} URLs (high count)")
    elif len(urls) > 2:
        phishing_score += 0.1
        reasons.append(f"{len(urls)} URLs")
    
    # Check for suspicious URL patterns
    suspicious_url_count = 0
    for url in urls:
        # Check existing patterns
        for pattern in SUSPICIOUS_URL_PATTERNS:
            if re.search(pattern, url, re.IGNORECASE):
                suspicious_url_count += 1
                break
        
        # Check for suspicious domain keywords
        domain_match = re.search(r'://([^/]+)', url)
        if domain_match:
            domain = domain_match.group(1).lower()
            # Check if domain contains suspicious keywords
            for keyword in SUSPICIOUS_DOMAIN_KEYWORDS:
                if keyword in domain:
                    suspicious_url_count += 1
                    reasons.append(f"suspicious domain: {domain}")
                    break
    
    if suspicious_url_count > 0:
        phishing_score += min(suspicious_url_count * 0.25, 0.5)
        if "suspicious domain" not in '; '.join(reasons):
            reasons.append(f"{suspicious_url_count} suspicious URL(s)")
    
    # 4. Mismatched sender domain (placeholder - would need sender analysis)
    # This would check if sender domain matches claimed brand
    
    # 5. HTML/text ratio (placeholder - would analyze MIME structure)
    
    # Normalize score to [0, 1]
    phishing_score = min(phishing_score, 1.0)
    
    # Determine label based on score thresholds
    if phishing_score >= 0.7:
        label = "phishing"
    elif phishing_score >= 0.3:
        label = "suspicious"
    else:
        label = "legit"
    
    # Build explanation
    if reasons:
        explanation = "; ".join(reasons)
    else:
        explanation = "no phishing indicators detected"
    
    return {
        "label": label,
        "score": round(phishing_score, 3),
        "explanation": explanation,
    }


def classify_with_model(
    subject: Optional[str],
    body: Optional[str],
    urls: Optional[List[str]] = None,
    model_path: Optional[str] = None
) -> Dict[str, any]:
    """
    Placeholder for ML model-based classification.
    
    In production, this would:
    1. Load a trained sklearn/HF model from model_path
    2. Vectorize/tokenize the email content
    3. Run inference
    4. Return predictions
    
    For now, falls back to heuristic classifier.
    """
    # TODO: Implement model loading and inference
    # Example:
    # model = joblib.load(model_path)
    # features = vectorize(subject, body, urls)
    # prediction = model.predict_proba(features)
    # return format_prediction(prediction)
    
    return classify_email(subject, body, urls)
