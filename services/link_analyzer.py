"""
Link Analyzer - Automated URL Intelligence Gathering
Visits suspicious links in a sandbox, extracts threat intelligence, and stores rich metadata.
"""

import re
import json
import socket
import requests
from datetime import datetime
from urllib.parse import urlparse
from typing import Dict, Optional, List
import hashlib

# Brand detection patterns
BRAND_PATTERNS = {
    'Microsoft': ['microsoft', 'outlook', 'office365', 'azure', 'onedrive', 'teams'],
    'PayPal': ['paypal', 'pp-'],
    'Amazon': ['amazon', 'aws', 'amzn'],
    'Apple': ['apple', 'icloud', 'itunes'],
    'Google': ['google', 'gmail', 'drive'],
    'Facebook': ['facebook', 'fb', 'meta'],
    'Bank': ['bank', 'banking', 'chase', 'wellsfargo', 'bofa', 'citibank'],
    'DHL': ['dhl', 'delivery'],
    'FedEx': ['fedex', 'shipping'],
    'Netflix': ['netflix', 'streaming'],
}

# Suspicious keywords for credential harvesting
CREDENTIAL_HARVEST_KEYWORDS = [
    'login', 'signin', 'verify', 'confirm', 'update', 'secure',
    'account', 'password', 'credential', 'auth', 'validate'
]

# File download indicators
DOWNLOAD_INDICATORS = [
    '.exe', '.zip', '.rar', '.pdf', '.doc', '.docx', '.xls', '.xlsx',
    'download', 'attachment', 'file'
]

# Country code to flag emoji mapping
COUNTRY_FLAGS = {
    'US': '🇺🇸', 'RU': '🇷🇺', 'CN': '🇨🇳', 'NL': '🇳🇱', 'DE': '🇩🇪',
    'GB': '🇬🇧', 'FR': '🇫🇷', 'BR': '🇧🇷', 'IN': '🇮🇳', 'CA': '🇨🇦',
    'AU': '🇦🇺', 'JP': '🇯🇵', 'KR': '🇰🇷', 'IT': '🇮🇹', 'ES': '🇪🇸',
}


def calculate_risk_score(url: str, analysis_data: Dict) -> int:
    """Calculate risk score 0-100 based on multiple factors."""
    score = 0
    
    # If redirects to legitimate domain, it's likely a tracking/marketing link
    if analysis_data.get('redirects_to_legit'):
        # Very low risk - legitimate redirect (e.g., go.microsoft.com → microsoft.com)
        return 10
    
    # Base score for suspicious URL
    score += 30
    
    # Brand impersonation
    if analysis_data.get('impersonated_brand') and analysis_data['impersonated_brand'] != 'Generic':
        score += 25
    
    # Credential harvesting indicators
    if analysis_data.get('credential_harvest'):
        score += 20
    
    # Multiple redirects (obfuscation)
    redirect_count = analysis_data.get('redirect_count', 0)
    if redirect_count > 2:
        score += 15
    elif redirect_count > 0:
        score += 10
    
    # Suspicious TLD
    parsed = urlparse(url)
    suspicious_tlds = ['.tk', '.ml', '.ga', '.cf', '.gq', '.xyz', '.top']
    if any(parsed.netloc.endswith(tld) for tld in suspicious_tlds):
        score += 10
    
    # File download
    if analysis_data.get('downloads_file'):
        score += 15
    
    return min(score, 100)


def detect_brand(url: str, page_content: Optional[str] = None) -> str:
    """Detect which brand is being impersonated."""
    url_lower = url.lower()
    
    for brand, keywords in BRAND_PATTERNS.items():
        for keyword in keywords:
            if keyword in url_lower:
                return brand
            if page_content and keyword in page_content.lower():
                return brand
    
    return 'Generic'


