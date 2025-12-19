"""
MailHog REST API client for fetching messages from the sandbox.
Normalizes message structure for pipeline consumption.
"""
import os
import re
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime
from email.utils import parsedate_to_datetime


def fetch_messages(api_url: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Fetch messages from MailHog API and normalize them.
    
    Args:
        api_url: MailHog API endpoint (defaults to MAILHOG_API env var)
        limit: Maximum number of messages to fetch
        
    Returns:
        List of normalized message dicts with keys:
        - ext_id: unique message ID
        - subject: email subject
        - sender: from address
        - recipient: to address
        - body_text: plain text body
        - body_html: HTML body
        - received_at: datetime
        - urls: list of extracted URLs
    """
    if not api_url:
        api_url = os.getenv("MAILHOG_API", "http://127.0.0.1:8025/api/v2/messages")
    
    try:
        # MailHog API returns JSON with {total, count, start, items: [...]}
        resp = requests.get(api_url, params={"limit": limit}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"[MAILHOG] Error fetching messages: {e}")
        return []
    
    items = data.get("items", [])
    messages = []
    
    for item in items:
        msg = _normalize_message(item)
        if msg:
            messages.append(msg)
    
    return messages


def _normalize_message(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Convert MailHog message format to our normalized schema.
    
    MailHog structure:
    {
      "ID": "...",
      "Content": {
        "Headers": {"From": [...], "To": [...], "Subject": [...], "Date": [...]},
        "Body": "...",
        "MIME": {...}
      },
      "MIME": {...},
      "Raw": {...}
    }
    """
    try:
        if not raw:
            print("[MAILHOG] Error: raw message is None or empty")
            return None
            
        msg_id = raw.get("ID", "")
        content = raw.get("Content")
        
        if content is None:
            print(f"[MAILHOG] Error: Content is None for message {msg_id}")
            return None
            
        headers = content.get("Headers", {})
        
        # Extract header values (MailHog stores them as lists)
        def get_header(name: str) -> str:
            vals = headers.get(name, [])
            return vals[0] if vals else ""
        
        subject = get_header("Subject")
        sender = get_header("From")
        recipient = get_header("To")
        date_str = get_header("Date")
        
        # Parse date
        received_at = None
        if date_str:
            try:
                received_at = parsedate_to_datetime(date_str)
            except Exception:
                received_at = datetime.utcnow()
        else:
            received_at = datetime.utcnow()
        
        # Extract body (MailHog stores raw MIME body)
        body_text = ""
        body_html = ""
        
        # Simple extraction: if MIME parts exist, parse them
        mime_data = content.get("MIME")
        mime_parts = mime_data.get("Parts", []) if mime_data else []
        
        if mime_parts:
            for part in mime_parts:
                part_headers = part.get("Headers", {})
                if part_headers:
                    content_type = part_headers.get("Content-Type", [""])[0] if isinstance(part_headers.get("Content-Type"), list) else ""
                    body = part.get("Body", "")
                    
                    if "text/plain" in content_type:
                        body_text = body
                    elif "text/html" in content_type:
                        body_html = body
        else:
            # Fallback: use raw body
            body_text = content.get("Body", "")
        
        # Extract URLs from text and HTML
        urls = _extract_urls(body_text + " " + body_html)
        
        return {
            "ext_id": msg_id,
            "subject": subject,
            "sender": sender,
            "recipient": recipient,
            "body_text": body_text,
            "body_html": body_html,
            "received_at": received_at,
            "urls": urls,
        }
    except Exception as e:
        print(f"[MAILHOG] Error normalizing message: {e}")
        return None


def _extract_urls(text: str) -> List[str]:
    """
    Extract URLs from text using regex.
    Returns unique URLs found.
    """
    if not text:
        return []
    
    # Simple URL regex (matches http/https URLs)
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    matches = re.findall(url_pattern, text, re.IGNORECASE)
    
    # Remove duplicates and clean
    urls = []
    seen = set()
    for url in matches:
        # Strip trailing punctuation
        url = url.rstrip('.,;:!?)')
        if url not in seen:
            urls.append(url)
            seen.add(url)
    
    return urls
