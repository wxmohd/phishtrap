"""
URL Pattern Analysis Service
Detects typosquatting, URL shorteners, and suspicious domain patterns.
"""
import re
from urllib.parse import urlparse
from difflib import SequenceMatcher
from typing import Dict, List, Optional


# Known legitimate brands to check for typosquatting
LEGITIMATE_BRANDS = [
    'paypal', 'amazon', 'microsoft', 'google', 'facebook', 'apple',
    'netflix', 'ebay', 'walmart', 'target', 'bestbuy', 'instagram',
    'twitter', 'linkedin', 'dropbox', 'adobe', 'oracle', 'salesforce',
    'bank', 'chase', 'wellsfargo', 'citibank', 'bankofamerica'
]

# Common URL shortener domains
URL_SHORTENERS = [
    'bit.ly', 'tinyurl.com', 'goo.gl', 't.co', 'ow.ly', 'is.gd',
    'buff.ly', 'adf.ly', 'bit.do', 'lnkd.in', 'shorte.st', 'mcaf.ee',
    'su.pr', 'tiny.cc', 'rebrand.ly', 'cutt.ly', 'shorturl.at'
]

# Suspicious domain patterns
SUSPICIOUS_PATTERNS = [
    r'secure[-_]',
    r'verify[-_]',
    r'account[-_]',
    r'login[-_]',
    r'signin[-_]',
    r'update[-_]',
    r'confirm[-_]',
    r'banking[-_]',
    r'support[-_]',
    r'service[-_]',
]

# Suspicious TLDs
SUSPICIOUS_TLDS = [
    '.tk', '.ml', '.ga', '.cf', '.gq',
    '.xyz', '.top', '.work', '.click', '.link',
    '.download', '.stream', '.review', '.trade'
]


def calculate_similarity(str1: str, str2: str) -> float:
    """Calculate similarity ratio between two strings (0-1)."""
    return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()


def detect_typosquatting(domain: str) -> Optional[Dict]:
    """Detect if domain is typosquatting a legitimate brand."""
    domain_lower = domain.lower()
    domain_name = re.sub(r'\.(com|net|org|co|io|app|dev)$', '', domain_lower)
    
    for brand in LEGITIMATE_BRANDS:
        similarity = calculate_similarity(domain_name, brand)
        
        if 0.75 <= similarity < 1.0:
            technique = detect_typosquatting_technique(domain_name, brand)
            
            return {
                'is_typosquatting': True,
                'target_brand': brand,
                'similarity': round(similarity * 100, 2),
                'technique': technique,
                'risk_level': 'HIGH' if similarity > 0.85 else 'MEDIUM'
            }
    
    return None


def detect_typosquatting_technique(typo_domain: str, brand: str) -> str:
    """Identify the specific typosquatting technique used."""
    if len(typo_domain) == len(brand):
        diff_count = sum(1 for a, b in zip(typo_domain, brand) if a != b)
        if diff_count == 1:
            return "Character Substitution"
    
    if len(typo_domain) == len(brand) - 1:
        return "Missing Character"
    
    if len(typo_domain) == len(brand) + 1:
        return "Extra Character"
    
    homoglyphs = {'0': 'o', '1': 'l', '1': 'i', '5': 's', '8': 'b'}
    for typo_char, real_char in homoglyphs.items():
        if typo_char in typo_domain and real_char in brand:
            return "Homoglyph Attack"
    
    if '-' in typo_domain and '-' not in brand:
        return "Hyphen Insertion"
    
    return "Similar Domain"


