#!/usr/bin/env python3
"""
Re-analyze existing links with updated risk scoring logic
"""
from database.models import SessionLocal, Link
from services.link_analyzer import analyze_link

def main():
    with SessionLocal() as session:
        # Get all analyzed links that redirect to legit
        links = session.query(Link).filter(
            Link.analysis_complete == True
        ).all()
        
        print(f"[REANALYZE] Found {len(links)} links to re-analyze")
        
        updated = 0
        for link in links:
            try:
                # Re-analyze with new logic
                analyze_link(link, session)
                updated += 1
                print(f"[REANALYZE] ✓ Updated Link #{link.id}: {link.risk_level} ({link.risk_score})")
            except Exception as e:
                print(f"[REANALYZE] ✗ Failed Link #{link.id}: {e}")
        
        print(f"\n[REANALYZE] ✅ Re-analyzed {updated}/{len(links)} links")

if __name__ == "__main__":
    main()
