# database/models.py
from datetime import datetime
import os
import sqlite3
from sqlalchemy import (
    create_engine, Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Float
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# --- SQLite location (relative to repo root) ---
DB_PATH = os.path.join(os.path.dirname(__file__), "phishtrap.db")
ENGINE = create_engine(
    f"sqlite:///{DB_PATH}",
    echo=False,
    future=True,
    connect_args={
        "timeout": 30,  # Wait up to 30 seconds for lock
        "check_same_thread": False  # Allow multi-threading
    }
)

Base = declarative_base()
SessionLocal = sessionmaker(bind=ENGINE, autoflush=False, autocommit=False, future=True)

# ----------------- MODELS -----------------

class Email(Base):
    __tablename__ = "emails"

    id          = Column(Integer, primary_key=True)
    ext_id      = Column(String, nullable=True)

    subject     = Column(String, nullable=True)
    sender      = Column(String, nullable=True)
    recipient   = Column(String, nullable=True)
    body_text   = Column(Text,   nullable=True)
    body_html   = Column(Text,   nullable=True)

    received_at = Column(DateTime, default=datetime.utcnow, index=True)
    replied     = Column(Boolean, default=False)
    replied_at  = Column(DateTime, nullable=True)  # When AI replied

    # AI annotations (optional)
    ai_label       = Column(String(32), nullable=True)
    ai_score       = Column(Integer, nullable=True)   # keep simple for now
    ai_explanation = Column(Text, nullable=True)
    ai_reply_text  = Column(Text, nullable=True)  # The actual reply sent by AI bot

    # Review queue fields
    review_status      = Column(String(32), default='auto_processed')  # 'auto_processed', 'pending_review', 'admin_approved', 'admin_rejected'
    admin_notified_at  = Column(DateTime, nullable=True)
    admin_reviewed_at  = Column(DateTime, nullable=True)
    admin_decision     = Column(String(50), nullable=True)  # 'approve_reply', 'mark_legit', 'blocklist_sender'
    blocked            = Column(Boolean, default=False)  # True if sender is blocklisted
    
    # Thread/conversation tracking
    parent_email_id    = Column(Integer, ForeignKey('emails.id'), nullable=True)  # Link to original email if this is a reply

    links       = relationship("Link", back_populates="email", cascade="all, delete-orphan")
    sender_intel = relationship("SenderIntelligence", back_populates="email", uselist=False, cascade="all, delete-orphan")
    
    # Thread relationships
    parent = relationship("Email", remote_side=[id], backref="replies", foreign_keys=[parent_email_id])


class Link(Base):
    __tablename__ = "links"

    id         = Column(Integer, primary_key=True)
    email_id   = Column(Integer, ForeignKey("emails.id"), index=True)
    url        = Column(String,  nullable=False)

    # Basic status
    status     = Column(String,  nullable=True)               # e.g. 'clicked', 'blocked', 'error', 'analyzed'
    fetched_at = Column(DateTime, nullable=True, index=True)  # when Selenium/HTTP fetched
    
    # Risk assessment
    risk_score = Column(Integer, nullable=True)               # 0-100 risk score
    risk_level = Column(String, nullable=True)                # 'low', 'medium', 'high'
    
    # Brand impersonation
    impersonated_brand = Column(String, nullable=True)        # 'Microsoft', 'PayPal', 'Bank', 'Generic'
    brand_logo_url = Column(String, nullable=True)            # URL to brand logo
    
    # Sandbox analysis results
    sandbox_verdict = Column(Text, nullable=True)             # JSON: credential_harvest, downloads_file, redirects, etc.
    final_url = Column(String, nullable=True)                 # Final destination after redirects
    redirect_count = Column(Integer, nullable=True, default=0) # Number of redirects
    
    # Geolocation & hosting
    country_code = Column(String, nullable=True)              # 'NL', 'RU', 'US'
    country_flag = Column(String, nullable=True)              # Unicode flag emoji
    hosting_ip = Column(String, nullable=True)                # IP address
    
    # Campaign tracking
    campaign_id = Column(String, nullable=True)               # Links same campaign together
    first_seen = Column(DateTime, nullable=True)              # When first detected
    
    # Analysis metadata
    analysis_complete = Column(Boolean, default=False)        # Whether full analysis is done
    analyzed_at = Column(DateTime, nullable=True)             # When analysis completed
    
    email      = relationship("Email", back_populates="links")


class ConnectedUser(Base):
    """
    Tracks users who connected the AI bot via OAuth (or other identity).
    Active == not revoked (revoked_at is NULL).
    """
    __tablename__ = "connected_users"

    id           = Column(Integer, primary_key=True)
    email        = Column(String, nullable=False, unique=True, index=True)
    provider     = Column(String, nullable=False, default="google")  # 'google', 'microsoft', etc.
    connected_at = Column(DateTime, default=datetime.utcnow)
    revoked_at   = Column(DateTime, nullable=True)
    meta         = Column(Text, nullable=True)  # JSON metadata (optional)


class Blocklist(Base):
    """
    Tracks blocklisted email senders.
    Can be per-user or global.
    """
    __tablename__ = "blocklist"

    id              = Column(Integer, primary_key=True)
    blocked_sender  = Column(String, nullable=False, index=True)
    recipient_email = Column(String, nullable=True, index=True)  # NULL for global blocks
    blocked_at      = Column(DateTime, default=datetime.utcnow)
    blocked_by      = Column(String, nullable=True)
    reason          = Column(Text, nullable=True)
    is_domain       = Column(Boolean, default=False)
    is_global       = Column(Boolean, default=False)  # True if global block


class SenderIntelligence(Base):
    """
    Stores comprehensive threat intelligence for email senders.
    Includes geolocation, IP reputation, domain analysis, and threat feed data.
    """
    __tablename__ = "sender_intelligence"

    id = Column(Integer, primary_key=True)
    email_id = Column(Integer, ForeignKey("emails.id"), index=True, nullable=False)
    
    # Email header analysis
    sender_ip = Column(String, nullable=True, index=True)
    sender_domain = Column(String, nullable=True, index=True)
    email_headers = Column(Text, nullable=True)  # JSON of relevant headers
    
    # Geolocation data
    country = Column(String, nullable=True)
    country_code = Column(String(2), nullable=True)
    city = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    isp = Column(String, nullable=True)
    asn = Column(String, nullable=True)
    
    # IP reputation
    is_vpn = Column(Boolean, default=False)
    is_proxy = Column(Boolean, default=False)
    is_tor = Column(Boolean, default=False)
    abuse_score = Column(Integer, nullable=True)  # 0-100 from AbuseIPDB
    abuse_reports_count = Column(Integer, nullable=True)
    ip_reputation = Column(String, nullable=True)  # 'clean', 'suspicious', 'malicious'
    
    # Domain intelligence
    domain_age_days = Column(Integer, nullable=True)
    domain_registrar = Column(String, nullable=True)
    domain_country = Column(String, nullable=True)
    privacy_protected = Column(Boolean, default=False)
    ssl_valid = Column(Boolean, default=False)
    
    # Threat intelligence feeds
    virustotal_detections = Column(Integer, nullable=True)  # X/92 vendors
    virustotal_categories = Column(Text, nullable=True)  # JSON array
    urlhaus_listed = Column(Boolean, default=False)
    phishtank_listed = Column(Boolean, default=False)
    alienvault_tags = Column(Text, nullable=True)  # JSON array
    
    # Overall assessment
    threat_level = Column(String, nullable=True)  # 'low', 'medium', 'high', 'critical'
    confidence_score = Column(Float, nullable=True)  # 0.0 - 1.0
    risk_factors = Column(Text, nullable=True)  # JSON array of detected risks
    
    # Metadata
    analyzed_at = Column(DateTime, default=datetime.utcnow, index=True)
    analysis_version = Column(String, default='1.0')  # Track intel system version
    
    # Relationship
    email = relationship("Email", back_populates="sender_intel")

# ----------------- UTILITIES -----------------

def init_db() -> None:
    """Create tables if they don't exist."""
    Base.metadata.create_all(ENGINE)

def _table_exists(cur, table: str) -> bool:
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    )
    return cur.fetchone() is not None

