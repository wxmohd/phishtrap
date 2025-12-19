# Database and Data Persistence Documentation

## Overview
PhishTrap uses **SQLite** as a lightweight, file-based database suitable for single-VM deployment. Database access is handled via **SQLAlchemy ORM**, providing structured models and consistent database operations.

---

## 🗄️ Database Configuration

### **Location & Setup**
```python
# database/models.py
DB_PATH = os.path.join(os.path.dirname(__file__), "phishtrap.db")

ENGINE = create_engine(
    f"sqlite:///{DB_PATH}",
    echo=False,  # Set to True for SQL query logging
    future=True,
    connect_args={
        "timeout": 30,  # Wait up to 30 seconds for database lock
        "check_same_thread": False  # Allow multi-threading
    }
)

Base = declarative_base()
SessionLocal = sessionmaker(bind=ENGINE, autoflush=False, autocommit=False, future=True)
```

### **Initialization**
```python
# dashboard/app.py
def create_app() -> Flask:
    init_db()          # Create tables if they don't exist
    ensure_columns()   # Add missing columns (lightweight migrations)
    # ...
```

---

## 📊 Database Schema

### **1. Email Table** - Core email storage

```python
class Email(Base):
    __tablename__ = "emails"
    
    # Primary identification
    id          = Column(Integer, primary_key=True)
    ext_id      = Column(String, nullable=True)  # External ID from Gmail/Outlook
    
    # Email content
    subject     = Column(String, nullable=True)
    sender      = Column(String, nullable=True)
    recipient   = Column(String, nullable=True)
    body_text   = Column(Text, nullable=True)
    body_html   = Column(Text, nullable=True)
    
    # Timestamps
    received_at = Column(DateTime, default=datetime.utcnow, index=True)
    replied     = Column(Boolean, default=False)
    replied_at  = Column(DateTime, nullable=True)
    
    # AI Classification
    ai_label       = Column(String(32), nullable=True)  # 'legit', 'suspicious', 'phishing'
    ai_score       = Column(Integer, nullable=True)     # 0-100 confidence score
    ai_explanation = Column(Text, nullable=True)        # Why AI classified this way
    ai_reply_text  = Column(Text, nullable=True)        # The actual reply sent by AI
    
    # Admin Review Queue
    review_status      = Column(String(32), default='auto_processed')
    # Values: 'auto_processed', 'pending_review', 'admin_approved', 'admin_rejected'
    admin_notified_at  = Column(DateTime, nullable=True)
    admin_reviewed_at  = Column(DateTime, nullable=True)
    admin_decision     = Column(String(50), nullable=True)
    # Values: 'approve_reply', 'mark_legit', 'blocklist_sender'
    blocked            = Column(Boolean, default=False)
    
    # Thread/Conversation Tracking
    parent_email_id    = Column(Integer, ForeignKey('emails.id'), nullable=True)
    
    # Relationships
    links       = relationship("Link", back_populates="email", cascade="all, delete-orphan")
    sender_intel = relationship("SenderIntelligence", back_populates="email", 
                                uselist=False, cascade="all, delete-orphan")
    parent = relationship("Email", remote_side=[id], backref="replies", 
                         foreign_keys=[parent_email_id])
```

**Example Data**:
```
┌────┬─────────────────┬──────────────────┬─────────┬──────────┬──────────────┬────────────┐
│ id │ ext_id          │ sender           │ subject │ ai_label │ ai_score     │ replied    │
├────┼─────────────────┼──────────────────┼─────────┼──────────┼──────────────┼────────────┤
│ 1  │ gmail_abc123    │ phish@evil.com   │ Verify  │ phishing │ 95           │ True       │
│ 2  │ AAMkADU...      │ legit@bank.com   │ Invoice │ legit    │ 10           │ False      │
└────┴─────────────────┴──────────────────┴─────────┴──────────┴──────────────┴────────────┘
```

---

### **2. Link Table** - Extracted URLs and analysis

