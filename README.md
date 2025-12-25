# PhishTrap

**AI-Powered Phishing Email Honeypot & Auto-Response System**

PhishTrap is an advanced cybersecurity research platform that ingests suspicious emails from Gmail and Outlook, classifies them using AI, automatically responds to phishing attempts, and provides real-time threat intelligence analytics. Built for the National Cyber Security Centre (NCSC) of Bahrain.

[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/flask-3.0+-green.svg)](https://flask.palletsprojects.com/)
[![Flask-SocketIO](https://img.shields.io/badge/socketio-5.3+-orange.svg)](https://flask-socketio.readthedocs.io/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## Features

### Core Capabilities
- **Multi-Provider Email Ingestion**: Gmail API & Microsoft Graph API with OAuth 2.0
- **AI Classification**: Heuristic-based phishing detection with confidence scoring (0-100%)
- **Real-Time WebSocket Updates**: Live email notifications in dashboard without refresh
- **Auto-Reply System**: Automated responses to high-confidence phishing (≥80%)
- **Threat Intelligence**: IP geolocation, VirusTotal, URLhaus, PhishTank, AlienVault OTX, AbuseIPDB
- **Admin Review Workflow**: Approve/reject/blocklist with decision tracking
- **URL Analysis**: Extraction, deduplication, sandbox analysis, redirect tracking
- **Interactive Dashboard**: Real-time KPIs, 3D threat globe visualization, email tables
- **Security Controls**: Admin-only routes, data isolation, session management
- **SQLite Database**: Persistent storage with automatic schema migrations

## Table of Contents

- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Development](#development)
- [Deployment](#deployment)
- [Contributing](#contributing)
- [License](#license)

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your OAuth credentials and API keys

# 3. Start PhishTrap
python3 main.py

# 4. Open browser
http://127.0.0.1:5000/admin/login

# 5. Login as admin
# Email: admin@ncsc.gov.bh
# Password: admin123

# 6. Connect email accounts
# Click "Manage Users" → "Connect Gmail" or "Connect Outlook"
# Complete OAuth flow

# 7. Watch real-time sync
# Dashboard updates automatically every 15 seconds
# New emails appear with WebSocket notifications
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         PhishTrap System                         │
└─────────────────────────────────────────────────────────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
        ▼                        ▼                        ▼
┌──────────────┐        ┌──────────────┐        ┌──────────────┐
│   Gmail API  │        │ Microsoft    │        │   Threat     │
│   OAuth 2.0  │        │ Graph API    │        │ Intelligence │
│              │        │   OAuth 2.0  │        │   APIs       │
└──────────────┘        └──────────────┘        └──────────────┘
        │                        │                        │
        └────────────────────────┼────────────────────────┘
                                 │
                                 ▼
                    ┌─────────────────────┐
                    │  Background Sync    │
                    │  (15s interval)     │
                    └─────────────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
        ▼                        ▼                        ▼
┌──────────────┐        ┌──────────────┐        ┌──────────────┐
│ Email Parser │        │ AI Classifier│        │ URL Analyzer │
│ & Dedup      │        │ (Heuristic)  │        │ & Sandbox    │
└──────────────┘        └──────────────┘        └──────────────┘
        │                        │                        │
        └────────────────────────┼────────────────────────┘
                                 │
                                 ▼
                    ┌─────────────────────┐
                    │  SQLite Database    │
                    │  (Email, Link,      │
                    │   SenderIntel)      │
                    └─────────────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
        ▼                        ▼                        ▼
┌──────────────┐        ┌──────────────┐        ┌──────────────┐
│ Auto-Reply   │        │  WebSocket   │        │    Admin     │
│ System       │        │  Events      │        │  Dashboard   │
└──────────────┘        └──────────────┘        └──────────────┘
```

### Core Components

#### Email Ingestion
- **services/gmail_client.py**: Gmail API client with OAuth 2.0
- **services/microsoft_client.py**: Microsoft Graph API client
- **services/gmail_pipeline.py**: Gmail email processing pipeline
- **services/outlook_pipeline.py**: Outlook email processing pipeline
- **services/background_sync.py**: Automatic 15-second sync loop

#### AI & Analysis
- **services/ai_classifier.py**: Heuristic phishing detection (keywords, URLs, patterns)
- **services/link_analyzer.py**: URL extraction, sandbox analysis, redirect tracking
- **services/sender_intel.py**: IP geolocation, reputation, WHOIS, threat intelligence
- **utils/email_parser.py**: HTML/text parsing, URL extraction with BeautifulSoup

#### Auto-Response
- **services/auto_responder.py**: Reply generation with templates
- **Auto-reply trigger**: Phishing emails ≥80% confidence

#### Real-Time Updates
- **services/websocket_events.py**: Flask-SocketIO event emitters
- **dashboard/templates/dashboard.html**: WebSocket client (socket.io.js)

#### Admin Interface
- **dashboard/app.py**: Flask routes, OAuth handlers, admin workflow
- **dashboard/templates/**: Jinja2 templates (dashboard, sender intel, AI reply)
- **dashboard/static/**: CSS, JavaScript, 3D threat globe

#### Database
- **database/models.py**: SQLAlchemy models (Email, Link, SenderIntelligence, ConnectedUser, Blocklist)
- **database/migrations.py**: Schema evolution and column additions

## Installation

### Prerequisites

- **Python 3.8+**
- **Gmail/Outlook Account** (for email ingestion)
- **Google OAuth 2.0 Credentials** (for Gmail)
- **Microsoft Azure App Registration** (for Outlook)
- **API Keys** (optional): VirusTotal, AbuseIPDB, AlienVault OTX, PhishTank

### Install Python Dependencies

```bash
pip install -r requirements.txt
```

**Key Dependencies:**
- `Flask` - Web framework
- `Flask-SocketIO` - Real-time WebSocket support
- `authlib` - OAuth 2.0 client
- `SQLAlchemy` - ORM
- `requests` - HTTP client
- `beautifulsoup4` - HTML parsing
- `python-dotenv` - Environment variables

## Configuration

### Environment Variables

Create `.env` file in project root:

```bash
# Flask Configuration
FLASK_ENV=development
SECRET_KEY=your-secret-key-change-in-production
DB_PATH=./database/phishtrap.db

# Admin Credentials
ADMIN_EMAIL=admin@ncsc.gov.bh
ADMIN_PASSWORD_HASH=pbkdf2:sha256:600000$...

# Google OAuth 2.0 (Gmail)
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://127.0.0.1:5000/oauth/google/callback
ALLOWED_GOOGLE_DOMAIN=  # Optional: restrict to specific domain

# Microsoft OAuth 2.0 (Outlook)
MICROSOFT_CLIENT_ID=your-azure-app-id
MICROSOFT_CLIENT_SECRET=your-azure-client-secret
MICROSOFT_REDIRECT_URI=http://127.0.0.1:5000/oauth/microsoft/callback
MICROSOFT_TENANT_ID=common  # or your tenant ID

# Threat Intelligence APIs (Optional)
VIRUSTOTAL_API_KEY=your-virustotal-api-key
ABUSEIPDB_API_KEY=your-abuseipdb-api-key
ALIENVAULT_OTX_API_KEY=your-otx-api-key
PHISHTANK_API_KEY=your-phishtank-api-key

# MailHog (Demo/Testing Only)
MAILHOG_API=http://127.0.0.1:8025/api/v2/messages
SMTP_HOST=127.0.0.1
SMTP_PORT=1025
```

### Generate Admin Password Hash

```python
from werkzeug.security import generate_password_hash
print(generate_password_hash("your-password"))
```

### Google OAuth 2.0 Setup (Gmail)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (e.g., "PhishTrap")
3. Enable **Gmail API**
4. Go to "Credentials" → "Create Credentials" → "OAuth 2.0 Client ID"
5. Application type: "Web application"
6. Add authorized redirect URI: `http://127.0.0.1:5000/oauth/google/callback`
7. Add scopes: `https://www.googleapis.com/auth/gmail.readonly`, `https://www.googleapis.com/auth/gmail.send`
8. Copy Client ID and Client Secret to `.env`

### Microsoft Azure Setup (Outlook)

1. Go to [Azure Portal](https://portal.azure.com/)
2. Navigate to "Azure Active Directory" → "App registrations" → "New registration"
3. Name: "PhishTrap"
4. Supported account types: "Accounts in any organizational directory and personal Microsoft accounts"
5. Redirect URI: `http://127.0.0.1:5000/oauth/microsoft/callback`
6. Go to "API permissions" → "Add permission" → "Microsoft Graph"
7. Add delegated permissions: `Mail.Read`, `Mail.Send`, `User.Read`
8. Go to "Certificates & secrets" → "New client secret"
9. Copy Application (client) ID and Client Secret to `.env`

## Usage

### Start PhishTrap

```bash
python3 main.py
```

Server starts on `http://127.0.0.1:5000` with:
- Background email sync (every 15 seconds)
- WebSocket server for real-time updates
- Admin dashboard

### Admin Workflow

#### 1. Login
```
http://127.0.0.1:5000/admin/login
Email: admin@ncsc.gov.bh
Password: admin123
```

#### 2. Connect Email Accounts
- Click **"Manage Users"** in sidebar
- Click **"Connect Gmail"** or **"Connect Outlook"**
- Complete OAuth flow
- Account appears in "Connected Users" list

#### 3. Monitor Dashboard
- **Overview Tab**: KPIs (Total Emails, Links, Replied, Connected Users)
- **Emails Tab**: Email list with AI classifications, badges, pagination
- **Threat Intel Tab**: 3D globe showing sender locations and threat levels
- **Review Queue**: Uncertain emails (60-79% confidence) awaiting admin decision

#### 4. Review Uncertain Emails
For emails in "Pending Admin Review":
- **Approve Reply**: Send auto-reply, mark as phishing
- **Mark as Legit**: Reclassify as legitimate (false positive)
- **Blocklist Sender**: Add to blocklist, prevent future emails

#### 5. View Threat Intelligence
- Click email → **"View Sender Intel"**
- See: IP geolocation, abuse score, VPN/Tor detection, VirusTotal results, URLhaus/PhishTank hits
- Risk factors and threat level calculation

#### 6. Manage Blocklist
- **Blocklist Tab**: View blocked senders
- Add manual entries with reason
- Global vs. per-user blocklists

### Auto-Reply System

**Automatic replies sent when:**
- AI label = `phishing`
- Confidence score ≥ 80%
- Email not already replied
- Auto-reply enabled

**Reply templates:**
- Randomized responses ("Thank you for contacting me...", "I'm interested...")
- Personalized based on subject (PayPal, bank, Amazon)
- Sent via Gmail API or Microsoft Graph API

### Real-Time Updates

**WebSocket notifications appear when:**
- New email arrives (purple gradient banner)
- Sync completes
- Dashboard auto-refreshes

**No manual refresh needed!**

## Development


### Project Structure

```
phishtrap/
├── main.py                         # Entry point
├── .env                            # Configuration (DO NOT COMMIT)
├── .gitignore                      # Git exclusions (secrets, DB)
├── requirements.txt                # Python dependencies
├── README.md                       # This file
├── dashboard/
│   ├── app.py                     # Flask routes, OAuth, admin workflow
│   ├── templates/                 # Jinja2 templates
│   │   ├── admin_login.html       # Admin login page
│   │   ├── dashboard.html         # Main dashboard (tabs, WebSocket)
│   │   ├── sender_intel.html      # Threat intelligence view
│   │   ├── ai_reply.html          # AI reply preview
│   │   ├── login.html             # User login page
│   │   ├── manage_users.html      # User management
│   │   └── oauth_success.html     # OAuth callback success
│   └── static/
│       ├── style-new.css          # Modern dark theme
│       ├── animated-bg.css        # Background effects
│       ├── dashboard-components.css # Component styles
│       ├── sidebar.css            # Sidebar navigation
│       ├── threat-intel-globe.css # Globe visualization styles
│       ├── threat-intel-globe.js  # 3D globe visualization
│       ├── three.min.js           # Three.js library
│       ├── OrbitControls.js       # Three.js controls
│       ├── logo.png               # Application logo
│       └── favicon.png            # Browser favicon
├── database/
│   ├── models.py                  # SQLAlchemy models
│   └── phishtrap.db               # SQLite database (created at runtime)
├── services/
│   ├── gmail_client.py            # Gmail API client
│   ├── microsoft_client.py        # Microsoft Graph API client
│   ├── gmail_pipeline.py          # Gmail email processing
│   ├── outlook_pipeline.py        # Outlook email processing
│   ├── ai_classifier.py           # Heuristic phishing detection
│   ├── ml_classifier.py           # ML model loader
│   ├── link_analyzer.py           # URL analysis & sandbox
│   ├── sender_intel.py            # Threat intelligence (IP, WHOIS, APIs)
│   ├── url_analyzer.py            # URL threat analysis
│   ├── auto_responder.py          # Reply generation
│   ├── background_sync.py         # 15-second sync loop
│   ├── websocket_events.py        # Flask-SocketIO events
│   ├── blocklist.py               # Sender blocklist management
│   ├── domain_whitelist.py        # Domain whitelist
│   ├── reply_detector.py          # Email thread detection
│   ├── admin_notifier.py          # Admin notifications
│   ├── outlook_blocklist_sync.py  # Outlook blocklist sync
│   ├── mailhog_client.py          # MailHog (testing only)
│   ├── mailhog_responder.py       # MailHog responder (testing only)
│   └── pipeline.py                # MailHog pipeline (testing only)
├── inbox_reader/
│   └── fetch_emails.py            # Email fetching utilities
├── utils/
│   └── email_parser.py            # HTML/text parsing, URL extraction
├── data/
│   └── GeoLite2-City.mmdb         # GeoIP database (61MB)
└── phish_model.joblib             # ML model (23MB)
```

### Database Schema

```sql
emails (
  id, ext_id, subject, sender, recipient,
  body_text, body_html, received_at,
  replied, replied_at, ai_reply_text,
  ai_label, ai_score, ai_explanation,
  review_status, admin_notified_at, admin_reviewed_at,
  admin_decision, blocked, parent_email_id
)

links (
  id, email_id, url, status, fetched_at,
  risk_score, risk_level, impersonated_brand,
  sandbox_verdict, final_url, redirect_count,
  country_code, country_flag, hosting_ip,
  campaign_id, analysis_complete, analyzed_at
)

sender_intelligence (
  id, email_id, sender_ip, sender_domain,
  country, country_code, city, latitude, longitude,
  isp, asn, abuse_score, reputation,
  is_vpn, is_proxy, is_tor,
  domain_age_days, privacy_protected,
  virustotal_detections, urlhaus_listed,
  phishtank_listed, otx_pulses,
  threat_level, confidence, risk_factors
)

connected_users (
  id, email, provider, connected_at, revoked_at, meta
)

blocklist (
  id, sender_email, recipient_email, reason,
  blocked_by, blocked_at, is_global
)
```

### Adding Features

1. **New Route**: Add to `dashboard/app.py`
2. **New Service**: Create in `services/`
3. **New Model**: Add to `database/models.py`
4. **New Template**: Add to `dashboard/templates/`

### Code Style

- Follow PEP 8
- Use type hints where appropriate
- Add docstrings to functions
- Keep functions focused and small

## Deployment

### Production Checklist

- [ ] Use PostgreSQL instead of SQLite
- [ ] Set `FLASK_ENV=production`
- [ ] Use strong `SECRET_KEY`
- [ ] Deploy with Gunicorn + Nginx
- [ ] Enable HTTPS
- [ ] Set up real mailbox integration (IMAP/Gmail/Graph)
- [ ] Train ML model for better classification
- [ ] Set up monitoring and logging
- [ ] Configure backups
- [ ] Implement rate limiting

### Example Production Setup

```bash
# Install Gunicorn
pip install gunicorn

# Run with Gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 "dashboard.app:create_app()"
```

### Docker (Future)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "dashboard.app:create_app()"]
```

### Development Setup

```bash
# Clone repository
git clone https://github.com/ncsc-bahrain/phishtrap.git
cd phishtrap

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt


```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- **Flask**: Web framework
- **Authlib**: OAuth client
- **SQLAlchemy**: ORM
- **Three.js**: 3D visualization
- **NCSC Bahrain**: Project sponsor

## Contact

- **Project Lead**: NCSC Bahrain
- **Email**: admin@ncsc.gov.bh
- **Website**: https://ncsc.gov.bh

## Roadmap

### Phase 1: Core (Complete)
- [x] Email ingestion from Gmail & Outlook (OAuth 2.0)
- [x] Heuristic AI classification with confidence scoring
- [x] Admin dashboard with real-time WebSocket updates
- [x] Google & Microsoft OAuth integration
- [x] SQLite database with automatic migrations
- [x] Auto-reply system (≥80% confidence)
- [x] Threat intelligence (VirusTotal, URLhaus, PhishTank, OTX, AbuseIPDB)
- [x] Admin review workflow (approve/reject/blocklist)
- [x] URL analysis & sandbox
- [x] 3D threat globe visualization
- [x] Background sync (15-second interval)

### Phase 2: Enhancement (Planned)
- [ ] ML model training (replace heuristics)
- [ ] Link clicking simulation with Selenium
- [ ] Advanced analytics & reporting
- [ ] Email campaign tracking
- [ ] Multi-language support
- [ ] Export reports (PDF/Excel)

### Phase 3: Scale (Future)
- [ ] PostgreSQL migration (production)
- [ ] Multi-tenancy support
- [ ] REST API
- [ ] Webhooks for external integrations
- [ ] Real-time alerting (Slack, Teams, email)
- [ ] Distributed deployment (Docker, Kubernetes)

## Known Issues

- **SQLite Limitations**: Not suitable for high concurrency (use PostgreSQL in production)
- **Token Refresh**: OAuth tokens expire after 1 hour (automatic refresh implemented but may need manual reconnect)
- **Rate Limiting**: No rate limiting on API calls (may hit provider limits)
- **Session Management**: Uses Flask sessions (needs Redis for multi-worker setups)
- **WebSocket Scaling**: Single-threaded (use Redis adapter for multiple workers)
- **Threat Intel APIs**: Optional and may have rate limits (free tiers)

## Tips

### Development
- **Check logs**: Flask prints detailed logs to console
- **Database inspection**: Use `sqlite3 database/phishtrap.db` or `sql_queries.sql`
- **Test classifier**: Run `python3 test_classifier.py`
- **WebSocket debugging**: Open browser console (F12) to see WebSocket events
- **OAuth troubleshooting**: Check redirect URIs match exactly (including port)

### Production
- **Backup database**: `cp database/phishtrap.db database/phishtrap.db.backup`
- **Monitor sync**: Check console for "[BACKGROUND_SYNC]" messages
- **API rate limits**: Monitor threat intelligence API usage
- **Token expiry**: Reconnect users if OAuth tokens expire
- **Security**: Change `SECRET_KEY` and `ADMIN_PASSWORD_HASH` in production

### Troubleshooting
- **No emails syncing**: Check OAuth connection in "Manage Users"
- **WebSocket not working**: Hard refresh browser (Ctrl+Shift+R)
- **401 errors**: OAuth token expired, reconnect account
- **Threat intel missing**: Check API keys in `.env`

---

**Built for cybersecurity senior project in Bahrain Polytechnic**
