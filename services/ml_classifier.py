"""
ML-powered phishing classifier using trained model.
Handles the phish_model.joblib format with vectorizer + model.
"""
import os
import re
import joblib
from typing import Dict, Optional, List

# Global model cache
_ml_model = None
_vectorizer = None
_model_loaded = False


def _load_model():
    """Load the trained ML model and vectorizer."""
    global _ml_model, _vectorizer, _model_loaded
    
    if _model_loaded:
        return _vectorizer, _ml_model
    
    try:
        # Try root directory first
        model_path = os.path.join(os.path.dirname(__file__), '..', 'phish_model.joblib')
        
        if not os.path.exists(model_path):
            print("[ML_CLASSIFIER] ⚠ phish_model.joblib not found")
            return None, None
        
        # Load the model dictionary
        model_dict = joblib.load(model_path)
        _vectorizer = model_dict.get("vectorizer")
        _ml_model = model_dict.get("model")
        _model_loaded = True
        
        print("[ML_CLASSIFIER] ✓ ML model loaded successfully")
        print(f"[ML_CLASSIFIER]   Vectorizer: {type(_vectorizer).__name__}")
        print(f"[ML_CLASSIFIER]   Model: {type(_ml_model).__name__}")
        
        return _vectorizer, _ml_model
        
    except Exception as e:
        print(f"[ML_CLASSIFIER] ⚠ Could not load ML model: {e}")
        _model_loaded = True  # Don't retry
        return None, None


# Text cleaning functions (matching your training pipeline)
url_re = re.compile(r'https?://\S+|www\.\S+', re.IGNORECASE)
email_re = re.compile(r'\b[\w\.-]+@[\w\.-]+\.\w+\b')
ws_re = re.compile(r'\s+')


def clean_text(text: str) -> str:
    """
    Clean text exactly as done during training.
    This is critical for model performance!
    """
    if not text:
        return ""
    
    text = str(text).lower()
    text = url_re.sub(" URL ", text)         # Replace URLs with token
    text = email_re.sub(" EMAIL ", text)     # Replace emails with token
    text = re.sub(r'<[^>]+>', ' ', text)     # Strip HTML tags
    text = ws_re.sub(' ', text).strip()      # Normalize whitespace
    
    return text


def classify_email_ml(
    subject: Optional[str],
    body: Optional[str],
    urls: Optional[List[str]] = None,
    sender: Optional[str] = None
) -> Optional[Dict[str, any]]:
    """
    Classify email using the trained ML model.
    
    Args:
        subject: Email subject line
        body: Email body (text or HTML)
        urls: List of URLs (not used by model, but kept for compatibility)
        sender: Sender email (not used by model, but kept for compatibility)
        
    Returns:
        Dict with:
        - label: 'phishing' | 'legit'
        - score: float in [0, 1] (probability of phishing)
        - explanation: human-readable reasoning
        
        Returns None if model not available.
    """
    vectorizer, model = _load_model()
    
    if vectorizer is None or model is None:
        return None
    
    # Combine subject and body (matching training format)
    text_parts = []
    if subject:
        text_parts.append(str(subject))
    if body:
        text_parts.append(str(body))
    
    combined_text = "\n".join(text_parts)
    
    # Clean text using the same pipeline as training
    cleaned_text = clean_text(combined_text)
    
    if not cleaned_text:
        return {
            "label": "legit",
            "score": 0.0,
            "explanation": "Empty email content"
        }
    
    try:
        # Transform text using vectorizer
        X = vectorizer.transform([cleaned_text])
        
        # Predict
        prediction = model.predict(X)[0]  # Returns 0 or 1
        
        # Get probability if available
        if hasattr(model, "predict_proba"):
            proba = model.predict_proba(X)[0]
            # proba[0] = probability of class 0 (legit)
            # proba[1] = probability of class 1 (phishing)
            phishing_prob = float(proba[1])
        else:
            # Fallback if no predict_proba
            phishing_prob = 1.0 if prediction == 1 else 0.0
        
        # Convert numeric prediction to label
        if prediction == 1:
            label = "phishing"
            explanation = f"ML model detected phishing patterns (confidence: {phishing_prob*100:.1f}%)"
        else:
            label = "legit"
            explanation = f"ML model classified as legitimate (confidence: {(1-phishing_prob)*100:.1f}%)"
        
        return {
            "label": label,
            "score": round(phishing_prob, 3),
            "explanation": explanation
        }
        
    except Exception as e:
        print(f"[ML_CLASSIFIER] ⚠ Prediction failed: {e}")
        return None


def is_model_available() -> bool:
    """Check if ML model is available."""
    vectorizer, model = _load_model()
    return vectorizer is not None and model is not None
