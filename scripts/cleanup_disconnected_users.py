#!/usr/bin/env python3
"""
Clean up emails and data from disconnected or deleted users.
Run this after manually deleting users from the database.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database.models import SessionLocal, Email, ConnectedUser, Blocklist
from sqlalchemy import select

def cleanup_orphaned_data():
    """Remove emails and blocklist entries for users no longer in the database."""
    
    with SessionLocal() as session:
        # Get all active user emails
        active_users = session.query(ConnectedUser.email).filter(
            ConnectedUser.revoked_at.is_(None)
        ).all()
        active_emails = {user.email for user in active_users}
        
        print(f"📧 Active users: {', '.join(active_emails) if active_emails else 'None'}")
        print()
        
        # Find emails from disconnected users
        all_emails = session.query(Email.recipient).distinct().all()
        orphaned_recipients = {email.recipient for email in all_emails if email.recipient not in active_emails}
        
        if not orphaned_recipients:
            print("✅ No orphaned data found. All emails belong to active users.")
            return
        
        print(f"🗑️  Found emails from disconnected users: {', '.join(orphaned_recipients)}")
        print()
        
        # Count what will be deleted
        for recipient in orphaned_recipients:
            email_count = session.query(Email).filter(Email.recipient == recipient).count()
            blocklist_count = session.query(Blocklist).filter(
                Blocklist.recipient_email == recipient,
                Blocklist.is_global == False
            ).count()
            
            print(f"  {recipient}:")
            print(f"    - {email_count} emails")
            print(f"    - {blocklist_count} blocklist entries")
        
        print()
        confirm = input("Delete all this data? [y/N]: ")
        
        if confirm.lower() != 'y':
            print("❌ Cancelled")
            return
        
        # Delete orphaned data
        total_emails = 0
        total_blocklist = 0
        
        for recipient in orphaned_recipients:
            deleted_emails = session.query(Email).filter(Email.recipient == recipient).delete()
            deleted_blocklist = session.query(Blocklist).filter(
                Blocklist.recipient_email == recipient,
                Blocklist.is_global == False
            ).delete()
            
            total_emails += deleted_emails
            total_blocklist += deleted_blocklist
        
        session.commit()
        
        print()
        print("✅ Cleanup complete!")
        print(f"   Deleted {total_emails} emails")
        print(f"   Deleted {total_blocklist} blocklist entries")

def cleanup_specific_user(email):
    """Remove all data for a specific user email."""
    
    with SessionLocal() as session:
        # Check if user exists
        user = session.query(ConnectedUser).filter(ConnectedUser.email == email).first()
        
        if user and user.revoked_at is None:
            print(f"⚠️  User {email} is still active!")
            print("   Use the dashboard 'Revoke' button or delete from database first.")
            return
        
        # Count data
        email_count = session.query(Email).filter(Email.recipient == email).count()
        blocklist_count = session.query(Blocklist).filter(
            Blocklist.recipient_email == email,
            Blocklist.is_global == False
        ).count()
        
        if email_count == 0 and blocklist_count == 0:
            print(f"✅ No data found for {email}")
            return
        
        print(f"🗑️  Found data for {email}:")
        print(f"   - {email_count} emails")
        print(f"   - {blocklist_count} blocklist entries")
        print()
        
        confirm = input(f"Delete all data for {email}? [y/N]: ")
        
        if confirm.lower() != 'y':
            print("❌ Cancelled")
            return
        
        # Delete data
        deleted_emails = session.query(Email).filter(Email.recipient == email).delete()
        deleted_blocklist = session.query(Blocklist).filter(
            Blocklist.recipient_email == email,
            Blocklist.is_global == False
        ).delete()
        
        session.commit()
        
        print()
        print("✅ Cleanup complete!")
        print(f"   Deleted {deleted_emails} emails")
        print(f"   Deleted {deleted_blocklist} blocklist entries")

def main():
    print("🧹 PhishTrap Data Cleanup Tool")
    print("=" * 60)
    print()
    
    if len(sys.argv) > 1:
        # Clean up specific user
        email = sys.argv[1]
        cleanup_specific_user(email)
    else:
        # Clean up all orphaned data
        cleanup_orphaned_data()

if __name__ == "__main__":
    main()
