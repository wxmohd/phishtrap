# 🔍 Sender Intelligence Troubleshooting & Enhancement Guide

## 📊 **Current Status**

### ✅ **What's Working:**
- Domain extraction (outlook.com detected)
- VirusTotal API integration (0 detections for outlook.com)
- GeoIP database installed (61MB)
- WHOIS library installed
- AbuseIPDB API configured
- VirusTotal API configured

### ❌ **What's Not Working:**
1. **No IP addresses extracted** from Outlook emails
2. **Domain WHOIS data shows "Unknown"** (analysis ran before WHOIS was installed)
3. **Geolocation shows "Unknown"** (no IP = no geolocation)
4. **ISP shows "Unknown"** (no IP = no ISP data)

---

## 🔍 **Root Cause Analysis**

### **Issue #1: No IP Addresses**

**Why:**
- Outlook/Microsoft Graph API doesn't include sender IP in message body
- Code tries to extract IP from `body_html`/`body_text` (wrong location)
- Email headers (where IP is stored) are not fetched or stored

**Impact:**
- ❌ No geolocation data
- ❌ No ISP information
- ❌ No IP reputation checks
- ❌ No VPN/Proxy detection

**Solution Options:**

**Option A: Fetch Email Headers (Complex)**
```python
# Requires additional Microsoft Graph API call per email
GET /me/messages/{id}/$value
# Returns full MIME message with headers
```
- ✅ Gets real sender IP
- ❌ Requires extra API call per email
- ❌ Increases processing time
- ❌ May hit rate limits

**Option B: Accept Limitation (Recommended)**
- ✅ Fast processing
- ✅ No extra API calls
- ✅ Still get domain analysis
- ❌ No IP-based intelligence

### **Issue #2: Domain Analysis Shows "Unknown"**

**Why:**
- WHOIS library was installed AFTER emails were analyzed
- Existing sender_intelligence records have NULL domain data
- New emails will have proper WHOIS data

**Solution:**
Re-analyze existing emails to populate WHOIS data.

---

## 🛠️ **Quick Fixes**

### **Fix #1: Re-analyze Existing Emails**

Run this to re-populate sender intelligence for all emails:

```bash
cd /home/osboxes/phishtrap
source venv/bin/activate
python3 << 'EOF'
from database.models import SessionLocal, Email
from services.sender_intel import analyze_sender

with SessionLocal() as session:
    emails = session.query(Email).all()
    for email in emails:
        print(f"Re-analyzing email {email.id}...")
        try:
            # Delete old intelligence
            session.query(SenderIntelligence).filter_by(email_id=email.id).delete()
            # Re-analyze
            analyze_sender(email, session)
        except Exception as e:
            print(f"Error: {e}")
    session.commit()
print("✓ Re-analysis complete!")
EOF
```

### **Fix #2: Add Note About Missing IP**

Update the template to explain why IP is missing for Outlook emails.

---

## 🌐 **Additional Threat Intelligence APIs**

### **Recommended Free APIs to Add:**

#### **1. URLhaus (Malware URLs)**
- **Free:** Unlimited
- **What:** Malware URL database
- **API:** https://urlhaus-api.abuse.ch/
- **No API key needed!**

```python
def check_urlhaus(url: str) -> Dict:
    """Check if URL is in URLhaus malware database."""
    response = requests.post(
        'https://urlhaus-api.abuse.ch/v1/url/',
        data={'url': url},
        timeout=5
    )
    if response.status_code == 200:
        data = response.json()
        if data.get('query_status') == 'ok':
            return {
                'is_malware': True,
                'threat': data.get('threat'),
                'tags': data.get('tags', [])
            }
    return {'is_malware': False}
```

#### **2. PhishTank (Phishing URLs)**
- **Free:** Unlimited
- **What:** Phishing URL database
- **API:** https://checkurl.phishtank.com/checkurl/
- **Requires free API key**

```python
def check_phishtank(url: str, api_key: str) -> Dict:
    """Check if URL is in PhishTank database."""
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
        return {
            'is_phishing': data.get('results', {}).get('in_database', False),
            'verified': data.get('results', {}).get('verified', False)
        }
    return {'is_phishing': False}
```

#### **3. Google Safe Browsing**
- **Free:** 10,000 requests/day
- **What:** Google's phishing/malware database
- **API:** https://developers.google.com/safe-browsing/v4/get-started

