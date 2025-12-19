"""
Sender Intelligence Service
Automatically gathers comprehensive threat intelligence about email senders.
Includes geolocation, IP reputation, domain analysis, and threat feed integration.
"""

import json
import re
import os
import requests
from typing import Dict, Optional, List
from datetime import datetime
from email import message_from_string
from email.utils import parseaddr
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    import whois
except ImportError:
    whois = None

try:
    import geoip2.database
    import geoip2.errors
except ImportError:
    geoip2 = None


def extract_sender_ip(email_headers: str) -> Optional[str]:
    """Extract originating IP address from email headers."""
    if not email_headers:
        return None
    
    try:
        msg = message_from_string(email_headers)
        
        # Try X-Originating-IP first
        orig_ip = msg.get('X-Originating-IP')
        if orig_ip:
            ip = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', orig_ip)
            if ip:
                return ip.group(1)
        
        # Parse Received headers
        received_headers = msg.get_all('Received', [])
        for received in received_headers:
            ip_match = re.search(r'\[(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\]', received)
            if not ip_match:
                ip_match = re.search(r'from\s+\S+\s+\((\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\)', received)
            
            if ip_match:
                ip = ip_match.group(1)
                if not is_private_ip(ip):
                    return ip
        
        return None
    except Exception as e:
        print(f"[SENDER_INTEL] Error extracting IP: {e}")
        return None


def is_private_ip(ip: str) -> bool:
    """Check if IP is private/local."""
    parts = ip.split('.')
    if len(parts) != 4:
        return True
    
    first = int(parts[0])
    second = int(parts[1])
    
    if first == 10 or first == 127:
        return True
    if first == 172 and 16 <= second <= 31:
        return True
    if first == 192 and second == 168:
        return True
    
    return False


def extract_sender_domain(sender_email: str) -> Optional[str]:
    """Extract domain from email address."""
    if not sender_email:
        return None
    
    _, email = parseaddr(sender_email)
    if '@' in email:
        return email.split('@')[1].lower()
    
    return None


