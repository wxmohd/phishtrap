#!/usr/bin/env python3
"""
Clear all emails and links from the database for a fresh start.
Keeps connected users intact.
"""

from database.models import SessionLocal, Email, Link, SenderIntelligence

def clear_all_data():
    """Delete all emails, links, and sender intelligence."""
    with SessionLocal() as session:
        # Delete sender intelligence first (foreign key constraint)
        deleted_intel = session.query(SenderIntelligence).delete()
        print(f"✓ Deleted {deleted_intel} sender intelligence records")
        
        # Delete all links
        deleted_links = session.query(Link).delete()
        print(f"✓ Deleted {deleted_links} links")
        
        # Delete all emails
        deleted_emails = session.query(Email).delete()
        print(f"✓ Deleted {deleted_emails} emails")
        
        session.commit()
        print("\n🎉 Database cleared! Fresh start ready.")
        print("\nConnected users are still intact.")
        print("New emails will be imported on next sync.")

if __name__ == "__main__":
    print("⚠️  WARNING: This will delete ALL emails, links, and sender intelligence!")
    print("Connected users will remain intact.\n")
    
    confirm = input("Are you sure? Type 'yes' to confirm: ")
    if confirm.lower() == 'yes':
        clear_all_data()
    else:
        print("❌ Cancelled")