```python
class Link(Base):
    __tablename__ = "links"
    
    id         = Column(Integer, primary_key=True)
    email_id   = Column(Integer, ForeignKey("emails.id"), index=True)
    url        = Column(String, nullable=False)
    
    # Basic status
    status     = Column(String, nullable=True)  # 'clicked', 'blocked', 'error', 'analyzed'
    fetched_at = Column(DateTime, nullable=True, index=True)
    
    # Risk assessment
    risk_score = Column(Integer, nullable=True)  # 0-100
    risk_level = Column(String, nullable=True)   # 'low', 'medium', 'high'
    
    # Brand impersonation detection
    impersonated_brand = Column(String, nullable=True)  # 'Microsoft', 'PayPal', 'Bank'
    brand_logo_url = Column(String, nullable=True)
    
    # Sandbox analysis
    sandbox_verdict = Column(Text, nullable=True)  # JSON: credential_harvest, downloads, etc.
    final_url = Column(String, nullable=True)      # After redirects
    redirect_count = Column(Integer, nullable=True, default=0)
    
    # Geolocation & hosting
    country_code = Column(String, nullable=True)  # 'NL', 'RU', 'US'
    country_flag = Column(String, nullable=True)  # Unicode flag emoji
    hosting_ip = Column(String, nullable=True)
    
    # Campaign tracking
    campaign_id = Column(String, nullable=True)   # Links same campaign together
    first_seen = Column(DateTime, nullable=True)
    
    # Analysis metadata
    analysis_complete = Column(Boolean, default=False)
    analyzed_at = Column(DateTime, nullable=True)
    
    email = relationship("Email", back_populates="links")
```

**Example Data**:
```
┌────┬──────────┬──────────────────────────┬────────────┬────────────┬──────────────┬──────────┐
│ id │ email_id │ url                      │ risk_score │ risk_level │ country_code │ campaign │
├────┼──────────┼──────────────────────────┼────────────┼────────────┼──────────────┼──────────┤
│ 1  │ 1        │ https://evil.com/phish   │ 95         │ high       │ RU           │ camp_001 │
│ 2  │ 1        │ https://malware.net/dl   │ 88         │ high       │ CN           │ camp_001 │
└────┴──────────┴──────────────────────────┴────────────┴────────────┴──────────────┴──────────┘
```

---

### **3. SenderIntelligence Table** - Threat intelligence

```python
class SenderIntelligence(Base):
    __tablename__ = "sender_intelligence"
    
    id = Column(Integer, primary_key=True)
    email_id = Column(Integer, ForeignKey("emails.id"), index=True, nullable=False)
    
    # Email header analysis
    sender_ip = Column(String, nullable=True, index=True)
    sender_domain = Column(String, nullable=True, index=True)
    email_headers = Column(Text, nullable=True)  # JSON
    
    # Geolocation data (from IP)
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
    virustotal_categories = Column(Text, nullable=True)     # JSON array
    urlhaus_listed = Column(Boolean, default=False)
    phishtank_listed = Column(Boolean, default=False)
    alienvault_tags = Column(Text, nullable=True)           # JSON array
    
    # Overall assessment
    threat_level = Column(String, nullable=True)  # 'low', 'medium', 'high', 'critical'
    confidence_score = Column(Float, nullable=True)  # 0.0 - 1.0
    risk_factors = Column(Text, nullable=True)  # JSON array
    
    # Metadata
    analyzed_at = Column(DateTime, default=datetime.utcnow, index=True)
    analysis_version = Column(String, default='1.0')
    
    email = relationship("Email", back_populates="sender_intel")
```

**Example Data**:
```
┌────┬──────────┬────────────────┬─────────┬──────┬─────────┬────────────┬──────────────┐
│ id │ email_id │ sender_ip      │ country │ city │ is_vpn  │ abuse_score│ threat_level │
├────┼──────────┼────────────────┼─────────┼──────┼─────────┼────────────┼──────────────┤
│ 1  │ 1        │ 45.67.89.123   │ Russia  │ Moscow│ True   │ 85         │ high         │
│ 2  │ 2        │ 8.8.8.8        │ USA     │ N/A   │ False  │ 0          │ low          │
└────┴──────────┴────────────────┴─────────┴──────┴─────────┴────────────┴──────────────┘
```

---

### **4. ConnectedUser Table** - OAuth user tracking

```python
class ConnectedUser(Base):
    __tablename__ = "connected_users"
    
    id           = Column(Integer, primary_key=True)
    email        = Column(String, nullable=False, unique=True, index=True)
    provider     = Column(String, nullable=False, default="google")  # 'google' or 'microsoft'
    connected_at = Column(DateTime, default=datetime.utcnow)
    revoked_at   = Column(DateTime, nullable=True)  # NULL = active, set = disconnected
    meta         = Column(Text, nullable=True)  # JSON with OAuth tokens
```

