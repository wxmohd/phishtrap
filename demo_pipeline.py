#!/usr/bin/env python3
"""
Demo script to show the email processing pipeline with detailed logging.
Perfect for documentation screenshots.

Pipeline: Fetch → Parse → Store → Classify → Extract URLs → Enrichment
"""

import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from database.models import SessionLocal, Email, Link, ConnectedUser
from sqlalchemy import select

def print_header(text):
    """Print a fancy header."""
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80 + "\n")

def print_step(step_num, step_name, status="IN PROGRESS"):
    """Print a pipeline step."""
    emoji = "⚡" if status == "IN PROGRESS" else "✓" if status == "COMPLETE" else "⚠️"
    print(f"\n{emoji} STEP {step_num}: {step_name} [{status}]")
    print("-" * 80)

def demo_pipeline():
    """Demonstrate the email processing pipeline."""
    
    print_header("📧 PhishTrap Email Processing Pipeline Demo")
    
    with SessionLocal() as session:
        # Get a sample email from database
        email = session.execute(
            select(Email).order_by(Email.received_at.desc()).limit(1)
        ).scalar_one_or_none()
        
        if not email:
            print("❌ No emails found in database. Please sync some emails first.")
            print("\nRun: python3 -c \"from services.pipeline import sync_from_mailhog; sync_from_mailhog()\"")
            return
        
        # STEP 1: FETCH
        print_step(1, "FETCH EMAIL", "COMPLETE")
        print(f"  Provider: {email.recipient.split('@')[1] if '@' in email.recipient else 'Unknown'}")
        print(f"  Recipient: {email.recipient}")
        print(f"  Message ID: {email.ext_id or 'N/A'}")
        print(f"  Received: {email.received_at.strftime('%Y-%m-%d %H:%M:%S') if email.received_at else 'N/A'}")
        
        # STEP 2: PARSE
        print_step(2, "PARSE EMAIL CONTENT", "COMPLETE")
        print(f"  From: {email.sender}")
        print(f"  Subject: {email.subject[:60]}{'...' if len(email.subject) > 60 else ''}")
        body = email.body_text or email.body_html or ''
        print(f"  Body Length: {len(body)} characters")
        print(f"  Body Preview: {body[:100]}...")
        
        # STEP 3: STORE
        print_step(3, "STORE IN DATABASE", "COMPLETE")
        print(f"  Email ID: #{email.id}")
        print(f"  Table: emails")
        print(f"  Stored At: {email.received_at.strftime('%Y-%m-%d %H:%M:%S') if email.received_at else 'N/A'}")
        
        # STEP 4: CLASSIFY
        print_step(4, "AI CLASSIFICATION", "COMPLETE")
        print(f"  Classification: {email.ai_label.upper() if email.ai_label else 'UNKNOWN'}")
        print(f"  Confidence: {email.ai_score * 100:.1f}%" if email.ai_score else "  Confidence: N/A")
        print(f"  Method: Heuristic-based (keyword analysis, URL patterns, brand spoofing)")
        print(f"  Explanation: {email.ai_explanation or 'N/A'}")
        
        if email.ai_label in ['suspicious', 'phishing']:
            print(f"  ⚠️  Review Status: {email.review_status or 'N/A'}")
        
        # STEP 5: EXTRACT URLs
        print_step(5, "EXTRACT & ANALYZE URLs", "COMPLETE")
        links = session.execute(
            select(Link).where(Link.email_id == email.id)
        ).scalars().all()
        
        if links:
            print(f"  URLs Found: {len(links)}")
            for i, link in enumerate(links[:3], 1):  # Show first 3
                print(f"\n  URL #{i}:")
                print(f"    • {link.url[:70]}{'...' if len(link.url) > 70 else ''}")
                print(f"    • Status: {link.status or 'pending'}")
                if link.risk_level:
                    print(f"    • Risk: {link.risk_level.upper()} ({link.risk_score}/100)")
                if link.impersonated_brand:
                    print(f"    • Brand: {link.impersonated_brand}")
                if link.country_code:
                    print(f"    • Location: {link.country_flag or ''} {link.country_code}")
            
            if len(links) > 3:
                print(f"\n  ... and {len(links) - 3} more URLs")
        else:
            print("  URLs Found: 0")
            print("  No links detected in email body")
        
        # STEP 6: ENRICHMENT (Optional)
        print_step(6, "SENDER INTELLIGENCE ENRICHMENT", "COMPLETE")
        
        # Check if sender intelligence exists
        from database.models import SenderIntelligence
        sender_intel = session.execute(
            select(SenderIntelligence).where(SenderIntelligence.email_id == email.id)
        ).scalar_one_or_none()
        
        if sender_intel:
            print(f"  Sender IP: {sender_intel.sender_ip or 'N/A'}")
            if sender_intel.country:
                print(f"  Location: {sender_intel.country}")
            if sender_intel.country_code:
                print(f"  Country Code: {sender_intel.country_code}")
            if sender_intel.asn:
                print(f"  ASN: {sender_intel.asn}")
            if sender_intel.org:
                print(f"  Organization: {sender_intel.org}")
            if sender_intel.isp:
                print(f"  ISP: {sender_intel.isp}")
            
            # Threat indicators
            threats = []
            if sender_intel.is_vpn:
                threats.append("VPN")
            if sender_intel.is_proxy:
                threats.append("Proxy")
            if sender_intel.is_tor:
                threats.append("Tor")
            if sender_intel.is_hosting:
                threats.append("Hosting Provider")
            
            if threats:
                print(f"  ⚠️  Threat Indicators: {', '.join(threats)}")
            
            if sender_intel.abuse_confidence_score:
                print(f"  Abuse Score: {sender_intel.abuse_confidence_score}/100")
        else:
            print("  Status: Not enriched (optional step)")
            print("  Note: Sender intelligence can be fetched on-demand")
        
        # FINAL SUMMARY
        print_header("📊 Pipeline Summary")
        print(f"  Total Processing Time: ~2-5 seconds")
        print(f"  Email Status: {email.ai_label.upper() if email.ai_label else 'PROCESSED'}")
        print(f"  Action Taken: {'Pending Admin Review' if email.review_status == 'pending_review' else 'Auto-processed'}")
        print(f"  URLs Analyzed: {len(links)}")
        print(f"  Enrichment: {'Complete' if sender_intel else 'Skipped'}")
        
        print("\n" + "=" * 80)
        print("  ✅ Pipeline demonstration complete!")
        print("=" * 80 + "\n")

if __name__ == "__main__":
    try:
        demo_pipeline()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
