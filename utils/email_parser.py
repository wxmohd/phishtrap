# utils/email_parser.py
from bs4 import BeautifulSoup
import re

def extract_links_from_html(html: str):
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    links = []
    # <a href="...">
    for a in soup.find_all("a", href=True):
        links.append(a["href"])
    # naive URL regex in plain text
    url_re = re.compile(r"https?://[^\s\"'>)]+")
    links += url_re.findall(soup.get_text(" "))
    # dedupe
    seen, out = set(), []
    for u in links:
        if u not in seen:
            seen.add(u); out.append(u)
    return out

def extract_links_from_text(text: str):
    if not text:
        return []
    url_re = re.compile(r"https?://[^\s\"'>)]+")
    return list(dict.fromkeys(url_re.findall(text)))