**Example Data**:
```
┌────┬─────────────────┬──────────┬────────────────────┬────────────┬──────────────┐
│ id │ email           │ provider │ connected_at       │ revoked_at │ meta         │
├────┼─────────────────┼──────────┼────────────────────┼────────────┼──────────────┤
│ 1  │ user@gmail.com  │ google   │ 2025-12-13 10:00   │ NULL       │ {"access...  │
│ 2  │ user@outlook.com│ microsoft│ 2025-12-13 11:00   │ NULL       │ {"access...  │
└────┴─────────────────┴──────────┴────────────────────┴────────────┴──────────────┘
```

---

### **5. Blocklist Table** - Sender blocking

```python
class Blocklist(Base):
    __tablename__ = "blocklist"
    
    id              = Column(Integer, primary_key=True)
    blocked_sender  = Column(String, nullable=False, index=True)
    recipient_email = Column(String, nullable=True, index=True)  # NULL = global
    blocked_at      = Column(DateTime, default=datetime.utcnow)
    blocked_by      = Column(String, nullable=True)
    reason          = Column(Text, nullable=True)
    is_domain       = Column(Boolean, default=False)  # Block entire domain?
    is_global       = Column(Boolean, default=False)  # Global vs per-user
```

**Example Data**:
```
┌────┬──────────────────┬─────────────────┬───────────┬──────────┬────────────┐
│ id │ blocked_sender   │ recipient_email │ is_domain │ is_global│ reason     │
├────┼──────────────────┼─────────────────┼───────────┼──────────┼────────────┤
│ 1  │ phish@evil.com   │ NULL            │ False     │ True     │ Known scam │
│ 2  │ spam.com         │ user@gmail.com  │ True      │ False    │ Personal   │
└────┴──────────────────┴─────────────────┴───────────┴──────────┴────────────┘
```

---

## 🔄 Database Operations

### **1. Creating Records**

```python
from database.models import SessionLocal, Email, Link

# Create new email
with SessionLocal() as session:
    email_obj = Email(
        ext_id="gmail_abc123",
        subject="Verify your account",
        sender="phish@evil.com",
        recipient="victim@company.com",
        body_text="Click here to verify...",
        received_at=datetime.utcnow(),
        ai_label="phishing",
        ai_score=95,
        ai_explanation="High confidence phishing attempt"
    )
    session.add(email_obj)
    session.flush()  # Get email_obj.id without committing
    
    # Add related link
    link = Link(
        email_id=email_obj.id,
        url="https://evil.com/phish",
        status="pending"
    )
    session.add(link)
    session.commit()
```

### **2. Querying Records**

```python
from sqlalchemy import select

# Simple query
with SessionLocal() as session:
    # Get email by ID
    email = session.get(Email, 1)
    
    # Query with filter
    phishing_emails = session.execute(
        select(Email).where(Email.ai_label == 'phishing')
    ).scalars().all()
    
    # Query with multiple conditions
    high_risk = session.execute(
        select(Email).where(
            Email.ai_label == 'phishing',
            Email.ai_score >= 80,
            Email.replied == False
        )
    ).scalars().all()
```

### **3. Updating Records**

```python
with SessionLocal() as session:
    email = session.get(Email, 1)
    
    # Update fields
    email.replied = True
    email.replied_at = datetime.utcnow()
    email.ai_reply_text = "Thank you for your email..."
    
    session.commit()
```

### **4. Deleting Records**

```python
with SessionLocal() as session:
    # Delete single record
    email = session.get(Email, 1)
    session.delete(email)
    
    # Bulk delete
    session.execute(
        delete(Email).where(Email.ai_label == 'legit')
    )
    
    session.commit()
```

### **5. Relationships & Joins**

```python
# Access related data via relationships
with SessionLocal() as session:
    email = session.get(Email, 1)
    
    # Access links (one-to-many)
    for link in email.links:
        print(f"URL: {link.url}, Risk: {link.risk_score}")
    
    # Access sender intelligence (one-to-one)
    if email.sender_intel:
        print(f"Sender IP: {email.sender_intel.sender_ip}")
        print(f"Country: {email.sender_intel.country}")
    
    # Access thread replies (self-referential)
    for reply in email.replies:
        print(f"Reply from: {reply.sender}")
```

### **6. Complex Queries with Joins**

