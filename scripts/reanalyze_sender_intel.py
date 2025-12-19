#!/usr/bin/env python3
"""
Re-analyze Sender Intelligence for Existing Emails
This script re-runs sender intelligence analysis to populate missing WHOIS/domain data.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.models import SessionLocal, Email, SenderIntelligence
from services.sender_intel import analyze_sender

def reanalyze_all():
    """Re-analyze all emails to populate sender intelligence."""
    print("🔍 Re-analyzing sender intelligence for all emails...")
    print()
    
    with SessionLocal() as session:
        # Get all emails
        emails = session.query(Email).all()
        total = len(emails)
        
        if total == 0:
            print("❌ No emails found in database")
            return
        
        print(f"📧 Found {total} emails to analyze")
        print()
        
        success_count = 0
        skip_count = 0
        error_count = 0
        
        for i, email in enumerate(emails, 1):
            print(f"[{i}/{total}] Email ID {email.id} from {email.sender}...")
            
            try:
                # Delete old intelligence record
                old_intel = session.query(SenderIntelligence).filter_by(email_id=email.id).first()
                if old_intel:
                    session.delete(old_intel)
                    session.flush()
                
                # Re-analyze
                intel = analyze_sender(email, session)
                
                if intel:
                    success_count += 1
                    print(f"  ✓ Analysis complete")
                    if intel.sender_domain:
                        print(f"    Domain: {intel.sender_domain}")
                    if intel.domain_age_days:
                        print(f"    Domain Age: {intel.domain_age_days} days")
                    if intel.domain_registrar:
                        print(f"    Registrar: {intel.domain_registrar}")
                else:
                    skip_count += 1
                    print(f"  ⏭️  Skipped (no IP or domain)")
                
            except Exception as e:
                error_count += 1
                print(f"  ❌ Error: {e}")
            
            print()
        
        # Commit all changes
        session.commit()
        
        print("=" * 60)
        print("📊 Summary:")
        print(f"  ✓ Successfully analyzed: {success_count}")
        print(f"  ⏭️  Skipped: {skip_count}")
        print(f"  ❌ Errors: {error_count}")
        print(f"  📧 Total: {total}")
        print("=" * 60)
        print()
        print("✅ Re-analysis complete!")
        print()
        print("🎯 Next steps:")
        print("  1. Refresh your dashboard to see updated intelligence")
        print("  2. Send a new test email to verify WHOIS data is captured")
        print("  3. Check sender intelligence page for domain details")

if __name__ == "__main__":
    try:
        reanalyze_all()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        sys.exit(1)
