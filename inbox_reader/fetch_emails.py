# inbox_reader/fetch_mailhog.py
import os, re, json, socket, ssl
from datetime import datetime
import requests
from urllib.parse import urlparse
import whois             # pip install python-whois
import dns.resolver      # pip install dnspython
# Optional: geoip2 for MaxMind local DB (pip install geoip2)
# from geoip2.database import Reader as GeoIPReader

from database.models import SessionLocal, Email, Link

MAILHOG_API = os.getenv("MAILHOG_API", "http://127.0.0.1:8025/api/v2/messages")
IPINFO_TOKEN = os.getenv("IPINFO_TOKEN", "")  # optional

URL_RE = re.compile(r"https?://[^\s'\"<>]+", re.I)

def extract_links_from_body(body: str):
    return URL_RE.findall(body or "")

def dns_lookup(domain):
    try:
        answers = dns.resolver.resolve(domain, 'A')
        ips = [str(a) for a in answers]
        return ips
    except Exception:
        return []

def whois_summary(domain):
    try:
        w = whois.whois(domain)
        # return a small summary (registrar, org, country)
        return json.dumps({
            "domain_name": w.domain_name,
            "registrar": w.registrar,
            "org": w.org if hasattr(w, "org") else None,
            "country": w.country
        }, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})

def ip_geoip_lookup(ip):
    # Demo: call ipinfo.io (or use MaxMind locally)
    if not IPINFO_TOKEN:
        return {}
    try:
        r = requests.get(f"https://ipinfo.io/{ip}/json", params={"token": IPINFO_TOKEN}, timeout=6)
        if r.ok:
            return r.json()
    except Exception:
        pass
    return {}

def parse_received_for_ip(received_header):
    # naive regex for the last IP in Received header
    if not received_header:
        return None
    m = re.search(r"\[?([0-9]{1,3}(?:\.[0-9]{1,3}){3})\]?", received_header)
    if m:
        return m.group(1)
    return None

def process_mailhog_message(m):
    # m is the JSON item from MailHog /api/v2/messages items
    content = m.get("Content", {})
    headers = content.get("Headers", {})
    to_list = headers.get("To", []) or []
    subject = headers.get("Subject", [""])[0]
    from_hdr = headers.get("From", [""])[0]
    # MailHog body: plain text or html
    body = content.get("Body", "") or ""
    received_raw = headers.get("Received", [""])[0] if headers.get("Received") else ""
    # Demo: custom attacker headers
    attacker_ip = headers.get("X-Attacker-IP", [None])[0] if headers.get("X-Attacker-IP") else None
    user_agent = headers.get("X-User-Agent", [None])[0] if headers.get("X-User-Agent") else None

    # fallback: try parse Received header
    if not attacker_ip:
        attacker_ip = parse_received_for_ip(received_raw)

    # find links
    links = extract_links_from_body(body)

    # store Email row
    with SessionLocal() as s:
        e = Email(
            ext_id = m.get("ID"),
            subject = subject[:255],
            sender = from_hdr[:255],
            recipient = ", ".join(to_list)[:255],
            body_text = body[:4000],
            received_at = datetime.utcnow(),
            replied = False,
        )
        # optional: attach attacker metadata to e if you added columns
        if attacker_ip:
            try:
                e.attacker_ip = attacker_ip
            except Exception:
                pass
        if user_agent:
            try:
                e.user_agent = user_agent
            except Exception:
                pass

        s.add(e)
        s.commit()
        s.refresh(e)

        # create Link rows and enrich each domain
        for url in links:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            link = Link(email_id=e.id, url=url, status=None, fetched_at=None)
            s.add(link)
            s.commit()
            s.refresh(link)

            # enrichment: dns, whois, http head
            ips = dns_lookup(domain)
            who = whois_summary(domain)
            http_head = {}
            try:
                r = requests.head(url, timeout=6, allow_redirects=True)
                http_head = {
                    "status_code": r.status_code,
                    "server": r.headers.get("Server"),
                    "content_type": r.headers.get("Content-Type")
                }
            except Exception:
                http_head = {"error": "HEAD failed"}

            # store enrichment in link.status or a new table/column
            try:
                link.status = json.dumps({"domain": domain, "ips": ips, "whois": who, "http": http_head})
                link.fetched_at = datetime.utcnow()
                s.add(link)
                s.commit()
            except Exception:
                s.rollback()

    return True

def fetch_and_process_all():
    r = requests.get(MAILHOG_API, timeout=10)
    r.raise_for_status()
    items = r.json().get("items", [])
    for m in items:
        # decide if this message should be processed (match recipient to connected users)
        # For demo, process all or add logic to match inbox_connections
        try:
            process_mailhog_message(m)
        except Exception as e:
            print("process error:", e)

if __name__ == "__main__":
    fetch_and_process_all()