```python
from sqlalchemy.orm import joinedload

# Eager load relationships to avoid N+1 queries
with SessionLocal() as session:
    emails = session.execute(
        select(Email).options(
            joinedload(Email.links),
            joinedload(Email.sender_intel)
        ).where(Email.ai_label == 'phishing')
    ).unique().scalars().all()
    
    for email in emails:
        # No additional queries needed - data already loaded
        print(f"Email: {email.subject}")
        print(f"Links: {len(email.links)}")
        print(f"Sender IP: {email.sender_intel.sender_ip if email.sender_intel else 'N/A'}")
```

---

## 📝 Real-World Examples from PhishTrap

### **Example 1: Gmail Pipeline - Store Email**

```python
# services/gmail_pipeline.py
with SessionLocal() as session:
    # Check if already exists
    existing = session.execute(
        select(Email).where(Email.ext_id == msg["ext_id"])
    ).scalar_one_or_none()
    
    if existing:
        continue  # Skip duplicates
    
    # Run AI classification
    classification = classify_email(
        subject=msg.get("subject"),
        body=msg.get("body_text"),
        urls=msg.get("urls", [])
    )
    
    # Create email record
    email_obj = Email(
        ext_id=msg["ext_id"],
        subject=msg.get("subject"),
        sender=msg.get("sender"),
        recipient=msg.get("recipient"),
        body_text=msg.get("body_text"),
        received_at=msg.get("received_at"),
        ai_label=classification["label"],
        ai_score=int(classification["score"] * 100),
        ai_explanation=classification["explanation"],
    )
    session.add(email_obj)
    session.flush()
    
    # Store URLs
    for url in msg.get("urls", []):
        link = Link(
            email_id=email_obj.id,
            url=url,
            status="pending"
        )
        session.add(link)
    
    session.commit()
```

### **Example 2: Dashboard - Get Emails with Pagination**

```python
# dashboard/app.py
@app.route("/")
def dashboard():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    with SessionLocal() as s:
        # Get active user emails
        active_user_emails = s.execute(
            select(ConnectedUser.email).where(
                ConnectedUser.revoked_at.is_(None)
            )
        ).scalars().all()
        
        # Get total count
        total_emails = s.execute(
            select(func.count(Email.id)).where(
                Email.recipient.in_(active_user_emails)
            )
        ).scalar()
        
        # Get paginated emails
        emails = s.execute(
            select(Email).where(
                Email.recipient.in_(active_user_emails)
            ).order_by(Email.received_at.desc())
            .limit(per_page)
            .offset((page - 1) * per_page)
        ).scalars().all()
        
        return render_template("dashboard.html", emails=emails, ...)
```

### **Example 3: Admin Review Queue**

```python
# dashboard/app.py
@app.route("/review/approve/<int:email_id>", methods=["POST"])
def approve_review(email_id):
    with SessionLocal() as s:
        email = s.get(Email, email_id)
        
        if not email or email.review_status != 'pending_review':
            flash("Email not found or already reviewed", "warning")
            return redirect(url_for("dashboard"))
        
        # Update review status
        email.review_status = 'admin_approved'
        email.admin_reviewed_at = datetime.utcnow()
        email.admin_decision = 'approve_reply'
        
        # Send auto-reply
        # ... (send reply logic)
        
        email.replied = True
        email.replied_at = datetime.utcnow()
        
        s.commit()
        flash("✓ Email approved and reply sent", "success")
```

### **Example 4: Sender Intelligence Analysis**

```python
# services/sender_intel.py
def analyze_sender(email_obj, session, sender_ip_from_headers=None):
    """Analyze sender and store intelligence."""
    
    # Check if already analyzed
    existing = session.execute(
        select(SenderIntelligence).where(
            SenderIntelligence.email_id == email_obj.id
        )
    ).scalar_one_or_none()
    
    if existing:
        return  # Skip if already analyzed
    
    # Extract sender IP
    sender_ip = sender_ip_from_headers or extract_ip_from_headers(email_obj)
    
    # Get geolocation
    geo_data = get_ip_geolocation(sender_ip)
    
    # Get IP reputation
    abuse_data = check_abuseipdb(sender_ip)
    
    # Create intelligence record
    intel = SenderIntelligence(
        email_id=email_obj.id,
        sender_ip=sender_ip,
        sender_domain=email_obj.sender.split('@')[1] if '@' in email_obj.sender else None,
        country=geo_data.get('country'),
        country_code=geo_data.get('country_code'),
        city=geo_data.get('city'),
        latitude=geo_data.get('latitude'),
        longitude=geo_data.get('longitude'),
        isp=geo_data.get('isp'),
        asn=geo_data.get('asn'),
        is_vpn=geo_data.get('is_vpn', False),
        is_proxy=geo_data.get('is_proxy', False),
        is_tor=geo_data.get('is_tor', False),
        abuse_score=abuse_data.get('abuseConfidenceScore'),
        abuse_reports_count=abuse_data.get('totalReports'),
        threat_level=calculate_threat_level(abuse_data, geo_data),
        analyzed_at=datetime.utcnow()
    )
    
    session.add(intel)
    session.commit()
```

