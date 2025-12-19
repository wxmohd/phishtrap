"""
WebSocket Event Emitter
Sends real-time updates to connected dashboard clients.
"""

from flask_socketio import SocketIO

# Global SocketIO instance (will be initialized by app)
socketio = None
flask_app = None

def init_socketio(app):
    """Initialize SocketIO with Flask app."""
    global socketio, flask_app
    flask_app = app
    # Disable verbose logging in production (set to True for debugging)
    # async_mode='threading' is required for background thread emissions
    socketio = SocketIO(
        app, 
        cors_allowed_origins="*",
        async_mode='threading',
        logger=False,
        engineio_logger=False
    )
    
    # Register connection handlers
    @socketio.on('connect')
    def handle_connect():
        print(f"[WEBSOCKET] 🔌 Client connected to namespace '/'")
        from flask import request
        sid = request.sid
        print(f"[WEBSOCKET] Client SID: {sid}")
    
    @socketio.on('disconnect')
    def handle_disconnect():
        print(f"[WEBSOCKET] 🔌 Client disconnected from namespace '/')")
    
    print("[WEBSOCKET] ✓ SocketIO initialized successfully")
    return socketio

def emit_new_email(email_data):
    """
    Emit new email event to all connected clients.
    Safe to call from any thread/background task.
    
    Args:
        email_data: Dictionary with email information
    """
    print(f"[WEBSOCKET] ========================================")
    print(f"[WEBSOCKET] emit_new_email() CALLED")
    print(f"[WEBSOCKET] Email data: {email_data}")
    
    if not socketio:
        print("[WEBSOCKET] ⚠️ Cannot emit new_email - socketio not initialized")
        return
    
    try:
        print(f"[WEBSOCKET] 📤 Emitting new_email event to all clients")
        print(f"[WEBSOCKET] Subject: {email_data.get('subject', 'N/A')}")
        
        # Check if there are connected clients
        try:
            from flask_socketio import rooms
            print(f"[WEBSOCKET] Active rooms: {rooms()}")
        except:
            pass
        
        # Use app context for background thread emissions
        if flask_app:
            with flask_app.app_context():
                socketio.emit('new_email', email_data, namespace='/')
        else:
            socketio.emit('new_email', email_data, namespace='/')
        
        print(f"[WEBSOCKET] ✅ new_email event emitted successfully!")
    except Exception as e:
        print(f"[WEBSOCKET] ❌ Error emitting new_email: {repr(e)}")
        import traceback
        traceback.print_exc()
    print(f"[WEBSOCKET] ========================================")

def emit_email_update(email_id, update_data):
    """
    Emit email update event (e.g., status change).
    Safe to call from any thread/background task.
    
    Args:
        email_id: ID of the email
        update_data: Dictionary with update information
    """
    if not socketio:
        print("[WEBSOCKET] ⚠️ Cannot emit email_update - socketio not initialized")
        return
    
    try:
        print(f"[WEBSOCKET] 📤 Emitting email_update for email {email_id}")
        
        # Use app context for background thread emissions
        if flask_app:
            with flask_app.app_context():
                socketio.emit('email_update', {
                    'email_id': email_id,
                    **update_data
                }, namespace='/')
        else:
            socketio.emit('email_update', {
                'email_id': email_id,
                **update_data
            }, namespace='/')
    except Exception as e:
        print(f"[WEBSOCKET] ❌ Error emitting email_update: {repr(e)}")

def emit_sync_complete(stats):
    """
    Emit sync complete event with statistics.
    Safe to call from any thread/background task.
    
    Args:
        stats: Dictionary with sync statistics
    """
    if not socketio:
        print("[WEBSOCKET] ⚠️ Cannot emit sync_complete - socketio not initialized")
        return
    
    try:
        print(f"[WEBSOCKET] ========================================")
        print(f"[WEBSOCKET] 📤 Emitting sync_complete event")
        print(f"[WEBSOCKET] Stats: {stats}")
        print(f"[WEBSOCKET] Imported: {stats.get('imported', 0)}")
        
        # Use app context for background thread emissions
        if flask_app:
            with flask_app.app_context():
                socketio.emit('sync_complete', stats, namespace='/')
        else:
            socketio.emit('sync_complete', stats, namespace='/')
        
        print(f"[WEBSOCKET] ✅ Event emitted successfully!")
        print(f"[WEBSOCKET] ========================================")
    except Exception as e:
        print(f"[WEBSOCKET] ❌ Error emitting sync_complete: {repr(e)}")
        import traceback
        traceback.print_exc()
