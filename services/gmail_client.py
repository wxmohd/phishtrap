"""
Gmail API client for fetching user emails.
Replaces MailHog in production mode.
"""
import json
import base64
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from email.utils import parsedate_to_datetime

import requests


def fetch_user_emails(access_token: str, max_results: int = 50, include_spam: bool = False) -> List[Dict[str, Any]]:
    """
    Fetch emails from user's Gmail using OAuth access token.
    
    Args:
        access_token: OAuth access token from ConnectedUser.meta
        max_results: Maximum number of emails to fetch
        include_spam: If False, excludes spam folder (default: False)
        
    Returns:
        List of normalized message dicts (same format as mailhog_client)
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }
    
    # Get list of message IDs
    list_url = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
    
    # Query to exclude spam folder (only read inbox)
    query = "-in:spam -in:trash" if not include_spam else ""
    params = {"maxResults": max_results, "q": query}
    
    try:
        resp = requests.get(list_url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"[GMAIL] Error fetching message list: {e}")
        return []
    
    message_ids = [msg["id"] for msg in data.get("messages", [])]
    
    # Fetch full message details
    messages = []
    for msg_id in message_ids:
        msg = _fetch_message_detail(msg_id, headers)
        if msg:
            messages.append(msg)
    
    return messages


def _fetch_message_detail(message_id: str, headers: dict) -> Optional[Dict[str, Any]]:
    """Fetch full message details from Gmail API."""
    url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}"
    params = {"format": "full"}
    
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"[GMAIL] Error fetching message {message_id}: {e}")
        return None
    
    return _normalize_gmail_message(data)


def _normalize_gmail_message(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Convert Gmail API message format to our normalized schema.
    
    Gmail structure:
    {
      "id": "...",
      "payload": {
        "headers": [...],
        "body": {"data": "..."},
        "parts": [...]
      },
      "internalDate": "..."
    }
    """
    try:
        msg_id = raw.get("id", "")
        payload = raw.get("payload", {})
        headers = payload.get("headers", [])
        
        # Extract headers
        def get_header(name: str) -> str:
            for h in headers:
                if h.get("name", "").lower() == name.lower():
                    return h.get("value", "")
            return ""
        
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
                pass
        
        if not received_at:
            # Use internalDate (milliseconds since epoch)
            internal_date = raw.get("internalDate")
            if internal_date:
                received_at = datetime.fromtimestamp(int(internal_date) / 1000)
            else:
                received_at = datetime.utcnow()
        
        # Extract body
        body_text = ""
        body_html = ""
        
        # Check if message has parts (multipart)
        parts = payload.get("parts", [])
        if parts:
            for part in parts:
                mime_type = part.get("mimeType", "")
                body_data = part.get("body", {}).get("data", "")
                
                if body_data:
                    decoded = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="ignore")
                    
                    if "text/plain" in mime_type:
                        body_text = decoded
                    elif "text/html" in mime_type:
                        body_html = decoded
        else:
            # Single part message
            body_data = payload.get("body", {}).get("data", "")
            if body_data:
                body_text = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="ignore")
        
        # Extract URLs
        urls = _extract_urls(body_text + " " + body_html)
        
        return {
            "ext_id": f"gmail_{msg_id}",
            "subject": subject,
            "sender": sender,
            "recipient": recipient,
            "body_text": body_text,
            "body_html": body_html,
            "received_at": received_at,
            "urls": urls,
        }
    except Exception as e:
        print(f"[GMAIL] Error normalizing message: {e}")
        return None


def _extract_urls(text: str) -> List[str]:
    """Extract URLs from text using regex."""
    if not text:
        return []
    
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    matches = re.findall(url_pattern, text, re.IGNORECASE)
    
    urls = []
    seen = set()
    for url in matches:
        url = url.rstrip('.,;:!?)')
        if url not in seen:
            urls.append(url)
            seen.add(url)
    
    return urls


def send_reply(access_token: str, to: str, subject: str, body: str, thread_id: Optional[str] = None, from_email: Optional[str] = None) -> bool:
    """
    Send a reply email via Gmail API.
    
    Args:
        access_token: OAuth access token
        to: Recipient email address
        subject: Email subject (use "Re: " prefix for replies)
        body: Email body (plain text)
        thread_id: Gmail thread ID (for threading replies)
        from_email: Custom sender email for display (optional)
        
    Returns:
        True if sent successfully, False otherwise
    """
    import base64
    from email.mime.text import MIMEText
    
    # Create message
    message = MIMEText(body)
    message['to'] = to
    message['subject'] = subject
    if from_email:
        message['from'] = from_email
    
    # Encode message
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
    
    payload = {"raw": raw_message}
    if thread_id:
        payload["threadId"] = thread_id
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    
    url = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
    
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        print(f"[GMAIL] Reply sent to {to}")
        return True
    except requests.RequestException as e:
        print(f"[GMAIL] Error sending reply: {e}")
        return False