---

## 🔧 Database Migrations

### **Lightweight Migration System**

PhishTrap uses a simple migration system for development:

```python
# database/models.py
def ensure_columns() -> None:
    """Add missing columns if DB is older. Safe to run multiple times."""
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    
    # Check if table exists
    if _table_exists(cur, "emails"):
        # Add missing columns
        if not _col_exists(cur, "emails", "ai_label"):
            cur.execute("ALTER TABLE emails ADD COLUMN ai_label TEXT")
        
        if not _col_exists(cur, "emails", "review_status"):
            cur.execute("ALTER TABLE emails ADD COLUMN review_status TEXT DEFAULT 'auto_processed'")
    
    con.commit()
    con.close()
```

### **Manual Migrations**

For complex schema changes, use SQL migration files:

```sql
-- migrations/add_parent_email_id.sql
ALTER TABLE emails ADD COLUMN parent_email_id INTEGER REFERENCES emails(id);
```

Run with:
```python
# run_migration.py
import sqlite3

con = sqlite3.connect('database/phishtrap.db')
with open('migrations/add_parent_email_id.sql') as f:
    con.executescript(f.read())
con.commit()
```

---

## 📊 Data Flow Summary

```
┌─────────────────────────────────────────────────────────────┐
│                    Data Persistence Flow                     │
└─────────────────────────────────────────────────────────────┘

1. Email Arrives (Gmail/Outlook API)
   │
   ▼
2. Parse & Normalize (gmail_client.py / microsoft_client.py)
   │
   ▼
3. Check Duplicate (SELECT WHERE ext_id = ?)
   │
   ▼
4. AI Classification (classify_email)
   │
   ▼
5. INSERT INTO emails (subject, sender, ai_label, ai_score, ...)
   │
   ▼
6. Extract URLs → INSERT INTO links
   │
   ▼
7. Analyze Sender → INSERT INTO sender_intelligence
   │
   ▼
8. Auto-Reply (if phishing ≥80%)
   │
   ▼
9. UPDATE emails SET replied=True, ai_reply_text=...
   │
   ▼
10. Dashboard Queries (SELECT with JOINs)
    │
    ▼
11. Display Real-Time Data (WebSocket updates)
```

---

## 🔍 Key Benefits

1. **Persistent Storage**: All data survives server restarts
2. **Audit Trail**: Complete history of emails, classifications, and admin decisions
3. **Relationships**: Easy access to related data (emails → links → intelligence)
4. **Indexing**: Fast queries on common fields (received_at, sender_ip, etc.)
5. **Transactions**: ACID compliance ensures data integrity
6. **ORM Benefits**: Type-safe, Pythonic database access
7. **Lightweight**: Single SQLite file, no separate database server needed

---

## 📁 Database File Location

```
/home/osboxes/phishtrap/database/phishtrap.db
```

**Backup**:
```bash
cp database/phishtrap.db database/phishtrap.db.backup
```

**View with SQLite CLI**:
```bash
sqlite3 database/phishtrap.db
.tables
.schema emails
SELECT * FROM emails LIMIT 5;
```

---

## Summary

PhishTrap's database layer provides:
- **5 core tables**: Email, Link, SenderIntelligence, ConnectedUser, Blocklist
- **SQLAlchemy ORM**: Type-safe, relationship-based access
- **SQLite backend**: Lightweight, file-based, ACID-compliant
- **Real persistence**: Dashboard always reflects stored pipeline results
- **Audit trail**: Complete history of all operations
- **Efficient queries**: Indexed fields, eager loading, pagination support

All pipeline results (email parsing, AI classification, threat intelligence, auto-replies) are permanently stored and queryable!
