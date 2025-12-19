"""
Microsoft Graph API client for fetching Outlook emails.
Similar to gmail_client.py but uses Microsoft Graph API.
"""
import json
import base64
import re
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from email.utils import parsedate_to_datetime

import requests


def refresh_access_token(refresh_token: str) -> Optional[Dict[str, Any]]:
    """
    Refresh an expired Microsoft OAuth access token.
    
    Args:
        refresh_token: The refresh token from the original OAuth flow
        
    Returns:
        Dict with new token data or None if refresh failed
    """
    client_id = os.getenv("MICROSOFT_CLIENT_ID")
    client_secret = os.getenv("MICROSOFT_CLIENT_SECRET")
    tenant_id = os.getenv("MICROSOFT_TENANT_ID", "common")
    
    if not client_id or not client_secret:
        print("[MICROSOFT] Missing client credentials for token refresh")
        return None
    
    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
        "scope": "https://graph.microsoft.com/Mail.Read https://graph.microsoft.com/Mail.Send https://graph.microsoft.com/MailboxSettings.ReadWrite offline_access"
    }
    
    try:
        response = requests.post(token_url, data=data)
        response.raise_for_status()
        token_data = response.json()
        
        # Calculate expiration time
        expires_in = token_data.get("expires_in", 3600)
        import time
        token_data["expires_at"] = int(time.time()) + expires_in
        
        print(f"[MICROSOFT] ✓ Token refreshed successfully")
        return token_data
    except Exception as e:
        print(f"[MICROSOFT] ✗ Token refresh failed: {e}")
        return None


def fetch_user_emails(access_token: str, max_results: int = 50, include_spam: bool = False) -> List[Dict[str, Any]]:
    """
    Fetch emails from user's Outlook using OAuth access token.
    
    Args:
        access_token: OAuth access token from ConnectedUser.meta
        max_results: Maximum number of emails to fetch
        include_spam: If False, excludes junk folder (default: False)
        
    Returns:
        List of normalized message dicts (same format as gmail_client)
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }
    
    # Microsoft Graph API endpoint
    url = "https://graph.microsoft.com/v1.0/me/messages"
    
    # Query to exclude junk folder and deleted items (only read inbox)
    filter_query = "isDraft eq false"
    if not include_spam:
        filter_query += " and parentFolderId ne 'junkemail'"
    # Always exclude deleted items
    filter_query += " and parentFolderId ne 'deleteditems'"
    
    params = {
        "$top": max_results,
        "$filter": filter_query,
        "$orderby": "receivedDateTime desc",
        "$select": "id,subject,from,toRecipients,receivedDateTime,body,bodyPreview,hasAttachments,internetMessageHeaders"
    }
    
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.HTTPError as e:
        print(f"[MICROSOFT] Error fetching message list: {e}")
        # Re-raise 401 errors so pipeline can refresh token
        if e.response.status_code == 401:
            raise
        return []
    except requests.RequestException as e:
        print(f"[MICROSOFT] Error fetching message list: {e}")
        return []
    
    messages = []
    raw_messages = data.get("value", [])
    print(f"[MICROSOFT] Fetched {len(raw_messages)} emails from API")
    
    for item in raw_messages:
        msg = _normalize_microsoft_message(item)
        if msg:
            messages.append(msg)
            print(f"[MICROSOFT]   - From: {msg.get('sender', 'unknown')[:50]} | Subject: {msg.get('subject', '')[:50]}")
    
    return messages


def _normalize_microsoft_message(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Convert Microsoft Graph message format to our normalized schema.
    
    Microsoft Graph structure:
    {
      "id": "...",
      "subject": "...",
      "from": {"emailAddress": {"address": "...", "name": "..."}},
      "toRecipients": [{"emailAddress": {"address": "...", "name": "..."}}],
      "receivedDateTime": "2025-11-09T10:00:00Z",
      "body": {"contentType": "html", "content": "..."},
      "bodyPreview": "..."
    }
    """
    try:
        if not raw:
            print("[MICROSOFT] Error: raw message is None or empty")
            return None
        
        msg_id = raw.get("id", "")
        subject = raw.get("subject", "")
        
        # Extract sender
        from_field = raw.get("from", {})
        sender_email = from_field.get("emailAddress", {}).get("address", "")
        
        # Extract recipient
        to_recipients = raw.get("toRecipients", [])
        recipient = to_recipients[0].get("emailAddress", {}).get("address", "") if to_recipients else ""
        
        # Parse received date
        date_str = raw.get("receivedDateTime", "")
        try:
            received_at = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            received_at = datetime.utcnow()
        
        # Extract body
        body_obj = raw.get("body", {})
        body_content = body_obj.get("content", "")
        body_type = body_obj.get("contentType", "text")
        
        body_text = ""
        body_html = ""
        
        if body_type.lower() == "html":
            body_html = body_content
            # Strip HTML tags for text version
            body_text = re.sub(r'<[^>]+>', '', body_content)
        else:
            body_text = body_content
        
        # If no body, use preview
        if not body_text and not body_html:
            body_text = raw.get("bodyPreview", "")
        
        # Extract URLs from text and HTML
        urls = _extract_urls(body_text + " " + body_html)
        
        # Extract sender IP from headers
        sender_ip = None
        headers = raw.get("internetMessageHeaders", [])
        if headers:
            sender_ip = _extract_sender_ip(headers)
        
        return {
            "ext_id": msg_id,
            "subject": subject,
            "sender": sender_email,
            "recipient": recipient,
            "body_text": body_text,
            "body_html": body_html,
            "received_at": received_at,
            "urls": urls,
            "sender_ip": sender_ip,
        }
    except Exception as e:
        print(f"[MICROSOFT] Error normalizing message: {e}")
        return None


