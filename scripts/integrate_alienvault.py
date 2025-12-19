#!/usr/bin/env python3
"""
AlienVault OTX Integration Example
Add this to services/sender_intel.py
"""
import requests
from typing import Dict, List

def check_alienvault_otx(domain: str = None, ip: str = None) -> Dict:
    """
    Check domain/IP against AlienVault OTX threat intelligence.
    
    Returns:
        Dict with:
        - otx_pulses: Number of threat intelligence pulses
        - otx_malicious: Boolean if found in malicious pulses
        - otx_tags: List of threat tags
        - otx_threat_score: Calculated threat score (0-100)
    """
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    result = {
        'otx_pulses': 0,
        'otx_malicious': False,
        'otx_tags': [],
        'otx_threat_score': 0
    }
    
    api_key = os.getenv('c3a4bc65b256514851c575e8b82777d1335d6a21723a6a79ec0c0dce84be50b9')
    if not api_key:
        print("[SENDER_INTEL] AlienVault OTX API key not configured")
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
                
                # Calculate threat score based on pulses and tags
                if result['otx_pulses'] > 0:
                    base_score = min(result['otx_pulses'] * 10, 50)
                    malicious_bonus = 50 if result['otx_malicious'] else 0
                    result['otx_threat_score'] = min(base_score + malicious_bonus, 100)
                
                print(f"[SENDER_INTEL] AlienVault OTX: {domain} -> {result['otx_pulses']} pulses, "
                      f"Malicious: {result['otx_malicious']}, Score: {result['otx_threat_score']}")
        
        # Check IP
        if ip and not domain:
            response = requests.get(
                f'https://otx.alienvault.com/api/v1/indicators/IPv4/{ip}/general',
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                pulse_info = data.get('pulse_info', {})
                result['otx_pulses'] = pulse_info.get('count', 0)
                
                pulses = pulse_info.get('pulses', [])
                for pulse in pulses:
                    tags = pulse.get('tags', [])
                    result['otx_tags'].extend(tags)
                
                if result['otx_pulses'] > 0:
                    result['otx_malicious'] = True
                    result['otx_threat_score'] = min(result['otx_pulses'] * 15, 100)
                
                print(f"[SENDER_INTEL] AlienVault OTX: {ip} -> {result['otx_pulses']} pulses")
    
    except Exception as e:
        print(f"[SENDER_INTEL] AlienVault OTX error: {e}")
    
    return result


def check_google_safe_browsing(urls: List[str]) -> Dict:
    """
    Check URLs against Google Safe Browsing API.
    
    Returns:
        Dict with:
        - threats_found: Number of threats detected
        - threat_types: List of threat types
        - malicious_urls: List of malicious URLs
    """
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    result = {
        'threats_found': 0,
        'threat_types': [],
        'malicious_urls': []
    }
    
    if not urls:
        return result
    
    api_key = os.getenv('GOOGLE_SAFE_BROWSING_KEY')
    if not api_key:
        print("[SENDER_INTEL] Google Safe Browsing API key not configured")
        return result
    
    try:
        threat_entries = [{'url': url} for url in urls]
        
        response = requests.post(
            f'https://safebrowsing.googleapis.com/v4/threatMatches:find?key={api_key}',
            json={
                'client': {
                    'clientId': 'phishtrap',
                    'clientVersion': '1.0'
                },
                'threatInfo': {
                    'threatTypes': ['MALWARE', 'SOCIAL_ENGINEERING', 'UNWANTED_SOFTWARE', 'POTENTIALLY_HARMFUL_APPLICATION'],
                    'platformTypes': ['ANY_PLATFORM'],
                    'threatEntryTypes': ['URL'],
                    'threatEntries': threat_entries
                }
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            matches = data.get('matches', [])
            
            result['threats_found'] = len(matches)
            result['threat_types'] = list(set([m.get('threatType') for m in matches]))
            result['malicious_urls'] = [m.get('threat', {}).get('url') for m in matches]
            
            if result['threats_found'] > 0:
                print(f"[SENDER_INTEL] Google Safe Browsing: {result['threats_found']} threats detected")
                print(f"[SENDER_INTEL]   Threat types: {', '.join(result['threat_types'])}")
            else:
                print(f"[SENDER_INTEL] Google Safe Browsing: All URLs clean")
    
    except Exception as e:
        print(f"[SENDER_INTEL] Google Safe Browsing error: {e}")
    
    return result


def check_ipinfo(ip: str) -> Dict:
    """
    Get enhanced geolocation and threat data from IPinfo.io.
    
    Returns:
        Dict with geolocation, ASN, company, privacy detection
    """
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    result = {
        'country': None,
        'city': None,
        'region': None,
        'latitude': None,
        'longitude': None,
        'isp': None,
        'asn': None,
        'company': None,
        'is_vpn': False,
        'is_proxy': False,
        'is_hosting': False
    }
    
    if not ip:
        return result
    
    api_key = os.getenv('IPINFO_API_KEY')
    if not api_key:
        # Try without API key (limited)
        url = f'https://ipinfo.io/{ip}/json'
    else:
        url = f'https://ipinfo.io/{ip}?token={api_key}'
    
    try:
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            
            result['country'] = data.get('country')
            result['city'] = data.get('city')
            result['region'] = data.get('region')
            
            # Parse location
            loc = data.get('loc', '').split(',')
            if len(loc) == 2:
                result['latitude'] = float(loc[0])
                result['longitude'] = float(loc[1])
            
            result['isp'] = data.get('org')
            result['asn'] = data.get('asn', {}).get('asn') if isinstance(data.get('asn'), dict) else None
            result['company'] = data.get('company', {}).get('name') if isinstance(data.get('company'), dict) else None
            
            # Privacy detection (requires paid plan)
            privacy = data.get('privacy', {})
            result['is_vpn'] = privacy.get('vpn', False)
            result['is_proxy'] = privacy.get('proxy', False)
            result['is_hosting'] = privacy.get('hosting', False)
            
            print(f"[SENDER_INTEL] IPinfo: {ip} -> {result['city']}, {result['country']}")
    
    except Exception as e:
        print(f"[SENDER_INTEL] IPinfo error: {e}")
    
    return result


# Test the integrations
if __name__ == "__main__":
    print("Testing AlienVault OTX...")
    otx_result = check_alienvault_otx(domain="google.com")
    print(f"Result: {otx_result}\n")
    
    print("Testing Google Safe Browsing...")
    gsb_result = check_google_safe_browsing(["https://google.com"])
    print(f"Result: {gsb_result}\n")
    
    print("Testing IPinfo...")
    ipinfo_result = check_ipinfo("8.8.8.8")
    print(f"Result: {ipinfo_result}")
