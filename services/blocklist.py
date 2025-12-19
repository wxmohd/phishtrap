"""
Blocklist management service.
Handles checking, adding, and removing blocklisted senders.
"""
from typing import Optional
from sqlalchemy import select, or_
from database.models import SessionLocal, Blocklist, ConnectedUser
from datetime import datetime
import json


def is_blocked(sender: str, recipient: str) -> bool:
    """
    Check if a sender is blocklisted for a specific recipient.
    
    Args:
        sender: Email address of sender
        recipient: Email address of recipient
        
    Returns:
        bool: True if sender is blocked
    """
    with SessionLocal() as session:
        # Check exact email match (per-user or global)
        exact_match = session.execute(
            select(Blocklist).where(
                Blocklist.blocked_sender == sender,
                or_(
                    Blocklist.recipient_email == recipient,
                    Blocklist.is_global == True
                )
            )
        ).scalar_one_or_none()
        
        if exact_match:
            return True
        
        # Check domain match (@domain.com)
        sender_domain = '@' + sender.split('@')[1] if '@' in sender else None
        if sender_domain:
            domain_match = session.execute(
                select(Blocklist).where(
                    Blocklist.blocked_sender == sender_domain,
                    Blocklist.is_domain == True,
                    or_(
                        Blocklist.recipient_email == recipient,
                        Blocklist.is_global == True
                    )
                )
            ).scalar_one_or_none()
            
            if domain_match:
                return True
        
        return False


def add_to_blocklist(
    sender: str,
    recipient: Optional[str] = None,
    reason: Optional[str] = None,
    blocked_by: Optional[str] = None,
    is_global: bool = False
) -> bool:
    """
    Add a sender to the blocklist.
    
    Args:
        sender: Email address or domain to block (e.g., abc@gmail.com or @evil.com)
        recipient: Recipient email (None for global block)
        reason: Reason for blocking
        blocked_by: Admin who blocked
        is_global: True for global block
        
    Returns:
        bool: True if added successfully
    """
    is_domain = sender.startswith('@')
    
    with SessionLocal() as session:
        # Check if already exists
        existing = session.execute(
            select(Blocklist).where(
                Blocklist.blocked_sender == sender,
                Blocklist.recipient_email == recipient
            )
        ).scalar_one_or_none()
        
        if existing:
            print(f"[BLOCKLIST] Already exists: {sender} for {recipient or 'global'}")
            return False
        
        # Add new blocklist entry
        entry = Blocklist(
            recipient_email=recipient if not is_global else None,
            blocked_sender=sender,
            blocked_at=datetime.utcnow(),
            blocked_by=blocked_by,
            reason=reason,
            is_domain=is_domain,
            is_global=is_global
        )
        session.add(entry)
        session.commit()
        
        print(f"[BLOCKLIST] ✓ Added: {sender} for {recipient or 'global'}")
        
        # Sync to Outlook if this is for a Microsoft account
        _sync_to_outlook(sender, recipient, is_global, action='add')
        
        return True


def remove_from_blocklist(blocklist_id: int) -> bool:
    """
    Remove an entry from the blocklist.
    Also updates any emails from this sender to clear blocked status.
    
    Args:
        blocklist_id: ID of blocklist entry
        
    Returns:
        bool: True if removed successfully
    """
    from database.models import Email
    
    with SessionLocal() as session:
        entry = session.get(Blocklist, blocklist_id)
        if entry:
            sender = entry.blocked_sender
            recipient = entry.recipient_email
            is_global = entry.is_global
            
            # Delete blocklist entry
            session.delete(entry)
            session.commit()
            print(f"[BLOCKLIST] ✓ Removed: {sender}")
            
            # Update emails from this sender - just unblock them
            if not sender.startswith('@'):  # Only for specific email addresses, not domains
                emails_to_update = session.execute(
                    select(Email).where(
                        Email.sender == sender,
                        Email.blocked == True
                    )
                ).scalars().all()
                
                for email in emails_to_update:
                    # Just mark as unblocked - keep original classification
                    email.blocked = False
                
                if emails_to_update:
                    session.commit()
                    print(f"[BLOCKLIST] ℹ️ Unblocked {len(emails_to_update)} emails from {sender}")
                else:
                    print(f"[BLOCKLIST] ℹ️ No blocked emails found for {sender}")
            
            # Sync to Outlook
            _sync_to_outlook(sender, recipient, is_global, action='remove')
            
            return True
        return False


def get_blocklist(recipient: Optional[str] = None):
    """
    Get blocklist entries.
    
    Args:
        recipient: Filter by recipient (None for all)
        
    Returns:
        List of Blocklist entries
    """
    with SessionLocal() as session:
        if recipient:
            entries = session.execute(
                select(Blocklist).where(
                    or_(
                        Blocklist.recipient_email == recipient,
                        Blocklist.is_global == True
                    )
                ).order_by(Blocklist.blocked_at.desc())
            ).scalars().all()
        else:
            entries = session.execute(
                select(Blocklist).order_by(Blocklist.blocked_at.desc())
            ).scalars().all()
        
        return entries


def _sync_to_outlook(sender: str, recipient: Optional[str], is_global: bool, action: str):
    """
    Sync blocklist change to Outlook accounts.
    
    Args:
        sender: Email address to block/unblock
        recipient: Specific recipient (None if global)
        is_global: True if global block
        action: 'add' or 'remove'
    """
    from services.outlook_blocklist_sync import sync_blocklist_to_outlook
    
    # Skip domain blocks (Outlook doesn't support domain-level blocks via API)
    if sender.startswith('@'):
        print(f"[BLOCKLIST] ℹ️ Skipping Outlook sync for domain block: {sender}")
        return
    
    with SessionLocal() as session:
        # Get affected users
        if is_global:
            # Sync to all Microsoft accounts
            users = session.execute(
                select(ConnectedUser).where(
                    ConnectedUser.provider == 'microsoft',
                    ConnectedUser.revoked_at.is_(None)
                )
            ).scalars().all()
        elif recipient:
            # Sync to specific recipient
            users = session.execute(
                select(ConnectedUser).where(
                    ConnectedUser.email == recipient,
                    ConnectedUser.provider == 'microsoft',
                    ConnectedUser.revoked_at.is_(None)
                )
            ).scalars().all()
        else:
            users = []
        
        # Sync to each user's Outlook
        for user in users:
            try:
                token_data = json.loads(user.meta or "{}")
                access_token = token_data.get("access_token")
                
                if access_token:
                    success = sync_blocklist_to_outlook(access_token, sender, action)
                    if success:
                        print(f"[BLOCKLIST] ✓ Synced {action} for {sender} to {user.email}'s Outlook")
                    else:
                        print(f"[BLOCKLIST] ✗ Failed to sync {action} for {sender} to {user.email}'s Outlook")
                else:
                    print(f"[BLOCKLIST] ⚠️ No access token for {user.email}")
                    
            except Exception as e:
                print(f"[BLOCKLIST] ✗ Error syncing to {user.email}: {e}")
