#!/usr/bin/env python3
"""
Clean up duplicate sender intelligence records.
Keeps only the most recent record for each email.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.models import SessionLocal, SenderIntelligence
from sqlalchemy import func, select

def cleanup_duplicates():
    """Remove duplicate sender intelligence records."""
    print("🧹 Cleaning up duplicate sender intelligence records...")
    print()
    
    with SessionLocal() as session:
        # Find email_ids with multiple intelligence records
        duplicates = session.execute(
            select(SenderIntelligence.email_id, func.count(SenderIntelligence.id).label('count'))
            .group_by(SenderIntelligence.email_id)
            .having(func.count(SenderIntelligence.id) > 1)
        ).all()
        
        if not duplicates:
            print("✅ No duplicates found!")
            return
        
        print(f"📧 Found {len(duplicates)} emails with duplicate intelligence records")
        print()
        
        total_deleted = 0
        
        for email_id, count in duplicates:
            print(f"Email ID {email_id}: {count} records")
            
            # Get all records for this email, ordered by analyzed_at desc
            records = session.execute(
                select(SenderIntelligence)
                .where(SenderIntelligence.email_id == email_id)
                .order_by(SenderIntelligence.analyzed_at.desc())
            ).scalars().all()
            
            # Keep the first (most recent), delete the rest
            to_delete = records[1:]
            
            for record in to_delete:
                session.delete(record)
                total_deleted += 1
            
            print(f"  ✓ Kept most recent, deleted {len(to_delete)} old record(s)")
        
        session.commit()
        
        print()
        print("=" * 60)
        print("📊 Summary:")
        print(f"  ✓ Deleted: {total_deleted} duplicate records")
        print(f"  📧 Cleaned: {len(duplicates)} emails")
        print("=" * 60)
        print()
        print("✅ Cleanup complete!")

if __name__ == "__main__":
    try:
        cleanup_duplicates()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