def get_country_from_ip(ip: str) -> tuple:
    """Get country code and flag from IP address."""
    try:
        # Use ip-api.com for geolocation (free, no key required)
        response = requests.get(f'http://ip-api.com/json/{ip}', timeout=5)
        if response.status_code == 200:
            data = response.json()
            country_code = data.get('countryCode', 'XX')
            flag = COUNTRY_FLAGS.get(country_code, '🏳️')
            return country_code, flag
    except Exception as e:
        print(f"[LINK_ANALYZER] ⚠️ Geolocation failed for {ip}: {e}")
    
    return 'XX', '🏳️'


def resolve_ip(url: str) -> Optional[str]:
    """Resolve domain to IP address."""
    try:
        parsed = urlparse(url)
        hostname = parsed.netloc.split(':')[0]  # Remove port if present
        ip = socket.gethostbyname(hostname)
        return ip
    except Exception as e:
        print(f"[LINK_ANALYZER] ⚠️ IP resolution failed: {e}")
        return None


def analyze_url_sandbox(url: str, timeout: int = 10) -> Dict:
    """
    Visit URL in a safe sandbox environment and extract intelligence.
    Uses HTTP requests (not full browser) for safety.
    """
    analysis = {
        'credential_harvest': False,
        'downloads_file': False,
        'redirects_to_legit': False,
        'redirect_chain': [],
        'redirect_count': 0,
        'final_url': url,
        'page_title': None,
        'status_code': None,
        'error': None,
    }
    
    try:
        print(f"[LINK_ANALYZER] 🔍 Analyzing: {url[:60]}...")
        
        # Follow redirects and track chain
        session = requests.Session()
        session.max_redirects = 10
        
        # Use a realistic user agent
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = session.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        
        # Track redirect chain
        if response.history:
            analysis['redirect_count'] = len(response.history)
            analysis['redirect_chain'] = [r.url for r in response.history]
            analysis['final_url'] = response.url
            print(f"[LINK_ANALYZER]   → {analysis['redirect_count']} redirects")
        
        analysis['status_code'] = response.status_code
        
        # Check if final destination is legitimate
        final_domain = urlparse(response.url).netloc.lower()
        legit_domains = ['microsoft.com', 'paypal.com', 'amazon.com', 'google.com', 'apple.com']
        if any(legit in final_domain for legit in legit_domains):
            analysis['redirects_to_legit'] = True
            print(f"[LINK_ANALYZER]   ✓ Redirects to legitimate site: {final_domain}")
        
        # Analyze page content
        content = response.text.lower()
        
        # Detect credential harvesting
        if any(keyword in content for keyword in CREDENTIAL_HARVEST_KEYWORDS):
            if 'password' in content or 'login' in content:
                analysis['credential_harvest'] = True
                print(f"[LINK_ANALYZER]   🚨 Credential harvest detected")
        
        # Detect file downloads
        if any(indicator in content or indicator in response.url.lower() 
               for indicator in DOWNLOAD_INDICATORS):
            analysis['downloads_file'] = True
            print(f"[LINK_ANALYZER]   📥 File download detected")
        
        # Extract page title
        title_match = re.search(r'<title>(.*?)</title>', response.text, re.IGNORECASE)
        if title_match:
            analysis['page_title'] = title_match.group(1).strip()[:100]
        
    except requests.exceptions.Timeout:
        analysis['error'] = 'Timeout'
        print(f"[LINK_ANALYZER]   ⏱️ Timeout")
    except requests.exceptions.TooManyRedirects:
        analysis['error'] = 'Too many redirects'
        print(f"[LINK_ANALYZER]   🔄 Too many redirects")
    except Exception as e:
        analysis['error'] = str(e)[:200]
        print(f"[LINK_ANALYZER]   ❌ Error: {e}")
    
    return analysis


def generate_campaign_id(url: str, brand: str) -> str:
    """Generate a campaign ID to group related phishing attempts."""
    # Use domain + brand as campaign identifier
    parsed = urlparse(url)
    domain = parsed.netloc
    campaign_string = f"{domain}:{brand}"
    return hashlib.md5(campaign_string.encode()).hexdigest()[:8]


