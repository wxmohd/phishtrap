"""
Background Email Sync Service
Automatically syncs emails from all connected users every 60 seconds.
"""

import time
import threading
from datetime import datetime
from sqlalchemy import select
from database.models import SessionLocal, ConnectedUser
from services.gmail_pipeline import sync_user_gmail
from services.outlook_pipeline import sync_user_outlook
from services.websocket_events import emit_sync_complete

class BackgroundSyncService:
    def __init__(self, interval=60):
        """
        Initialize background sync service.
        
        Args:
            interval: Sync interval in seconds (default: 60)
        """
        self.interval = interval
        self.running = False
        self.thread = None
        
    def start(self):
        """Start the background sync service."""
        if self.running:
            print("[BACKGROUND_SYNC] Already running")
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._sync_loop, daemon=True)
        self.thread.start()
        print(f"[BACKGROUND_SYNC] ✓ Started (syncing every {self.interval}s)")
        
    def stop(self):
        """Stop the background sync service."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        print("[BACKGROUND_SYNC] ✓ Stopped")
        
    def _sync_loop(self):
        """Main sync loop that runs in background thread."""
        while self.running:
            try:
                self._sync_all_users()
            except Exception as e:
                print(f"[BACKGROUND_SYNC] ⚠️ Error during sync: {e}")
            
            # Wait for next sync interval
            time.sleep(self.interval)
    
    def _sync_all_users(self):
        """Sync emails for all connected users."""
        total_imported = 0
        
        with SessionLocal() as session:
            # Get all active connected users
            users = session.execute(
                select(ConnectedUser).where(
                    ConnectedUser.revoked_at.is_(None)
                )
            ).scalars().all()
            
            if not users:
                print("[BACKGROUND_SYNC] No connected users to sync")
                return
            
            print(f"[BACKGROUND_SYNC] Syncing {len(users)} users...")
            
            for user in users:
                try:
                    # Only fetch emails received AFTER user connected (not historical emails)
                    if user.provider == 'google':
                        result = sync_user_gmail(
                            user.email, 
                            auto_reply=True,
                            after_timestamp=user.connected_at  # ⚡ Only new emails
                        )
                        imported = result.get('imported', 0)
                        total_imported += imported
                        print(f"[BACKGROUND_SYNC] Gmail {user.email}: {imported} new emails")
                    elif user.provider == 'microsoft':
                        result = sync_user_outlook(
                            user.email, 
                            auto_reply=True,
                            after_timestamp=user.connected_at  # ⚡ Only new emails
                        )
                        imported = result.get('imported', 0)
                        total_imported += imported
                        print(f"[BACKGROUND_SYNC] Outlook {user.email}: {imported} new emails")
                except Exception as e:
                    print(f"[BACKGROUND_SYNC] ⚠️ Failed to sync {user.email}: {e}")
            
            print(f"[BACKGROUND_SYNC] ✓ Sync complete at {datetime.now().strftime('%H:%M:%S')}")
            
            # Emit WebSocket event if new emails were imported
            if total_imported > 0:
                emit_sync_complete({
                    'imported': total_imported,
                    'timestamp': datetime.now().isoformat()
                })
                print(f"[BACKGROUND_SYNC] 📡 Emitted WebSocket event: {total_imported} new emails")


# Global instance
_sync_service = None

def start_background_sync(interval=60):
    """Start the background sync service."""
    global _sync_service
    if _sync_service is None:
        _sync_service = BackgroundSyncService(interval=interval)
    _sync_service.start()
    return _sync_service

def stop_background_sync():
    """Stop the background sync service."""
    global _sync_service
    if _sync_service:
        _sync_service.stop()
