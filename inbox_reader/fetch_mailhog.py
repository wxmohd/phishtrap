# inbox_reader/fetch_mailhog.py

import re
import requests
from datetime import datetime

from database.models import SessionLocal, Email, Link

MAILHOG_API = "http://127.0.0.1:8025/apAI Bot Reply
📧 Original Phishing Email
Subject: Employment Confirmation Required
From: phishing_testt1@outlook.com
To: d3m01231@outlook.com
Received: 2025-11-30 11:05:08
AI Classification: PHISHING (93.0% confidence)
Email Body:


Hello,Your application has been pre-approved.Before we can finalize your employment file, we require you to complete the onboarding form.👉 Complete Onboarding Formhttp://career-verify-platform.com/formPlease submit within 12 hours to avoid cancellation.HR Recruitment Team
🤖 AI Bot's Reply
Reply Sent At: 2025-11-30 06:05:22
Status: ✅ Sent Successfully
Reply Content:
i/v2/messages"

# simple URL finder
URL_REGEX = re.compile(r'https?://[^\s"\'<>]+')

def _extract_text_and_urls(mailhog_item):
    """Pulls a rough text body and URLs from a MailHog message JSON."""
    body_text = ""
    urls = set()

    # MailHog often puts the raw message under Raw.Data
    raw = (mailhog_item.get("Raw") or {}).get("Data") or ""
    if raw:
        body_text = raw
        for u in URL_REGEX.findall(raw):
            urls.add(u)

    # fallback to Content.Body if present
    content = mailhog_item.get("Content") or {}
    if not body_text and "Body" in content:
        body_text = content["Body"] or ""
        for u in URL_REGEX.findall(body_text):
            urls.add(u)

    return body_text, list(urls)

def fetch_mailhog_messages(filter_recipient: str | None = None) -> int:
    """
    Fetch messages from MailHog and store them in SQLite.
    If filter_recipient is given, only emails sent to that address are stored.
    Returns how many messages were processed.
    """
    resp = requests.get(MAILHOG_API, timeout=5)
    resp.raise_for_status()
    payload = resp.json()

    items = payload.get("items", [])
    processed = 0

    with SessionLocal() as db:
        for item in items:
            headers = (item.get("Content") or {}).get("Headers", {}) or {}

            # headers can be list or string depending on MailHog
            def _first(hkey):
                val = headers.get(hkey)
                if isinstance(val, list):
                    return val[0]
                return val or ""

            to_hdr = _first("To")
            if filter_recipient and filter_recipient not in to_hdr:
                # skip messages not for this user
                continue

            subject = _first("Subject")
            sender = _first("From")
            recipient = to_hdr

            # MailHog message id
            ext_id = item.get("ID") or item.get("Key")

            # body + urls
            body_text, urls = _extract_text_and_urls(item)

            # created time
            created = item.get("Created") or item.get("Time")
            try:
                received_at = datetime.fromisoformat(created.replace("Z", "+00:00")) if created else datetime.utcnow()
            except Exception:
                received_at = datetime.utcnow()

            # check if we already have this mail
            existing = db.execute(
                Email.__table__.select().where(Email.ext_id == ext_id)
            ).first()

            if existing:
                email_obj = db.get(Email, existing[0])
            else:
                email_obj = Email(
                    ext_id=ext_id,
                    subject=subject,
                    sender=sender,
                    recipient=recipient,
                    body_text=body_text,
                    received_at=received_at,
                )
                db.add(email_obj)
                db.flush()

            # add links
            for url in urls:
                dup = db.execute(
                    Link.__table__.select().where(
                        (Link.email_id == email_obj.id) & (Link.url == url)
                    )
                ).first()
                if not dup:
                    db.add(
                        Link(
                            email_id=email_obj.id,
                            url=url,
                            status=None,
                        )
                    )

            processed += 1

        db.commit()

    return processed