def _col_exists(cur, table: str, col: str) -> bool:
    cols = [r[1] for r in cur.execute(f"PRAGMA table_info({table})")]
    return col in cols

def ensure_columns() -> None:
    """
    Lightweight dev-only migration to add missing tables/columns if the DB file is older.
    Safe to run multiple times.
    """
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    # Ensure 'emails' table columns
    if _table_exists(cur, "emails"):
        if not _col_exists(cur, "emails", "ext_id"):
            cur.execute("ALTER TABLE emails ADD COLUMN ext_id TEXT")
        if not _col_exists(cur, "emails", "ai_label"):
            cur.execute("ALTER TABLE emails ADD COLUMN ai_label TEXT")
        if not _col_exists(cur, "emails", "ai_score"):
            cur.execute("ALTER TABLE emails ADD COLUMN ai_score INTEGER")
        if not _col_exists(cur, "emails", "ai_explanation"):
            cur.execute("ALTER TABLE emails ADD COLUMN ai_explanation TEXT")
        if not _col_exists(cur, "emails", "review_status"):
            cur.execute("ALTER TABLE emails ADD COLUMN review_status TEXT DEFAULT 'auto_processed'")
        if not _col_exists(cur, "emails", "admin_notified_at"):
            cur.execute("ALTER TABLE emails ADD COLUMN admin_notified_at DATETIME")
        if not _col_exists(cur, "emails", "admin_reviewed_at"):
            cur.execute("ALTER TABLE emails ADD COLUMN admin_reviewed_at DATETIME")
        if not _col_exists(cur, "emails", "admin_decision"):
            cur.execute("ALTER TABLE emails ADD COLUMN admin_decision TEXT")
        if not _col_exists(cur, "emails", "blocked"):
            cur.execute("ALTER TABLE emails ADD COLUMN blocked INTEGER DEFAULT 0")

    # Ensure 'links' table columns
    if _table_exists(cur, "links"):
        if not _col_exists(cur, "links", "status"):
            cur.execute("ALTER TABLE links ADD COLUMN status TEXT")
        if not _col_exists(cur, "links", "fetched_at"):
            cur.execute("ALTER TABLE links ADD COLUMN fetched_at DATETIME")

    # Ensure 'connected_users' table
    if not _table_exists(cur, "connected_users"):
        cur.execute("""
            CREATE TABLE connected_users (
                id INTEGER PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                provider TEXT NOT NULL DEFAULT 'google',
                connected_at DATETIME,
                revoked_at DATETIME,
                meta TEXT
            )
        """)
        cur.execute("CREATE INDEX idx_connected_users_email ON connected_users(email)")
    
    # Migrate from old auth_connections table if it exists
    if _table_exists(cur, "auth_connections") and not _table_exists(cur, "connected_users"):
        cur.execute("""
            CREATE TABLE  AS
            SELECT 
                id,
                email,
                provider,
                connected_at,
                CASE WHEN revoked = 1 THEN disconnected_at ELSE NULL END as revoked_at,
                NULL as meta
            FROM auth_connections
        """)
        cur.execute("CREATE UNIQUE INDEX idx_connected_users_email ON connected_users(email)")

    con.commit()
    con.close()
