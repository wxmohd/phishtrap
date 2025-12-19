#!/usr/bin/env python3
"""
Check for and optionally remove duplicate links in the database.
Run this to see if there are duplicate URL entries for the same email.
"""

from database.models import SessionLocal, Link, Email
from sqlalchemy import select, func

def check_duplicates():
    """Check for duplicate links in the database."""
    with SessionLocal() as session:
        # Find duplicate links (same email_id + url)
        duplicates = session.execute(
            select(
                Link.email_id,
                Link.url,
                func.count(Link.id).label('count')
            )
            .group_by(Link.email_id, Link.url)
            .having(func.count(Link.id) > 1)
        ).all()
        
        if not duplicates:
            print("✅ No duplicate links found!")
            return
        
        print(f"⚠️ Found {len(duplicates)} duplicate link entries:")
        print()
        
        total_duplicates = 0
        for email_id, url, count in duplicates:
            # Get email subject
            email = session.get(Email, email_id)
            subject = email.subject[:50] if email else "Unknown"
            
            print(f"  Email #{email_id}: {subject}")
            print(f"  URL: {url[:80]}")
            print(f"  Count: {count} (should be 1)")
            print()
            
            total_duplicates += (count - 1)
        
        print(f"Total extra duplicate entries: {total_duplicates}")
        print()
        print("To remove duplicates, run: python3 remove_duplicate_links.py")

if __name__ == "__main__":
    check_duplicates()
