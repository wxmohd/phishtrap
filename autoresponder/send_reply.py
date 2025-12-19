# autoresponder/send_reply.py
import os, smtplib
from email.mime.text import MIMEText
from app.logger import log
from database.models import SessionLocal, Email, ActionLog

SMTP_HOST = os.getenv("SMTP_HOST", "127.0.0.1")
SMTP_PORT = int(os.getenv("SMTP_PORT", "1025"))
SMTP_FROM = os.getenv("SMTP_FROM", "phishtrap@local")

TEMPLATE = """Hi,

Thank you for your email. Could you please resend the details and attachments?
Best regards,
User Support
"""

def main():
    session = SessionLocal()
    try:
        pending = session.query(Email).filter(Email.replied == False).all()
        if not pending:
            log.info("No emails to reply to.")
            return
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            for em in pending:
                msg = MIMEText(TEMPLATE)
                msg["Subject"] = f"Re: {em.subject}"
                msg["From"] = SMTP_FROM
                msg["To"] = em.sender
                s.send_message(msg)
                em.replied = True
                session.add(ActionLog(action="REPLY", details=f"Replied to {em.ext_id} -> {em.sender}"))
                log.info(f"Replied to {em.ext_id}")
        session.commit()
    except Exception as e:
        session.add(ActionLog(action="ERROR", details=str(e)))
        session.commit()
        log.exception("send_reply failed")
    finally:
        session.close()

if __name__ == "__main__":
    main()
