# ai/inference.py

import os
import joblib

# in case we want to reuse the email parser later
try:
    from utils.email_parser import clean_text  # your current parser
except Exception:
    clean_text = None  # we'll just fallback to our own cleaning

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "model.pkl")

_model = None  # lazy-loaded


def _load_model():
    global _model
    if _model is None:
        if not os.path.exists(MODEL_PATH):
            raise RuntimeError(
                f"[ai] Model file not found at {MODEL_PATH}. "
                "Run: python -m ai.train_model"
            )
        _model = joblib.load(MODEL_PATH)
    return _model


def _simple_clean(s: str) -> str:
    s = s or ""
    return s.replace("\n", " ").replace("\r", " ").strip().lower()


def classify_email(subject: str = "", body: str = "", sender: str = "") -> dict:
    """
    Returns a dict like:
    {
        "label": "phishing" / "legit",
        "score": 0.91,
        "explanation": "subject matched phishing pattern",
    }
    """
    model = _load_model()

    # build one text field
    parts = []
    if subject:
        parts.append(f"subject: {subject}")
    if sender:
        parts.append(f"from: {sender}")
    if body:
        parts.append(body)

    text = " ".join(parts)
    if clean_text:
        text = clean_text(text)
    else:
        text = _simple_clean(text)

    # model is a sklearn Pipeline: we can just do predict_proba
    # but LogisticRegression has predict_proba; LinearSVC does not
    label = model.predict([text])[0]

    # best effort for score
    score = None
    if hasattr(model, "predict_proba"):
        proba = model.predict_proba([text])[0]
        score = float(max(proba))
    else:
        score = 1.0  # can't compute, just say full confidence

    explanation = ""
    if label == "phishing":
        explanation = "Content resembles known phishing patterns."
    else:
        explanation = "Content looks similar to benign internal emails."

    return {
        "label": label,
        "score": score,
        "explanation": explanation,
        "raw_text": text,
    }