def analyze_link(link_obj, session) -> Dict:
    """
    Perform comprehensive analysis on a link and update database.
    
    Args:
        link_obj: Link database object
        session: SQLAlchemy session
    
    Returns:
        Dict with analysis results
    """
    url = link_obj.url
    
    print(f"\n[LINK_ANALYZER] 🎯 Starting analysis for Link #{link_obj.id}")
    
    # Step 1: Resolve IP and get geolocation
    hosting_ip = resolve_ip(url)
    country_code, country_flag = 'XX', '🏳️'
    if hosting_ip:
        country_code, country_flag = get_country_from_ip(hosting_ip)
        print(f"[LINK_ANALYZER]   🌍 Hosted in: {country_flag} {country_code} ({hosting_ip})")
    
    # Step 2: Visit URL in sandbox
    sandbox_results = analyze_url_sandbox(url)
    
    # Step 3: Detect brand impersonation
    impersonated_brand = detect_brand(url, sandbox_results.get('page_title'))
    print(f"[LINK_ANALYZER]   🏢 Brand: {impersonated_brand}")
    
    # Step 4: Calculate risk score
    analysis_data = {
        'impersonated_brand': impersonated_brand,
        'credential_harvest': sandbox_results.get('credential_harvest', False),
        'downloads_file': sandbox_results.get('downloads_file', False),
        'redirect_count': sandbox_results.get('redirect_count', 0),
        'redirects_to_legit': sandbox_results.get('redirects_to_legit', False),
    }
    risk_score = calculate_risk_score(url, analysis_data)
    
    # Determine risk level
    if risk_score >= 70:
        risk_level = 'high'
    elif risk_score >= 40:
        risk_level = 'medium'
    else:
        risk_level = 'low'
    
    print(f"[LINK_ANALYZER]   📊 Risk: {risk_level.upper()} ({risk_score}/100)")
    
    # Step 5: Generate campaign ID
    campaign_id = generate_campaign_id(url, impersonated_brand)
    
    # Step 6: Update database
    now = datetime.utcnow()
    link_obj.risk_score = risk_score
    link_obj.risk_level = risk_level
    link_obj.impersonated_brand = impersonated_brand
    link_obj.hosting_ip = hosting_ip
    link_obj.country_code = country_code
    link_obj.country_flag = country_flag
    link_obj.redirect_count = sandbox_results.get('redirect_count', 0)
    link_obj.final_url = sandbox_results.get('final_url')
    link_obj.campaign_id = campaign_id
    link_obj.first_seen = now
    link_obj.fetched_at = now  # Set fetched_at so links appear in dashboard
    link_obj.analyzed_at = now
    link_obj.analysis_complete = True
    link_obj.status = 'analyzed'
    
    # Store sandbox verdict as JSON
    verdict = {
        'credential_harvest': sandbox_results.get('credential_harvest', False),
        'downloads_file': sandbox_results.get('downloads_file', False),
        'redirects_to_legit': sandbox_results.get('redirects_to_legit', False),
        'page_title': sandbox_results.get('page_title'),
        'status_code': sandbox_results.get('status_code'),
        'error': sandbox_results.get('error'),
    }
    link_obj.sandbox_verdict = json.dumps(verdict)
    
    session.commit()
    print(f"[LINK_ANALYZER] ✅ Analysis complete for Link #{link_obj.id}")
    
    return {
        'link_id': link_obj.id,
        'risk_score': risk_score,
        'risk_level': risk_level,
        'brand': impersonated_brand,
        'campaign_id': campaign_id,
    }


def analyze_pending_links(session, limit: int = 10):
    """Analyze all pending links that haven't been analyzed yet."""
    from database.models import Link
    
    pending_links = session.query(Link).filter(
        Link.analysis_complete == False
    ).limit(limit).all()
    
    if not pending_links:
        print("[LINK_ANALYZER] No pending links to analyze")
        return
    
    print(f"[LINK_ANALYZER] 📋 Found {len(pending_links)} pending links")
    
    results = []
    for link in pending_links:
        try:
            result = analyze_link(link, session)
            results.append(result)
        except Exception as e:
            print(f"[LINK_ANALYZER] ❌ Failed to analyze Link #{link.id}: {e}")
            link.status = 'error'
            session.commit()
    
    return results
