# sandbox/click_links.py
import requests, datetime
from app.logger import log
from database.models import SessionLocal, Link, ActionLog

TIMEOUT = 6  # short timeout; requests only (safe), no JS

def main():
    session = SessionLocal()
    try:
        links = session.query(Link).filter(Link.http_status.is_(None)).all()
        if not links:
            log.info("No uncrawled links.")
            return
        for lk in links:
            try:
                r = requests.get(lk.url, timeout=TIMEOUT, allow_redirects=True)
                lk.http_status = r.status_code
                lk.fetched_at = datetime.datetime.utcnow()
                session.add(ActionLog(action="CLICK", details=f"{lk.url} -> {r.status_code}"))
                log.info(f"Fetched {lk.url} -> {r.status_code}")
            except Exception as e:
                lk.http_status = -1
                lk.fetched_at = datetime.datetime.utcnow()
                session.add(ActionLog(action="ERROR", details=f"{lk.url}: {e}"))
                log.warning(f"Failed {lk.url}: {e}")
        session.commit()
    finally:
        session.close()

if __name__ == "__main__":
    main()