def geolocate_ip(ip: str) -> Dict:
    """Get geolocation data for IP address."""
    result = {
        'country': None,
        'country_code': None,
        'city': None,
        'latitude': None,
        'longitude': None,
        'isp': None,
        'asn': None
    }
    
    if not ip:
        return result
    
    # Try MaxMind GeoIP2 database first
    if geoip2:
        try:
            db_paths = [
                os.path.join(os.path.dirname(__file__), '../data/GeoLite2-City.mmdb'),
                '/usr/share/GeoIP/GeoLite2-City.mmdb',
            ]
            
            for db_path in db_paths:
                if os.path.exists(db_path):
                    reader = geoip2.database.Reader(db_path)
                    response = reader.city(ip)
                    
                    result['country'] = response.country.name
                    result['country_code'] = response.country.iso_code
                    result['city'] = response.city.name
                    result['latitude'] = response.location.latitude
                    result['longitude'] = response.location.longitude
                    
                    reader.close()
                    print(f"[SENDER_INTEL] GeoIP: {ip} -> {result['city']}, {result['country']}")
                    return result
        except geoip2.errors.AddressNotFoundError:
            print(f"[SENDER_INTEL] IP {ip} not in GeoIP database")
        except Exception as e:
            print(f"[SENDER_INTEL] GeoIP error: {e}")
    
    # Fallback to ip-api.com
    try:
        response = requests.get(f"http://ip-api.com/json/{ip}", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                result['country'] = data.get('country')
                result['country_code'] = data.get('countryCode')
                result['city'] = data.get('city')
                result['latitude'] = data.get('lat')
                result['longitude'] = data.get('lon')
                result['isp'] = data.get('isp')
                result['asn'] = data.get('as')
                
                print(f"[SENDER_INTEL] ip-api: {ip} -> {result['city']}, {result['country']}")
                return result
    except Exception as e:
        print(f"[SENDER_INTEL] ip-api error: {e}")
    
    return result


def check_ip_reputation(ip: str) -> Dict:
    """Check IP reputation using AbuseIPDB API."""
    result = {
        'abuse_score': None,
        'abuse_reports_count': None,
        'is_vpn': False,
        'is_proxy': False,
        'is_tor': False,
        'reputation': 'unknown'
    }
    
    if not ip:
        return result
    
    api_key = os.getenv('ABUSEIPDB_API_KEY')
    if not api_key:
        print("[SENDER_INTEL] AbuseIPDB API key not configured")
        return result
    
    try:
        headers = {
            'Key': api_key,
            'Accept': 'application/json'
        }
        params = {
            'ipAddress': ip,
            'maxAgeInDays': 90,
            'verbose': ''
        }
        
        response = requests.get(
            'https://api.abuseipdb.com/api/v2/check',
            headers=headers,
            params=params,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json().get('data', {})
            
            result['abuse_score'] = data.get('abuseConfidenceScore', 0)
            result['abuse_reports_count'] = data.get('totalReports', 0)
            result['is_vpn'] = data.get('usageType') == 'Data Center/Web Hosting/Transit'
            result['is_tor'] = data.get('isTor', False)
            
            # Determine reputation
            score = result['abuse_score']
            if score >= 75:
                result['reputation'] = 'malicious'
            elif score >= 25:
                result['reputation'] = 'suspicious'
            else:
                result['reputation'] = 'clean'
            
            print(f"[SENDER_INTEL] AbuseIPDB: {ip} -> Score: {score}, Reports: {result['abuse_reports_count']}")
        else:
            print(f"[SENDER_INTEL] AbuseIPDB error: {response.status_code}")
    
    except Exception as e:
        print(f"[SENDER_INTEL] AbuseIPDB exception: {e}")
    
    return result


def analyze_domain(domain: str) -> Dict:
    """Analyze domain using WHOIS lookup."""
    result = {
        'domain_age_days': None,
        'domain_registrar': None,
        'domain_country': None,
        'privacy_protected': False
    }
    
    if not domain or not whois:
        return result
    
    try:
        w = whois.whois(domain)
        
        # Get creation date
        creation_date = w.creation_date
        if isinstance(creation_date, list):
            creation_date = creation_date[0]
        
        if creation_date:
            # Handle timezone-aware datetimes
            if creation_date.tzinfo is not None:
                # Remove timezone info for comparison
                creation_date = creation_date.replace(tzinfo=None)
            age = (datetime.now() - creation_date).days
            result['domain_age_days'] = age
        
        result['domain_registrar'] = w.registrar
        result['domain_country'] = w.country
        
        # Check for privacy protection
        registrant = str(w.name).lower() if w.name else ''
        result['privacy_protected'] = any(keyword in registrant for keyword in [
            'privacy', 'protected', 'redacted', 'whoisguard', 'proxy'
        ])
        
        print(f"[SENDER_INTEL] WHOIS: {domain} -> Age: {result['domain_age_days']} days")
    
    except Exception as e:
        print(f"[SENDER_INTEL] WHOIS error for {domain}: {e}")
    
    return result


def check_urlhaus(url: str) -> Dict:
    """Check URL against URLhaus malware database (no API key needed)."""
    result = {
        'urlhaus_malware': False,
        'urlhaus_threat': None,
        'urlhaus_tags': []
    }
    
    if not url:
        return result
    
    try:
        response = requests.post(
            'https://urlhaus-api.abuse.ch/v1/url/',
            data={'url': url},
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('query_status') == 'ok':
                result['urlhaus_malware'] = True
                result['urlhaus_threat'] = data.get('threat')
                result['urlhaus_tags'] = data.get('tags', [])
                print(f"[SENDER_INTEL] URLhaus: {url} -> MALWARE DETECTED ({data.get('threat')})")
            else:
                print(f"[SENDER_INTEL] URLhaus: {url} -> Clean")
    
    except Exception as e:
        print(f"[SENDER_INTEL] URLhaus error: {e}")
    
    return result


def check_phishtank(url: str) -> Dict:
    """Check URL against PhishTank database (requires API key)."""
    result = {
        'phishtank_phishing': False,
        'phishtank_verified': False
    }
    
    if not url:
        return result
    
    api_key = os.getenv('PHISHTANK_API_KEY')
    if not api_key:
        return result
    
    try:
        import urllib.parse
        response = requests.post(
            'https://checkurl.phishtank.com/checkurl/',
            data={
                'url': urllib.parse.quote(url),
                'format': 'json',
                'app_key': api_key
            },
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', {})
            result['phishtank_phishing'] = results.get('in_database', False)
            result['phishtank_verified'] = results.get('verified', False)
            
            if result['phishtank_phishing']:
                print(f"[SENDER_INTEL] PhishTank: {url} -> PHISHING DETECTED")
            else:
                print(f"[SENDER_INTEL] PhishTank: {url} -> Clean")
    
    except Exception as e:
        print(f"[SENDER_INTEL] PhishTank error: {e}")
    
    return result


def check_alienvault_otx(domain: str = None, ip: str = None) -> Dict:
    """Check domain/IP against AlienVault OTX threat intelligence."""
    result = {
        'otx_pulses': 0,
        'otx_malicious': False,
        'otx_tags': [],
        'otx_threat_score': 0
    }
    
    api_key = os.getenv('ALIENVAULT_OTX_API_KEY')
    if not api_key or api_key == 'your_api_key_here':
        return result
    
    headers = {'X-OTX-API-KEY': api_key}
    
    try:
        # Check domain
        if domain:
            response = requests.get(
                f'https://otx.alienvault.com/api/v1/indicators/domain/{domain}/general',
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                pulse_info = data.get('pulse_info', {})
                result['otx_pulses'] = pulse_info.get('count', 0)
                
                # Analyze pulses
                pulses = pulse_info.get('pulses', [])
                malicious_tags = ['malware', 'phishing', 'ransomware', 'trojan', 'botnet', 'c2']
                
                for pulse in pulses:
                    tags = [tag.lower() for tag in pulse.get('tags', [])]
                    result['otx_tags'].extend(tags)
                    
                    # Check for malicious indicators
                    if any(tag in malicious_tags for tag in tags):
                        result['otx_malicious'] = True
                
                # Calculate threat score
                if result['otx_pulses'] > 0:
                    base_score = min(result['otx_pulses'] * 10, 50)
                    malicious_bonus = 50 if result['otx_malicious'] else 0
                    result['otx_threat_score'] = min(base_score + malicious_bonus, 100)
                
                print(f"[SENDER_INTEL] AlienVault OTX: {domain} -> {result['otx_pulses']} pulses, "
                      f"Malicious: {result['otx_malicious']}, Score: {result['otx_threat_score']}")
        
        # Check IP
        elif ip:
            response = requests.get(
                f'https://otx.alienvault.com/api/v1/indicators/IPv4/{ip}/general',
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                pulse_info = data.get('pulse_info', {})
                result['otx_pulses'] = pulse_info.get('count', 0)
                
                if result['otx_pulses'] > 0:
                    result['otx_malicious'] = True
                    result['otx_threat_score'] = min(result['otx_pulses'] * 15, 100)
                
                print(f"[SENDER_INTEL] AlienVault OTX: {ip} -> {result['otx_pulses']} pulses")
    
    except Exception as e:
        print(f"[SENDER_INTEL] AlienVault OTX error: {e}")
    
    return result


def check_virustotal(domain: str, ip: str) -> Dict:
    """Check domain/IP against VirusTotal."""
    result = {
        'virustotal_detections': None,
        'virustotal_categories': []
    }
    
    api_key = os.getenv('VIRUSTOTAL_API_KEY')
    if not api_key:
        print("[SENDER_INTEL] VirusTotal API key not configured")
        return result
    
    try:
        headers = {'x-apikey': api_key}
        
        # Check domain
        if domain:
            response = requests.get(
                f'https://www.virustotal.com/api/v3/domains/{domain}',
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json().get('data', {}).get('attributes', {})
                stats = data.get('last_analysis_stats', {})
                
                malicious = stats.get('malicious', 0)
                suspicious = stats.get('suspicious', 0)
                total = sum(stats.values())
                
                result['virustotal_detections'] = malicious + suspicious
                
                categories = data.get('categories', {})
                result['virustotal_categories'] = list(categories.values())
                
                print(f"[SENDER_INTEL] VirusTotal: {domain} -> {malicious + suspicious}/{total} detections")
    
    except Exception as e:
        print(f"[SENDER_INTEL] VirusTotal error: {e}")
    
    return result


def calculate_threat_level(intel_data: Dict) -> tuple:
    """Calculate overall threat level and confidence."""
    risk_factors = []
    score = 0.0
    
    # IP reputation (40% weight)
    abuse_score = intel_data.get('abuse_score') or 0
    if abuse_score >= 75:
        score += 0.4
        risk_factors.append("High IP abuse score")
    elif abuse_score >= 25:
        score += 0.2
        risk_factors.append("Moderate IP abuse score")
    
    # VPN/Proxy detection (10% weight)
    if intel_data.get('is_vpn') or intel_data.get('is_proxy'):
        score += 0.1
        risk_factors.append("VPN/Proxy detected")
    
    if intel_data.get('is_tor'):
        score += 0.15
        risk_factors.append("Tor exit node")
    
    # Domain age (20% weight)
    domain_age = intel_data.get('domain_age_days')
    if domain_age is not None:
        if domain_age < 30:
            score += 0.2
            risk_factors.append(f"New domain ({domain_age} days old)")
        elif domain_age < 90:
            score += 0.1
            risk_factors.append(f"Recent domain ({domain_age} days old)")
    
    # Privacy protection (5% weight)
    if intel_data.get('privacy_protected'):
        score += 0.05
        risk_factors.append("Domain privacy protection enabled")
    
    # VirusTotal detections (25% weight)
    vt_detections = intel_data.get('virustotal_detections') or 0
    if vt_detections >= 5:
        score += 0.25
        risk_factors.append(f"VirusTotal: {vt_detections} vendors flagged")
    elif vt_detections >= 1:
        score += 0.15
        risk_factors.append(f"VirusTotal: {vt_detections} vendors flagged")
    
    # URLhaus malware detections (30% weight - very high confidence)
    urlhaus_hits = intel_data.get('urlhaus_detections') or 0
    if urlhaus_hits > 0:
        score += 0.3
        malware_threats = intel_data.get('malware_threats', [])
        if malware_threats:
            risk_factors.append(f"URLhaus: {urlhaus_hits} malware URL(s) - {', '.join(set(malware_threats))}")
        else:
            risk_factors.append(f"URLhaus: {urlhaus_hits} malware URL(s)")
    
    # PhishTank phishing detections (25% weight)
    phishtank_hits = intel_data.get('phishtank_detections') or 0
    if phishtank_hits > 0:
        score += 0.25
        risk_factors.append(f"PhishTank: {phishtank_hits} phishing URL(s)")
    
    # AlienVault OTX threat intelligence (35% weight - very high confidence)
    otx_pulses = intel_data.get('otx_pulses') or 0
    otx_malicious = intel_data.get('otx_malicious', False)
    otx_threat_score = intel_data.get('otx_threat_score', 0)
    
    if otx_pulses > 0:
        # Scale OTX threat score (0-100) to weight (0-0.35)
        otx_weight = (otx_threat_score / 100) * 0.35
        score += otx_weight
        
        otx_tags = intel_data.get('otx_tags', [])
        unique_tags = list(set(otx_tags))[:5]  # Show up to 5 unique tags
        
        if otx_malicious:
            risk_factors.append(f"AlienVault OTX: {otx_pulses} threat pulses - MALICIOUS ({', '.join(unique_tags)})")
        else:
            risk_factors.append(f"AlienVault OTX: {otx_pulses} threat pulses")
    
    # Determine threat level
    if score >= 0.7:
        threat_level = 'critical'
    elif score >= 0.5:
        threat_level = 'high'
    elif score >= 0.3:
        threat_level = 'medium'
    else:
        threat_level = 'low'
    
    confidence = min(score, 1.0)
    
    return threat_level, confidence, risk_factors


def analyze_sender(email_obj, db_session, sender_ip_from_headers=None) -> Optional[object]:
    """
    Main function: Analyze email sender and store intelligence.
    
    Args:
        email_obj: Email database object
        db_session: Database session
        sender_ip_from_headers: IP address extracted from email headers (optional)
    
    Returns:
        SenderIntelligence object or None.
    """
    from database.models import SenderIntelligence
    
    print(f"[SENDER_INTEL] Analyzing sender for email ID {email_obj.id}")
    
    # Check if intelligence already exists for this email
    existing = db_session.query(SenderIntelligence).filter_by(email_id=email_obj.id).first()
    if existing:
        print(f"[SENDER_INTEL] Intelligence already exists for email {email_obj.id}, skipping")
        return existing
    
    # Extract basic info
    sender_domain = extract_sender_domain(email_obj.sender)
    
    # Use IP from headers if provided, otherwise try to extract from body
    sender_ip = sender_ip_from_headers or extract_sender_ip(email_obj.body_html or email_obj.body_text or '')
    
    if not sender_ip and not sender_domain:
        print("[SENDER_INTEL] No IP or domain to analyze")
        return None
    
    # Gather intelligence
    intel_data = {}
    
    # Geolocation
    if sender_ip:
        geo_data = geolocate_ip(sender_ip)
        intel_data.update(geo_data)
        
        # IP reputation
        rep_data = check_ip_reputation(sender_ip)
        intel_data.update(rep_data)
    
    # Domain analysis
    if sender_domain:
        domain_data = analyze_domain(sender_domain)
        intel_data.update(domain_data)
        
        # VirusTotal
        vt_data = check_virustotal(sender_domain, sender_ip)
        intel_data.update(vt_data)
        
        # AlienVault OTX
        otx_data = check_alienvault_otx(domain=sender_domain, ip=sender_ip)
        intel_data.update(otx_data)
    
    # URL threat feeds (check all URLs in email)
    from database.models import Link
    links = db_session.query(Link).filter_by(email_id=email_obj.id).all()
    
    urlhaus_hits = 0
    phishtank_hits = 0
    malware_threats = []
    
    for link in links:
        # URLhaus check (free, no API key)
        urlhaus_result = check_urlhaus(link.url)
        if urlhaus_result['urlhaus_malware']:
            urlhaus_hits += 1
            if urlhaus_result['urlhaus_threat']:
                malware_threats.append(urlhaus_result['urlhaus_threat'])
        
        # PhishTank check (if API key configured)
        phishtank_result = check_phishtank(link.url)
        if phishtank_result['phishtank_phishing']:
            phishtank_hits += 1
    
    intel_data['urlhaus_detections'] = urlhaus_hits
    intel_data['phishtank_detections'] = phishtank_hits
    intel_data['malware_threats'] = malware_threats
    
    # Calculate threat level
    threat_level, confidence, risk_factors = calculate_threat_level(intel_data)
    
    # Create SenderIntelligence record
    sender_intel = SenderIntelligence(
        email_id=email_obj.id,
        sender_ip=sender_ip,
        sender_domain=sender_domain,
        country=intel_data.get('country'),
        country_code=intel_data.get('country_code'),
        city=intel_data.get('city'),
        latitude=intel_data.get('latitude'),
        longitude=intel_data.get('longitude'),
        isp=intel_data.get('isp'),
        asn=intel_data.get('asn'),
        is_vpn=intel_data.get('is_vpn', False),
        is_proxy=intel_data.get('is_proxy', False),
        is_tor=intel_data.get('is_tor', False),
        abuse_score=intel_data.get('abuse_score'),
        abuse_reports_count=intel_data.get('abuse_reports_count'),
        ip_reputation=intel_data.get('reputation'),
        domain_age_days=intel_data.get('domain_age_days'),
        domain_registrar=intel_data.get('domain_registrar'),
        domain_country=intel_data.get('domain_country'),
        privacy_protected=intel_data.get('privacy_protected', False),
        virustotal_detections=intel_data.get('virustotal_detections'),
        virustotal_categories=json.dumps(intel_data.get('virustotal_categories', [])),
        urlhaus_listed=(urlhaus_hits > 0),
        phishtank_listed=(phishtank_hits > 0),
        alienvault_tags=json.dumps(intel_data.get('otx_tags', [])),
        threat_level=threat_level,
        confidence_score=confidence,
        risk_factors=json.dumps(risk_factors),
        analyzed_at=datetime.utcnow()
    )
    
    db_session.add(sender_intel)
    db_session.commit()
    
    print(f"[SENDER_INTEL] ✓ Analysis complete: Threat={threat_level}, Confidence={confidence:.2f}")
    print(f"[SENDER_INTEL] Risk factors: {', '.join(risk_factors) if risk_factors else 'None'}")
    
    return sender_intel