def is_url_shortener(url: str) -> bool:
    """Check if URL uses a known shortener service."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        domain = re.sub(r'^www\.', '', domain)
        return domain in URL_SHORTENERS
    except:
        return False


def detect_suspicious_patterns(domain: str) -> List[str]:
    """Detect suspicious patterns in domain name."""
    suspicious_flags = []
    domain_lower = domain.lower()
    
    for pattern in SUSPICIOUS_PATTERNS:
        if re.search(pattern, domain_lower):
            keyword = pattern.replace('[-_]', '').replace(r'\b', '')
            suspicious_flags.append(f"Contains '{keyword}' keyword")
    
    for tld in SUSPICIOUS_TLDS:
        if domain_lower.endswith(tld):
            suspicious_flags.append(f"Suspicious TLD: {tld}")
    
    hyphen_count = domain.count('-')
    if hyphen_count >= 3:
        suspicious_flags.append(f"Excessive hyphens ({hyphen_count})")
    
    if re.search(r'\d', domain) and not re.search(r'^(365|24|7)$', domain):
        suspicious_flags.append("Contains numbers")
    
    parts = domain.split('.')
    if len(parts) > 3:
        suspicious_flags.append(f"Long subdomain chain ({len(parts)} levels)")
    
    return suspicious_flags


def analyze_url(url: str) -> Dict:
    """Comprehensive URL analysis."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        domain_clean = re.sub(r'^www\.', '', domain)
        
        analysis = {
            'url': url,
            'domain': domain,
            'is_shortener': False,
            'typosquatting': None,
            'suspicious_patterns': [],
            'risk_score': 0,
            'risk_level': 'LOW',
            'flags': []
        }
        
        if is_url_shortener(url):
            analysis['is_shortener'] = True
            analysis['flags'].append('URL Shortener')
            analysis['risk_score'] += 20
        
        typo_result = detect_typosquatting(domain_clean)
        if typo_result:
            analysis['typosquatting'] = typo_result
            analysis['flags'].append(f"Typosquatting: {typo_result['target_brand']}")
            analysis['risk_score'] += 40 if typo_result['risk_level'] == 'HIGH' else 25
        
        suspicious = detect_suspicious_patterns(domain_clean)
        if suspicious:
            analysis['suspicious_patterns'] = suspicious
            analysis['flags'].extend(suspicious)
            analysis['risk_score'] += len(suspicious) * 10
        
        if analysis['risk_score'] >= 50:
            analysis['risk_level'] = 'HIGH'
        elif analysis['risk_score'] >= 25:
            analysis['risk_level'] = 'MEDIUM'
        else:
            analysis['risk_level'] = 'LOW'
        
        return analysis
        
    except Exception as e:
        return {
            'url': url,
            'error': str(e),
            'risk_level': 'UNKNOWN'
        }


def analyze_url_batch(urls: List[str]) -> List[Dict]:
    """Analyze multiple URLs and return results."""
    return [analyze_url(url) for url in urls]


def get_url_statistics(url_analyses: List[Dict]) -> Dict:
    """Generate statistics from URL analyses."""
    total = len(url_analyses)
    
    if total == 0:
        return {
            'total_urls': 0,
            'shorteners': 0,
            'typosquatting': 0,
            'high_risk': 0,
            'medium_risk': 0,
            'low_risk': 0
        }
    
    shorteners = sum(1 for a in url_analyses if a.get('is_shortener'))
    typosquatting = sum(1 for a in url_analyses if a.get('typosquatting'))
    high_risk = sum(1 for a in url_analyses if a.get('risk_level') == 'HIGH')
    medium_risk = sum(1 for a in url_analyses if a.get('risk_level') == 'MEDIUM')
    low_risk = sum(1 for a in url_analyses if a.get('risk_level') == 'LOW')
    
    return {
        'total_urls': total,
        'shorteners': shorteners,
        'shorteners_pct': round(shorteners / total * 100, 1) if total > 0 else 0,
        'typosquatting': typosquatting,
        'typosquatting_pct': round(typosquatting / total * 100, 1) if total > 0 else 0,
        'high_risk': high_risk,
        'medium_risk': medium_risk,
        'low_risk': low_risk,
        'high_risk_pct': round(high_risk / total * 100, 1) if total > 0 else 0
    }