def _extract_urls(text: str) -> List[str]:
    """Extract URLs from text using regex."""
    if not text:
        return []
    
    # URL pattern (http/https)
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    urls = re.findall(url_pattern, text, re.IGNORECASE)
    
    # Deduplicate
    return list(set(urls))


def _extract_sender_ip(headers: List[Dict[str, str]]) -> Optional[str]:
    """
    Extract sender IP address from email headers.
    Aggressively extracts IPs from multiple sources to catch:
    - Hacked SMTP servers
    - Botnets
    - VPS servers
    - Spoofed headers
    - Cheap mail scripts
    
    Args:
        headers: List of header dicts with 'name' and 'value' keys
        
    Returns:
        IP address string or None
    """
    ip_pattern = r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b'
    
    # Priority 1: X-Originating-IP (webmail providers sometimes include this)
    for header in headers:
        name = header.get("name", "").lower()
        value = header.get("value", "")
        
        if name == "x-originating-ip":
            matches = re.findall(ip_pattern, value)
            if matches:
                ip = matches[0]
                if not ip.startswith(('10.', '172.', '192.168.', '127.')):
                    print(f"[MICROSOFT] ✓ Found sender IP in X-Originating-IP: {ip}")
                    return ip
    
    # Priority 2: X-Sender-IP (some mail servers use this)
    for header in headers:
        name = header.get("name", "").lower()
        value = header.get("value", "")
        
        if name == "x-sender-ip":
            matches = re.findall(ip_pattern, value)
            if matches:
                ip = matches[0]
                if not ip.startswith(('10.', '172.', '192.168.', '127.')):
                    print(f"[MICROSOFT] ✓ Found sender IP in X-Sender-IP: {ip}")
                    return ip
    
    # Priority 3: Collect ALL Received headers (in order)
    received_headers = []
    for header in headers:
        name = header.get("name", "").lower()
        value = header.get("value", "")
        
        if name == "received":
            received_headers.append(value)
    
    # Known legitimate mail server patterns (to skip)
    legitimate_patterns = [
        'outlook.com', 'protection.outlook.com', 'microsoft.com', 'office365.com',
        'google.com', 'gmail.com', 'googlemail.com',
        'yahoodns.net', 'yahoo.com',
        'protonmail.ch', 'protonmail.com',
        'icloud.com', 'apple.com'
    ]
    
    # Known attacker infrastructure patterns (to prioritize)
    suspicious_patterns = [
        'unknown', 'localhost', 'user-pc', 'desktop', 'laptop',
        'cpanel', 'plesk', 'webmail', 'mail.', 'smtp.',
        'vps', 'server', 'host', 'node', 'cloud'
    ]
    
    # Parse Received headers in REVERSE order (last = earliest hop)
    suspicious_ips = []
    legitimate_ips = []
    
    for received in reversed(received_headers):
        # Extract all IPs from this header
        matches = re.findall(ip_pattern, received)
        received_lower = received.lower()
        
        for ip in matches:
            # Skip private/local IPs
            if ip.startswith(('10.', '172.', '192.168.', '127.', '0.')):
                continue
            
            # Check if this is a legitimate mail server
            is_legitimate = any(pattern in received_lower for pattern in legitimate_patterns)
            
            # Check if this looks suspicious (hacked server, botnet, VPS)
            is_suspicious = any(pattern in received_lower for pattern in suspicious_patterns)
            
            if is_suspicious and not is_legitimate:
                # This looks like attacker infrastructure!
                print(f"[MICROSOFT] 🎯 SUSPICIOUS IP FOUND: {ip}")
                print(f"[MICROSOFT] Header: {received[:150]}...")
                suspicious_ips.append(ip)
            elif not is_legitimate:
                # Not legitimate, but not obviously suspicious either
                suspicious_ips.append(ip)
            else:
                # Legitimate mail server
                legitimate_ips.append(ip)
    
    # Return the first suspicious IP (most likely attacker)
    if suspicious_ips:
        ip = suspicious_ips[0]
        print(f"[MICROSOFT] ✓ Using suspicious IP (likely attacker): {ip}")
        return ip
    
    # Fallback: Return first legitimate IP (mail server)
    if legitimate_ips:
        ip = legitimate_ips[0]
        print(f"[MICROSOFT] ⚠️ Using mail server IP (no attacker IP found): {ip}")
        return ip
    
    print(f"[MICROSOFT] ❌ No valid IP found in headers")
    return None