```python
def check_safe_browsing(urls: List[str], api_key: str) -> Dict:
    """Check URLs against Google Safe Browsing."""
    threat_entries = [{'url': url} for url in urls]
    response = requests.post(
        f'https://safebrowsing.googleapis.com/v4/threatMatches:find?key={api_key}',
        json={
            'client': {'clientId': 'phishtrap', 'clientVersion': '1.0'},
            'threatInfo': {
                'threatTypes': ['MALWARE', 'SOCIAL_ENGINEERING'],
                'platformTypes': ['ANY_PLATFORM'],
                'threatEntryTypes': ['URL'],
                'threatEntries': threat_entries
            }
        },
        timeout=10
    )
    if response.status_code == 200:
        data = response.json()
        return {
            'threats_found': len(data.get('matches', [])),
            'matches': data.get('matches', [])
        }
    return {'threats_found': 0}
```

#### **4. EmailRep.io (Email Reputation)**
- **Free:** 100 requests/day
- **What:** Email reputation scoring
- **API:** https://emailrep.io/

```python
def check_emailrep(email: str) -> Dict:
    """Check email reputation."""
    response = requests.get(
        f'https://emailrep.io/{email}',
        headers={'User-Agent': 'PhishTrap/1.0'},
        timeout=5
    )
    if response.status_code == 200:
        data = response.json()
        return {
            'reputation': data.get('reputation'),
            'suspicious': data.get('suspicious', False),
            'references': data.get('references', 0),
            'details': data.get('details', {})
        }
    return {}
```

#### **5. IPQualityScore (Fraud Detection)**
- **Free:** 5,000 lookups/month
- **What:** IP/Email/URL fraud scoring
- **API:** https://www.ipqualityscore.com/create-account

```python
def check_ipqs(email: str, api_key: str) -> Dict:
    """Check email with IPQualityScore."""
    response = requests.get(
        f'https://ipqualityscore.com/api/json/email/{api_key}/{email}',
        timeout=5
    )
    if response.status_code == 200:
        data = response.json()
        return {
            'fraud_score': data.get('fraud_score', 0),
            'disposable': data.get('disposable', False),
            'spam_trap': data.get('spam_trap_score'),
            'valid': data.get('valid', False)
        }
    return {}
```

---

## 📋 **API Key Setup Guide**

### **Get Free API Keys:**

1. **PhishTank**
   - Sign up: https://www.phishtank.com/register.php
   - Get key: https://www.phishtank.com/api_info.php
   - Add to `.env`: `PHISHTANK_API_KEY=your_key`

2. **Google Safe Browsing**
   - Go to: https://console.cloud.google.com/
   - Enable Safe Browsing API
   - Create API key
   - Add to `.env`: `GOOGLE_SAFE_BROWSING_KEY=your_key`

3. **EmailRep.io**
   - Sign up: https://emailrep.io/
   - Get key from dashboard
   - Add to `.env`: `EMAILREP_API_KEY=your_key`

4. **IPQualityScore**
   - Sign up: https://www.ipqualityscore.com/create-account
   - Get key from dashboard
   - Add to `.env`: `IPQS_API_KEY=your_key`

---

## 🎯 **Recommended Implementation Priority**

### **Phase 1: No-Code-Change Fixes**
1. ✅ Re-analyze existing emails (populate WHOIS data)
2. ✅ Update template to explain missing IP for Outlook

### **Phase 2: Easy Additions (No API Key)**
3. Add URLhaus malware URL checking
4. Improve domain reputation scoring

### **Phase 3: Free API Integrations**
5. Add PhishTank phishing URL checking
6. Add Google Safe Browsing
7. Add EmailRep.io email reputation

### **Phase 4: Advanced Features**
8. Add IPQualityScore fraud detection
9. Implement email header fetching for IP extraction
10. Add threat intelligence caching

---

## 📊 **Expected Results After Fixes**

### **For Outlook.com Emails:**
- ✅ Domain: outlook.com
- ✅ Domain Age: ~30 years (created 1994)
- ✅ Registrar: MarkMonitor, Inc.
- ✅ Country: US
- ✅ VirusTotal: 0 detections
- ✅ Reputation: Clean/Legitimate
- ❌ IP Address: Not available (Outlook limitation)
- ❌ Geolocation: Not available (no IP)
- ❌ ISP: Not available (no IP)

### **For Phishing Emails from Your Test Accounts:**
- ✅ Domain: outlook.com (same as above)
- ✅ All domain data available
- ❌ IP still not available
- ✅ URL analysis will catch malicious links
- ✅ Content analysis will detect phishing patterns

---

## 🚀 **Next Steps**

1. **Run re-analysis script** to populate WHOIS data
2. **Test with new phishing email** to see updated intelligence
3. **Add URLhaus integration** (easiest win, no API key)
4. **Get PhishTank API key** and integrate
5. **Monitor API usage** and adjust as needed

---

**Note:** For production use, consider implementing:
- API response caching (reduce API calls)
- Rate limiting (respect API limits)
- Fallback mechanisms (if API is down)
- Async processing (don't block email sync)
