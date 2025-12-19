#!/usr/bin/env python3
"""
Re-classify existing emails with updated AI classifier.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.models import SessionLocal, Email, Link
from services.ai_classifier import classify_email

def reclassify_all():
    """Re-classify all emails with updated AI."""
    print("🤖 Re-classifying emails with enhanced AI...")
    print()
    
    with SessionLocal() as session:
        emails = session.query(Email).filter(
            Email.ai_label.in_(['legit', 'suspicious', 'phishing'])
        ).all()
        
        total = len(emails)
        if total == 0:
            print("❌ No emails to re-classify")
            return
        
        print(f"📧 Found {total} emails to re-classify")
        print()
        
        updated = 0
        unchanged = 0
        
        for i, email in enumerate(emails, 1):
            old_label = email.ai_label
            old_score = email.ai_score
            
            # Get URLs for this email
            links = session.query(Link).filter_by(email_id=email.id).all()
            urls = [link.url for link in links]
            
            # Re-classify
            result = classify_email(email.subject, email.body_text, urls)
            
            new_label = result['label']
            new_score = round(result['score'] * 100, 1)
            
            if new_label != old_label or abs(new_score - old_score) > 0.1:
                print(f"[{i}/{total}] Email ID {email.id}")
                print(f"  Subject: {email.subject[:60]}...")
                print(f"  Old: {old_label.upper()} {old_score}%")
                print(f"  New: {new_label.upper()} {new_score}%")
                print(f"  Reason: {result['explanation']}")
                print()
                
                # Update
                email.ai_label = new_label
                email.ai_score = new_score
                email.ai_explanation = result['explanation']
                
                updated += 1
            else:
                unchanged += 1
        
        session.commit()
        
        print("=" * 60)
        print("📊 Summary:")
        print(f"  ✓ Updated: {updated}")
        print(f"  ⏭️  Unchanged: {unchanged}")
        print(f"  📧 Total: {total}")
        print("=" * 60)
        print()
        print("✅ Re-classification complete!")

if __name__ == "__main__":
    try:
        reclassify_all()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
