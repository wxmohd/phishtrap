#!/usr/bin/env python3
"""
Remove duplicate links from the database.
Keeps the first occurrence of each (email_id, url) pair and deletes the rest.
"""

from database.models import SessionLocal, Link
from sqlalchemy import select, func

def remove_duplicates():
    """Remove duplicate links, keeping only the first occurrence."""
    with SessionLocal() as session:
        # Find all duplicate groups
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
        
        print(f"⚠️ Found {len(duplicates)} duplicate link groups")
        print("Removing duplicates (keeping first occurrence)...")
        print()
        
        total_removed = 0
        
        for email_id, url, count in duplicates:
            # Get all links for this (email_id, url) pair
            links = session.execute(
                select(Link)
                .where(Link.email_id == email_id, Link.url == url)
                .order_by(Link.id)
            ).scalars().all()
            
            # Keep the first one, delete the rest
            for link in links[1:]:
                session.delete(link)
                total_removed += 1
                print(f"  ✗ Deleted duplicate link #{link.id}: {url[:60]}")
        
        session.commit()
        print()
        print(f"✅ Removed {total_removed} duplicate link entries!")

if __name__ == "__main__":
    confirm = input("This will delete duplicate links. Continue? (yes/no): ")
    if confirm.lower() == 'yes':
        remove_duplicates()
    else:
        print("Cancelled.")
