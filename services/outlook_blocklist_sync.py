"""
Sync PhishTrap blocklist with Outlook junk email rules.
Uses Microsoft Graph API to add/remove blocked senders.
"""
import requests
import json
from typing import Optional


def add_to_outlook_blocklist(access_token: str, sender_email: str) -> bool:
    """
    Add sender to Outlook's blocked senders list via Microsoft Graph API.
    Creates an inbox rule to automatically delete emails from this sender.
    
    Args:
        access_token: OAuth access token for Microsoft Graph
        sender_email: Email address to block
        
    Returns:
        bool: True if successful
    """
    url = "https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messageRules"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # Create inbox rule to delete emails from this sender
    rule_name = f"PhishTrap Block: {sender_email}"
    payload = {
        "displayName": rule_name,
        "sequence": 1,
        "isEnabled": True,
        "conditions": {
            "fromAddresses": [
                {
                    "emailAddress": {
                        "address": sender_email
                    }
                }
            ]
        },
        "actions": {
            "delete": True,
            "stopProcessingRules": True
        }
    }
    
    try:
        print(f"[OUTLOOK_BLOCKLIST] Creating inbox rule for {sender_email}...")
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code in [200, 201]:
            rule_data = response.json()
            rule_id = rule_data.get('id', 'unknown')
            print(f"[OUTLOOK_BLOCKLIST] ✓ Added {sender_email} to Outlook blocklist (inbox rule)")
            print(f"[OUTLOOK_BLOCKLIST] Rule ID: {rule_id}")
            print(f"[OUTLOOK_BLOCKLIST] Check: Outlook → Settings → Mail → Rules")
            return True
        else:
            print(f"[OUTLOOK_BLOCKLIST] ✗ Failed to add {sender_email}: {response.status_code}")
            print(f"[OUTLOOK_BLOCKLIST] Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"[OUTLOOK_BLOCKLIST] ✗ Error adding {sender_email}: {e}")
        return False


def remove_from_outlook_blocklist(access_token: str, sender_email: str) -> bool:
    """
    Remove sender from Outlook's blocked senders list via Microsoft Graph API.
    Deletes the inbox rule that blocks this sender.
    
    Args:
        access_token: OAuth access token for Microsoft Graph
        sender_email: Email address to unblock
        
    Returns:
        bool: True if successful
    """
    # Get all inbox rules
    get_url = "https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messageRules"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    try:
        # Get all rules
        response = requests.get(get_url, headers=headers)
        
        if response.status_code != 200:
            print(f"[OUTLOOK_BLOCKLIST] ✗ Failed to get inbox rules: {response.status_code}")
            return False
        
        data = response.json()
        rules = data.get("value", [])
        
        # Find rule for this sender
        rule_id = None
        rule_name = f"PhishTrap Block: {sender_email}"
        for rule in rules:
            if rule.get("displayName") == rule_name:
                rule_id = rule.get("id")
                break
        
        if not rule_id:
            print(f"[OUTLOOK_BLOCKLIST] ℹ️ {sender_email} not found in Outlook blocklist")
            return True
        
        # Delete the rule
        delete_url = f"{get_url}/{rule_id}"
        response = requests.delete(delete_url, headers=headers)
        
        if response.status_code in [200, 204]:
            print(f"[OUTLOOK_BLOCKLIST] ✓ Removed {sender_email} from Outlook blocklist")
            return True
        else:
            print(f"[OUTLOOK_BLOCKLIST] ✗ Failed to remove {sender_email}: {response.status_code}")
            print(f"[OUTLOOK_BLOCKLIST] Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"[OUTLOOK_BLOCKLIST] ✗ Error removing {sender_email}: {e}")
        return False


def sync_blocklist_to_outlook(access_token: str, sender_email: str, action: str) -> bool:
    """
    Sync a blocklist change to Outlook.
    
    Args:
        access_token: OAuth access token
        sender_email: Email to block/unblock
        action: 'add' or 'remove'
        
    Returns:
        bool: True if successful
    """
    if action == 'add':
        return add_to_outlook_blocklist(access_token, sender_email)
    elif action == 'remove':
        return remove_from_outlook_blocklist(access_token, sender_email)
    else:
        print(f"[OUTLOOK_BLOCKLIST] ✗ Invalid action: {action}")
        return False