def send_email(access_token: str, to_email: str, subject: str, body: str, from_email: str = None) -> bool:
    """
    Send a new email using Microsoft Graph API.
    
    Args:
        access_token: OAuth access token
        to_email: Recipient email address
        subject: Email subject
        body: Email body text
        from_email: Sender email (for display purposes, optional)
        
    Returns:
        bool: True if sent successfully
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    
    # Microsoft Graph API endpoint for sending mail
    url = "https://graph.microsoft.com/v1.0/me/sendMail"
    
    payload = {
        "message": {
            "subject": subject,
            "body": {
                "contentType": "Text",
                "content": body
            },
            "toRecipients": [
                {
                    "emailAddress": {
                        "address": to_email
                    }
                }
            ]
        },
        "saveToSentItems": "true"
    }
    
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        print(f"[MICROSOFT] ✓ Email sent to {to_email}")
        return True
    except requests.RequestException as e:
        print(f"[MICROSOFT] ✗ Error sending email: {e}")
        return False


def send_reply(access_token: str, message_id: str, reply_body: str, reply_subject: str) -> bool:
    """
    Send a reply to an Outlook email using Microsoft Graph API.
    
    Args:
        access_token: OAuth access token
        message_id: ID of the message to reply to
        reply_body: Reply body text
        reply_subject: Reply subject
        
    Returns:
        bool: True if sent successfully
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    
    # Microsoft Graph API endpoint for reply
    url = f"https://graph.microsoft.com/v1.0/me/messages/{message_id}/reply"
    
    # According to Microsoft Graph API docs, reply only needs comment field
    payload = {
        "comment": reply_body
    }
    
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        print(f"[MICROSOFT] ✓ Reply sent for message {message_id}")
        return True
    except requests.RequestException as e:
        print(f"[MICROSOFT] ✗ Error sending reply: {e}")
        return False
