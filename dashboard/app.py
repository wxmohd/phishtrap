import os
from functools import wraps
from datetime import datetime

from flask import (
    Flask, render_template, redirect, url_for, request, session, flash
)
from sqlalchemy import select, func
from dotenv import load_dotenv
from werkzeug.security import check_password_hash, generate_password_hash
from authlib.integrations.flask_client import OAuth

from database.models import SessionLocal, Email, Link, ConnectedUser, Blocklist, init_db, ensure_columns
from services.pipeline import sync_from_mailhog
from services.gmail_pipeline import sync_user_gmail
from services.outlook_pipeline import sync_user_outlook
from services.blocklist import add_to_blocklist, remove_from_blocklist, get_blocklist
from services.auto_responder import generate_reply, create_reply_subject
from services.gmail_client import send_reply as send_gmail_reply
from services.microsoft_client import send_reply as send_outlook_reply, refresh_access_token
from services.background_sync import start_background_sync
from services.websocket_events import init_socketio
import json

load_dotenv()  # load .env from project root


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)
    return wrapper


def create_app() -> Flask:
    # DB
    init_db()
    ensure_columns()

    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-change-this!")
    
    # Add custom Jinja2 filter for parsing JSON
    @app.template_filter('from_json')
    def from_json_filter(value):
        """Parse JSON string to Python object."""
        if not value:
            return []
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return []
    
    # Add custom Jinja2 filter for URL analysis
    @app.template_filter('analyze_url')
    def analyze_url_filter(url):
        """Analyze URL for threats in templates."""
        if not url:
            return None
        try:
            from services.url_analyzer import analyze_url
            return analyze_url(url)
        except Exception as e:
            return None
    
    # Session configuration to prevent CSRF state mismatch
    app.config["SESSION_COOKIE_SECURE"] = False  # Set True in production with HTTPS
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["PERMANENT_SESSION_LIFETIME"] = 3600  # 1 hour

    # ---------------- Admin creds ----------------
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@phishtrap.local")
    raw_env_hash = os.getenv("ADMIN_PASSWORD_HASH", "").strip()
    try:
        _ = check_password_hash(raw_env_hash, "probe")
        ADMIN_PASSWORD_HASH = raw_env_hash
    except Exception:
        ADMIN_PASSWORD_HASH = generate_password_hash("admin123")

    # ---------------- OAuth (Google) -------------
    oauth = OAuth(app)

    google_client_id = os.getenv("GOOGLE_CLIENT_ID")
    google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    google_redirect_uri = os.getenv(
        "GOOGLE_REDIRECT_URI",
        "http://127.0.0.1:5000/oauth/google/callback",
    )

    oauth.register(
        name="google",
        client_id=google_client_id,
        client_secret=google_client_secret,
        access_token_url="https://oauth2.googleapis.com/token",
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={
            "scope": "openid email profile https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.send",
            "prompt": "select_account"
        },
    )

    # ---------------- OAuth (Microsoft) -------------
    microsoft_client_id = os.getenv("MICROSOFT_CLIENT_ID")
    microsoft_client_secret = os.getenv("MICROSOFT_CLIENT_SECRET")
    microsoft_tenant_id = os.getenv("MICROSOFT_TENANT_ID", "common")
    microsoft_redirect_uri = os.getenv(
        "MICROSOFT_REDIRECT_URI",
        "http://localhost:5000/oauth/microsoft/callback",
    )

    oauth.register(
        name="microsoft",
        client_id=microsoft_client_id,
        client_secret=microsoft_client_secret,
        server_metadata_url=f"https://login.microsoftonline.com/{microsoft_tenant_id}/v2.0/.well-known/openid-configuration",
        token_endpoint_auth_method="client_secret_post",
        client_kwargs={
            "scope": "openid email profile offline_access https://graph.microsoft.com/Mail.Read https://graph.microsoft.com/Mail.Send https://graph.microsoft.com/MailboxSettings.ReadWrite",
            "prompt": "select_account",
            "token_endpoint_auth_method": "client_secret_post"
        },
    )

    allowed_domain = os.getenv("ALLOWED_GOOGLE_DOMAIN", "").strip()

    # ---------------- User login (UX only; no local validation) -------------
    @app.route("/login", methods=["GET", "POST"])
    def user_login():
        if request.method == "POST":
            flash("Use Continue with Google for secure sign-in.", "info")
        return render_template("login.html")

    # ---------------- Admin login (validates) -------------------------------
    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        if request.method == "POST":
            email = request.form.get("email", "").strip()
            password = request.form.get("password", "")
            if email.lower() == ADMIN_EMAIL.lower() and check_password_hash(ADMIN_PASSWORD_HASH, password):
                session.permanent = True  # Use 1-hour timeout
                session["is_admin"] = True
                session["admin_email"] = email
                flash("Welcome back, admin.", "success")
                return redirect(url_for("dashboard"))
            flash("Invalid credentials.", "danger")
        return render_template("admin_login.html")

    @app.route("/logout")
    def logout():
        session.clear()
        flash("Logged out.", "info")
        return redirect(url_for("user_login"))

    # ---------------- Google OAuth flow -------------------------------------
    @app.route("/login/google")
    def google_login():
        session.permanent = True  # Make session persistent to prevent state mismatch
        redirect_uri = google_redirect_uri
        return oauth.google.authorize_redirect(redirect_uri)

    @app.route("/oauth/google/callback")
    def google_callback():
        # Exchange code -> tokens
        try:
            token = oauth.google.authorize_access_token()
        except Exception as e:
            print("[GOOGLE TOKEN ERROR]", e)
            flash("Google sign-in failed. Check client secret.", "danger")
            return redirect(url_for("user_login"))

        # Get user info from UserInfo endpoint
        try:
            resp = oauth.google.get("https://openidconnect.googleapis.com/v1/userinfo")
            userinfo = resp.json()
        except Exception as e:
            print("[USERINFO ERROR]", e)
            flash("Google sign-in failed. Try again.", "danger")
            return redirect(url_for("user_login"))

        email = (userinfo or {}).get("email")
        hd = (userinfo or {}).get("hd")

        if not email:
            flash("Google sign-in failed: no email returned.", "danger")
            return redirect(url_for("user_login"))

        if allowed_domain and hd and hd.lower() != allowed_domain.lower():
            flash("This Google account is not allowed.", "danger")
            return redirect(url_for("user_login"))

        # Store OAuth tokens for Gmail API access
        import json
        token_data = json.dumps({
            "access_token": token.get("access_token"),
            "refresh_token": token.get("refresh_token"),
            "expires_at": token.get("expires_at"),
            "token_type": token.get("token_type"),
        })
        
        with SessionLocal() as s:
            conn = s.execute(
                select(ConnectedUser).where(
                    ConnectedUser.email == email,
                )
            ).scalar_one_or_none()

            if conn:
                # User is reconnecting - delete ALL previous data for clean state
                print(f"[OAUTH] User {email} reconnecting - cleaning previous data...")
                
                # Get all email IDs for this user
                email_ids = [e.id for e in s.query(Email).filter(Email.recipient == email).all()]
                
                # Delete sender intelligence
                if email_ids:
                    from database.models import SenderIntelligence
                    s.query(SenderIntelligence).filter(
                        SenderIntelligence.email_id.in_(email_ids)
                    ).delete(synchronize_session=False)
                    
                    # Delete links
                    s.query(Link).filter(
                        Link.email_id.in_(email_ids)
                    ).delete(synchronize_session=False)
                
                # Delete all emails
                s.query(Email).filter(Email.recipient == email).delete()
                
                # Delete personal blocklist entries
                s.query(Blocklist).filter(
                    Blocklist.recipient_email == email,
                    Blocklist.is_global == False
                ).delete()
                
                print(f"[OAUTH] Cleaned all previous data for {email}")
                
                # Update user with new tokens
                conn.revoked_at = None
                conn.provider = "google"
                conn.meta = token_data
                conn.connected_at = datetime.utcnow()
            else:
                # New user - create fresh record
                conn = ConnectedUser(
                    email=email,
                    provider="google",
                    connected_at=datetime.utcnow(),
                    revoked_at=None,
                    meta=token_data,
                )
                s.add(conn)
            s.commit()

        session["user_email"] = email
        flash("Logged in successfully with Google.", "success")
        return render_template("oauth_success.html", provider="Google", email=email)

    # ---------------- Microsoft OAuth flow ----------------------------------
    @app.route("/login/microsoft")
    def microsoft_login():
        session.permanent = True  # Make session persistent to prevent state mismatch
        redirect_uri = microsoft_redirect_uri
        return oauth.microsoft.authorize_redirect(redirect_uri)

    @app.route("/oauth/microsoft/callback")
    def microsoft_callback():
        # Exchange code -> tokens
        try:
            # Skip issuer validation for multi-tenant apps
            token = oauth.microsoft.authorize_access_token(
                claims_options={
                    "iss": {"essential": False}
                }
            )
        except Exception as e:
            print("[MICROSOFT TOKEN ERROR]", e)
            flash("Microsoft sign-in failed. Check client secret.", "danger")
            return redirect(url_for("user_login"))

        # Get user info from ID token claims (more reliable than Graph API)
        try:
            # Parse the ID token to get user claims
            userinfo = token.get("userinfo")
            if not userinfo:
                # If userinfo not in token, try to parse id_token
                import jwt
                id_token = token.get("id_token")
                if id_token:
                    # Decode without verification (we already validated the token)
                    userinfo = jwt.decode(id_token, options={"verify_signature": False})
                else:
                    userinfo = {}
            
            print("[MICROSOFT USERINFO]", userinfo)  # Debug: see what we get
        except Exception as e:
            print("[MICROSOFT USERINFO ERROR]", e)
            flash("Microsoft sign-in failed. Try again.", "danger")
            return redirect(url_for("user_login"))

        # Try multiple fields to get email from ID token claims
        email = (
            (userinfo or {}).get("email") or 
            (userinfo or {}).get("preferred_username") or
            (userinfo or {}).get("upn") or
            (userinfo or {}).get("unique_name")
        )
        
        print(f"[MICROSOFT EMAIL] Extracted email: {email}")

        if not email:
            print("[MICROSOFT EMAIL ERROR] No email found in userinfo:", userinfo)
            flash("Microsoft sign-in failed: no email returned.", "danger")
            return redirect(url_for("user_login"))

        # Store OAuth tokens for Microsoft Graph API access
        import json
        token_data = json.dumps({
            "access_token": token.get("access_token"),
            "refresh_token": token.get("refresh_token"),
            "expires_at": token.get("expires_at"),
            "token_type": token.get("token_type"),
        })
        
        with SessionLocal() as s:
            conn = s.execute(
                select(ConnectedUser).where(
                    ConnectedUser.email == email,
                )
            ).scalar_one_or_none()

            if conn:
                # User is reconnecting - delete ALL previous data for clean state
                print(f"[OAUTH] User {email} reconnecting - cleaning previous data...")
                
                # Get all email IDs for this user
                email_ids = [e.id for e in s.query(Email).filter(Email.recipient == email).all()]
                
                # Delete sender intelligence
                if email_ids:
                    from database.models import SenderIntelligence
                    s.query(SenderIntelligence).filter(
                        SenderIntelligence.email_id.in_(email_ids)
                    ).delete(synchronize_session=False)
                    
                    # Delete links
                    s.query(Link).filter(
                        Link.email_id.in_(email_ids)
                    ).delete(synchronize_session=False)
                
                # Delete all emails
                s.query(Email).filter(Email.recipient == email).delete()
                
                # Delete personal blocklist entries
                s.query(Blocklist).filter(
                    Blocklist.recipient_email == email,
                    Blocklist.is_global == False
                ).delete()
                
                print(f"[OAUTH] Cleaned all previous data for {email}")
                
                # Update user with new tokens
                conn.revoked_at = None
                conn.provider = "microsoft"
                conn.meta = token_data
                conn.connected_at = datetime.utcnow()
            else:
                # New user - create fresh record
                conn = ConnectedUser(
                    email=email,
                    provider="microsoft",
                    connected_at=datetime.utcnow(),
                    revoked_at=None,
                    meta=token_data,
                )
                s.add(conn)
            s.commit()

        session["user_email"] = email
        flash("Logged in successfully with Microsoft.", "success")
        return render_template("oauth_success.html", provider="Microsoft", email=email)

    # ---------------- Dashboard ---------------------------------------------
    @app.route("/")
    @admin_required
    def dashboard():
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = 10
        
        with SessionLocal() as s:
            # Get list of currently connected user emails
            active_user_emails = s.execute(
                select(ConnectedUser.email).where(
                    ConnectedUser.revoked_at.is_(None)
                )
            ).scalars().all()
            
            # Only show emails from currently connected users
            if active_user_emails:
                # Get total count for pagination
                total_emails = s.execute(
                    select(func.count(Email.id)).where(
                        Email.recipient.in_(active_user_emails)
                    )
                ).scalar()
                
                # Get total count of replied emails (for counter)
                total_replied = s.execute(
                    select(func.count(Email.id)).where(
                        Email.recipient.in_(active_user_emails),
                        Email.replied == True
                    )
                ).scalar()
                
                # Get total count of all links (for counter)
                total_links = s.execute(
                    select(func.count(Link.id)).where(
                        Link.email_id.in_(
                            select(Email.id).where(Email.recipient.in_(active_user_emails))
                        )
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
                
                # Get pending reviews (only from connected users)
                pending_reviews = s.execute(
                    select(Email).where(
                        Email.review_status == 'pending_review',
                        Email.recipient.in_(active_user_emails)
                    ).order_by(Email.received_at.desc())
                ).scalars().all()
                
                # Get blocklist entries (only for connected users)
                blocklist_entries = s.execute(
                    select(Blocklist).where(
                        Blocklist.recipient_email.in_(active_user_emails) | 
                        (Blocklist.is_global == True)
                    ).order_by(Blocklist.blocked_at.desc()).limit(20)
                ).scalars().all()
            else:
                # No connected users - show nothing in emails tab
                emails = []
                pending_reviews = []
                blocklist_entries = []
                total_emails = 0
                total_replied = 0
                total_links = 0

            # Get recent emails for threat intelligence globe (limit 20) - ALWAYS show all emails
            from sqlalchemy.orm import joinedload
            from database.models import SenderIntelligence
            threat_emails = s.execute(
                select(Email).options(
                    joinedload(Email.sender_intel),
                    joinedload(Email.links)
                ).order_by(Email.received_at.desc()).limit(20)
            ).unique().scalars().all()
            
            # Count users with active connection
            connected_users = len(active_user_emails)
            
            # Get connected users for blocklist dropdown
            users = s.execute(
                select(ConnectedUser).where(
                    ConnectedUser.revoked_at.is_(None)
                )
            ).scalars().all()
            
        # Calculate pagination info
        total_pages = (total_emails + per_page - 1) // per_page if total_emails > 0 else 1
        
        return render_template(
            "dashboard.html",
            emails=emails,
            threat_emails=threat_emails,
            admin_email=session.get("admin_email"),
            connected_users=connected_users,
            pending_reviews=pending_reviews,
            page=page,
            total_pages=total_pages,
            total_emails=total_emails,
            total_replied=total_replied,
            total_links=total_links,
            per_page=per_page,
            blocklist_entries=blocklist_entries,
            users=users,
        )

    # Sync emails from MailHog
    @app.route("/sync-mailhog", methods=["POST"])
    @admin_required
    def sync_mailhog():
        auto_reply = request.form.get("auto_reply") == "on"
        try:
            result = sync_from_mailhog(limit=100, auto_reply=auto_reply)
            msg = f"Sync complete: {result['imported']} imported, {result['updated']} updated, {result['total_links']} links"
            if result.get('replies_sent', 0) > 0:
                msg += f", {result['replies_sent']} replies sent"
            if result.get('errors', 0) > 0:
                msg += f", {result['errors']} errors"
            flash(msg, "success")
        except Exception as e:
            flash(f"Sync failed: {str(e)}", "danger")
        return redirect(url_for("dashboard"))
    
    # Sync emails from connected users (Gmail and Outlook)
    @app.route("/sync-email", methods=["POST"])
    @admin_required
    def sync_email():
        """
        DISABLED: Manual sync is not needed - emails sync automatically every 60 seconds.
        Background sync service runs continuously and emits WebSocket events for real-time updates.
        """
        flash("⚠️ Manual sync is disabled. Emails sync automatically via WebSocket every 60 seconds.", "info")
        return redirect(url_for("dashboard"))
    
    # Manage connected users page
    @app.route("/manage-users")
    @admin_required
    def manage_users():
        """Display all connected users with management options."""
        with SessionLocal() as s:
            all_users = s.query(ConnectedUser).order_by(ConnectedUser.connected_at.desc()).all()
        
        return render_template(
            "manage_users.html",
            users=all_users,
            admin_email=session.get("admin_email", ADMIN_EMAIL)
        )
    
    # Disconnect user (delete from DB and clean up all data)
    @app.route("/disconnect-user", methods=["POST"])
    @admin_required
    def disconnect_user():
        """Completely disconnect a user and delete all their data."""
        email = request.form.get("email", "").strip().lower()
        if not email:
            flash("Email required", "warning")
            return redirect(url_for("manage_users"))
        
        with SessionLocal() as s:
            # Find the user
            user = s.query(ConnectedUser).filter(ConnectedUser.email == email).first()
            
            if not user:
                flash(f"User {email} not found.", "warning")
                return redirect(url_for("manage_users"))
            
            # Get all email IDs for this user (for cascading deletes)
            email_ids = [e.id for e in s.query(Email).filter(Email.recipient == email).all()]
            
            # Delete sender intelligence for these emails
            if email_ids:
                from database.models import SenderIntelligence
                deleted_intel = s.query(SenderIntelligence).filter(
                    SenderIntelligence.email_id.in_(email_ids)
                ).delete(synchronize_session=False)
                
                # Delete links for these emails
                deleted_links = s.query(Link).filter(
                    Link.email_id.in_(email_ids)
                ).delete(synchronize_session=False)
            else:
                deleted_intel = 0
                deleted_links = 0
            
            # Delete all emails associated with this user (cascades to relationships)
            deleted_emails = s.query(Email).filter(Email.recipient == email).delete()
            
            # Delete all personal blocklist entries for this user
            deleted_blocklist = s.query(Blocklist).filter(
                Blocklist.recipient_email == email,
                Blocklist.is_global == False
            ).delete()
            
            # Delete the user from connected_users
            s.delete(user)
            
            s.commit()
            
            flash(
                f"✅ Disconnected {email}. Removed {deleted_emails} emails, {deleted_links} links, {deleted_intel} intelligence records, and {deleted_blocklist} blocklist entries.",
                "success"
            )
        
        return redirect(url_for("manage_users"))
    
    # Revoke user access (admin-only) - DEPRECATED, use disconnect_user instead
    @app.route("/revoke-user", methods=["POST"])
    @admin_required
    def revoke_user():
        email = request.form.get("email", "").strip().lower()
        if not email:
            flash("Email required", "warning")
            return redirect(url_for("dashboard"))
        
        with SessionLocal() as s:
            conn = s.execute(
                select(ConnectedUser).where(
                    ConnectedUser.email == email,
                    ConnectedUser.revoked_at.is_(None),
                )
            ).scalar_one_or_none()
            if conn:
                # Mark user as revoked
                conn.revoked_at = datetime.utcnow()
                
                # Delete all emails associated with this user
                deleted_emails = s.query(Email).filter(Email.recipient == email).delete()
                
                # Delete all blocklist entries for this user
                deleted_blocklist = s.query(Blocklist).filter(
                    Blocklist.recipient_email == email,
                    Blocklist.is_global == False
                ).delete()
                
                s.commit()
                flash(f"Revoked access for {email}. Removed {deleted_emails} emails and {deleted_blocklist} blocklist entries.", "info")
            else:
                flash("No active connection found.", "warning")
        return redirect(url_for("dashboard"))
    
    # Sender Intelligence route
    @app.route("/intel/<int:email_id>")
    @admin_required
    def sender_intelligence(email_id):
        """Display detailed sender intelligence for an email."""
        from database.models import SenderIntelligence
        
        with SessionLocal() as s:
            email = s.get(Email, email_id)
            if not email:
                flash("Email not found", "error")
                return redirect(url_for("dashboard"))
            
            # Get conversation thread (parent and replies)
            thread_emails = []
            if email.parent_email_id:
                # This is a reply - get the parent
                parent = s.get(Email, email.parent_email_id)
                if parent:
                    thread_emails.append(parent)
                    # Get all replies to the parent
                    thread_emails.extend(parent.replies)
            elif email.replies:
                # This is the original - show it and all replies
                thread_emails.append(email)
                thread_emails.extend(email.replies)
            
            # Sort by received_at
            thread_emails.sort(key=lambda e: e.received_at if e.received_at else datetime.min)
            
            # Get sender intelligence (most recent if duplicates exist)
            intel = s.execute(
                select(SenderIntelligence)
                .where(SenderIntelligence.email_id == email_id)
                .order_by(SenderIntelligence.analyzed_at.desc())
            ).scalars().first()
            
            # Parse JSON fields
            risk_factors = []
            vt_categories = []
            map_data = None
            
            if intel:
                if intel.risk_factors:
                    try:
                        risk_factors = json.loads(intel.risk_factors)
                    except:
                        pass
                if intel.virustotal_categories:
                    try:
                        vt_categories = json.loads(intel.virustotal_categories)
                    except:
                        pass
                
                # Prepare map data
                if intel.latitude and intel.longitude:
                    # Determine circle color based on threat level
                    color_map = {
                        'critical': {'color': 'red', 'fillColor': '#f03'},
                        'high': {'color': 'orange', 'fillColor': '#f90'},
                        'medium': {'color': 'yellow', 'fillColor': '#ff0'},
                        'low': {'color': 'green', 'fillColor': '#0f0'}
                    }
                    colors = color_map.get(intel.threat_level, {'color': 'green', 'fillColor': '#0f0'})
                    
                    # Build popup content (with HTML escaping)
                    from html import escape
                    popup_parts = ['<b>Sender Location</b><br>']
                    if intel.city:
                        popup_parts.append(escape(str(intel.city)))
                    if intel.city and intel.country:
                        popup_parts.append(', ')
                    if intel.country:
                        popup_parts.append(escape(str(intel.country)))
                    if intel.sender_ip:
                        popup_parts.append('<br>IP: ' + escape(str(intel.sender_ip)))
                    
                    map_data = {
                        'latitude': intel.latitude,
                        'longitude': intel.longitude,
                        'popup': ''.join(popup_parts),
                        'color': colors['color'],
                        'fillColor': colors['fillColor']
                    }
            
            return render_template(
                "sender_intel.html",
                email=email,
                intel=intel,
                risk_factors=risk_factors,
                vt_categories=vt_categories,
                map_data=json.dumps(map_data) if map_data else None,
                thread_emails=thread_emails
            )
    
    # View AI Reply route
    @app.route("/ai-reply/<int:email_id>")
    @admin_required
    def view_ai_reply(email_id):
        """Display the AI bot's reply for an email."""
        with SessionLocal() as s:
            email = s.get(Email, email_id)
            if not email:
                flash("Email not found", "error")
                return redirect(url_for("dashboard"))
            
            if not email.replied or not email.ai_reply_text:
                flash("No AI reply found for this email", "warning")
                return redirect(url_for("dashboard"))
            
            return render_template(
                "ai_reply.html",
                email=email
            )
    
    # ---------------- Admin Review Actions ----------------------------------
    @app.route("/review/<int:email_id>/approve", methods=["POST"])
    @admin_required
    def approve_reply(email_id):
        """Admin approves auto-reply for uncertain email."""
        with SessionLocal() as s:
            email = s.get(Email, email_id)
            if not email or email.review_status != 'pending_review':
                flash("Email not found or already reviewed", "warning")
                return redirect(url_for("dashboard"))
            
            # Get connected user for this recipient
            user = s.execute(
                select(ConnectedUser).where(
                    ConnectedUser.email == email.recipient,
                    ConnectedUser.revoked_at.is_(None)
                )
            ).scalar_one_or_none()
            
            if not user:
                flash(f"No connected user found for {email.recipient}", "danger")
                return redirect(url_for("dashboard"))
            
            # Generate reply
            msg_data = {
                'subject': email.subject,
                'sender': email.sender,
                'body_text': email.body_text
            }
            reply_body = generate_reply(msg_data, email.ai_label)
            reply_subject = create_reply_subject(email.subject)
            
            # Parse OAuth token
            try:
                token_data = json.loads(user.meta or "{}")
                access_token = token_data.get("access_token")
            except:
                flash("Invalid OAuth token", "danger")
                return redirect(url_for("dashboard"))
            
            # Send reply based on provider
            success = False
            if user.provider == 'google':
                success = send_gmail_reply(
                    access_token=access_token,
                    to=email.sender,
                    subject=reply_subject,
                    body=reply_body
                )
            elif user.provider == 'microsoft':
                try:
                    success = send_outlook_reply(
                        access_token=access_token,
                        message_id=email.ext_id,
                        reply_body=reply_body,
                        reply_subject=reply_subject
                    )
                except Exception as e:
                    # If 401 error, try to refresh token
                    if "401" in str(e) or "Unauthorized" in str(e):
                        print(f"[APPROVE_REPLY] Token expired, attempting refresh...")
                        refresh_token = token_data.get("refresh_token")
                        if refresh_token:
                            new_token_data = refresh_access_token(refresh_token)
                            if new_token_data:
                                # Update database with new tokens
                                user.meta = json.dumps(new_token_data)
                                s.commit()
                                print(f"[APPROVE_REPLY] ✓ Token refreshed, retrying send...")
                                
                                # Retry with new token
                                try:
                                    success = send_outlook_reply(
                                        access_token=new_token_data.get("access_token"),
                                        message_id=email.ext_id,
                                        reply_body=reply_body,
                                        reply_subject=reply_subject
                                    )
                                except Exception as retry_error:
                                    print(f"[APPROVE_REPLY] ✗ Still failed after refresh: {retry_error}")
                                    success = False
                            else:
                                print(f"[APPROVE_REPLY] ✗ Token refresh failed")
                        else:
                            print(f"[APPROVE_REPLY] ✗ No refresh token available")
                    else:
                        print(f"[APPROVE_REPLY] ✗ Send error: {e}")
            
            if success:
                email.replied = True
                email.ai_reply_text = reply_body
                email.replied_at = datetime.utcnow()
                email.review_status = 'admin_approved'
                email.admin_reviewed_at = datetime.utcnow()
                email.admin_decision = 'approve_reply'
                
                # Reclassify as phishing (admin approved)
                original_score = email.ai_score
                email.ai_label = 'phishing'
                email.ai_explanation = f"Admin approved AI reply (original: {email.ai_label} {original_score}%)"
                
                s.commit()
                flash(f"✓ Reply sent to {email.sender}", "success")
            else:
                flash(f"✗ Failed to send reply to {email.sender}", "danger")
        
        return redirect(url_for("dashboard"))
    
    @app.route("/review/<int:email_id>/mark-legit", methods=["POST"])
    @admin_required
    def mark_legit(email_id):
        """Admin marks uncertain email as legitimate."""
        with SessionLocal() as s:
            email = s.get(Email, email_id)
            if not email or email.review_status != 'pending_review':
                flash("Email not found or already reviewed", "warning")
                return redirect(url_for("dashboard"))
            
            email.ai_label = 'legit'
            email.review_status = 'admin_rejected'
            email.admin_reviewed_at = datetime.utcnow()
            email.admin_decision = 'mark_legit'
            s.commit()
            
            flash(f"✓ Email marked as legitimate", "info")
        
        return redirect(url_for("dashboard"))
    
    @app.route("/review/<int:email_id>/mark-legit", methods=["POST"])
    @admin_required
    def mark_as_legit(email_id):
        """Admin marks email as legitimate (false positive)."""
        with SessionLocal() as s:
            email = s.get(Email, email_id)
            if not email or email.review_status != 'pending_review':
                flash("Email not found or already reviewed", "warning")
                return redirect(url_for("dashboard"))
            
            # Update email classification
            email.ai_label = 'legit'
            email.ai_score = 0
            email.ai_explanation = 'Admin override: marked as legitimate (false positive)'
            email.review_status = 'admin_approved'
            email.admin_reviewed_at = datetime.utcnow()
            email.admin_decision = 'mark_legit'
            s.commit()
            
            flash(f"✓ Email marked as legitimate: {email.subject[:50]}", "success")
        
        return redirect(url_for("dashboard"))
    
    @app.route("/review/<int:email_id>/blocklist", methods=["POST"])
    @admin_required
    def blocklist_from_review(email_id):
        """Admin blocklists sender from review queue."""
        with SessionLocal() as s:
            email = s.get(Email, email_id)
            if not email or email.review_status != 'pending_review':
                flash("Email not found or already reviewed", "warning")
                return redirect(url_for("dashboard"))
            
            # Add to blocklist
            add_to_blocklist(
                sender=email.sender,
                recipient=email.recipient,
                reason=f"Admin decision from review queue (email ID: {email_id})",
                blocked_by=session.get("admin_email", "admin"),
                is_global=False
            )
            
            # Update email
            email.blocked = True
            email.review_status = 'admin_rejected'
            email.admin_reviewed_at = datetime.utcnow()
            email.admin_decision = 'blocklist_sender'
            s.commit()
            
            flash(f"✓ Sender {email.sender} blocklisted for {email.recipient}", "success")
        
        return redirect(url_for("dashboard"))
    
    @app.route("/review/bulk-approve-high-confidence", methods=["POST"])
    @admin_required
    def bulk_approve_high_confidence():
        """Bulk approve all emails with 80%+ confidence."""
        with SessionLocal() as s:
            # Get all pending reviews with 80%+ confidence
            high_confidence_emails = s.execute(
                select(Email).where(
                    Email.review_status == 'pending_review',
                    Email.ai_score >= 80
                )
            ).scalars().all()
            
            if not high_confidence_emails:
                flash("No high-confidence emails to approve", "info")
                return redirect(url_for("dashboard"))
            
            approved_count = 0
            for email in high_confidence_emails:
                # Update status to auto-processed
                email.review_status = 'auto_processed'
                email.admin_reviewed_at = datetime.utcnow()
                email.admin_decision = 'bulk_approved_high_confidence'
                approved_count += 1
            
            s.commit()
            flash(f"✓ Bulk approved {approved_count} high-confidence emails (≥80%)", "success")
        
        return redirect(url_for("dashboard"))
    
    # ---------------- Blocklist Management ----------------------------------
    @app.route("/block_sender", methods=["POST"])
    @admin_required
    def block_sender():
        """Quick block sender from email list."""
        sender = request.form.get("sender", "").strip().lower()
        
        if not sender:
            flash("Sender email required", "warning")
            return redirect(url_for("dashboard"))
        
        success = add_to_blocklist(
            sender=sender,
            recipient=None,  # Global block
            reason="Blocked from phishing email",
            blocked_by=session.get("admin_email", "admin"),
            is_global=True
        )
        
        if success:
            flash(f"✓ Blocked {sender} globally", "success")
        else:
            flash(f"✗ {sender} already in blocklist", "warning")
        
        return redirect(url_for("dashboard"))
    
    @app.route("/blocklist/add", methods=["POST"])
    @admin_required
    def add_blocklist():
        """Manually add sender to blocklist."""
        sender = request.form.get("sender", "").strip().lower()
        recipient = request.form.get("recipient", "").strip().lower()
        is_global = request.form.get("is_global") == "on"
        reason = request.form.get("reason", "").strip()
        
        if not sender:
            flash("Sender email required", "warning")
            return redirect(url_for("dashboard"))
        
        success = add_to_blocklist(
            sender=sender,
            recipient=recipient if recipient and not is_global else None,
            reason=reason,
            blocked_by=session.get("admin_email", "admin"),
            is_global=is_global
        )
        
        if success:
            scope = "globally" if is_global else f"for {recipient}"
            flash(f"✓ Added {sender} to blocklist {scope}", "success")
        else:
            flash(f"✗ {sender} already in blocklist", "warning")
        
        return redirect(url_for("dashboard"))
    
    @app.route("/blocklist/remove/<int:blocklist_id>", methods=["POST"])
    @admin_required
    def remove_blocklist(blocklist_id):
        """Remove sender from blocklist."""
        success = remove_from_blocklist(blocklist_id)
        
        if success:
            flash("✓ Removed from blocklist", "success")
        else:
            flash("✗ Blocklist entry not found", "warning")
        
        return redirect(url_for("dashboard"))
    
    # ---------------- WebSocket Test Endpoint (Debug) ---------------------------
    @app.route("/test-websocket")
    @admin_required
    def test_websocket():
        """Test WebSocket by emitting a test event."""
        import threading
        from services.websocket_events import emit_sync_complete
        
        def emit_after_response():
            import time
            time.sleep(0.1)  # Small delay to ensure response is sent
            emit_sync_complete({
                'imported': 99,
                'timestamp': datetime.now().isoformat(),
                'test': True
            })
        
        # Emit in background thread
        thread = threading.Thread(target=emit_after_response)
        thread.daemon = True
        thread.start()
        
        flash("✓ WebSocket test event emitted! Check browser console.", "success")
        return redirect(url_for("dashboard"))
    
    # Initialize WebSocket support and store the instance
    # Connection handlers are registered inside init_socketio()
    socketio_instance = init_socketio(app)
    
    # Start background email sync AFTER socketio is initialized
    # This enables automatic real-time email detection via WebSocket
    # Syncs every 15 seconds and emits WebSocket events to dashboard
    start_background_sync(interval=15)

    # Return app with socketio instance
    return app, socketio_instance
