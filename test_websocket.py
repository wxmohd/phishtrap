#!/usr/bin/env python3
"""
Test WebSocket functionality by manually triggering an event.
Run this AFTER the server is running to test if WebSocket events reach the browser.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from services.websocket_events import emit_new_email, emit_sync_complete
from datetime import datetime

print("=" * 60)
print("WebSocket Test Script")
print("=" * 60)
print()
print("This script will emit test WebSocket events.")
print("Make sure:")
print("  1. The Flask server is running (python3 main.py)")
print("  2. You have the dashboard open in your browser")
print("  3. Browser console is open (F12) to see logs")
print()
print("=" * 60)
print()

# Test 1: Emit a test email event
print("TEST 1: Emitting new_email event...")
emit_new_email({
    'id': 999,
    'subject': '🧪 TEST EMAIL - WebSocket Working!',
    'sender': 'test@websocket.com',
    'recipient': 'you@example.com',
    'ai_label': 'legit',
    'ai_score': 0,
    'received_at': datetime.utcnow().isoformat()
})

print()
print("TEST 2: Emitting sync_complete event...")
emit_sync_complete({
    'imported': 1,
    'timestamp': datetime.utcnow().isoformat()
})

print()
print("=" * 60)
print("✅ Test events emitted!")
print()
print("Check your browser:")
print("  - Console should show: [WebSocket] 🔔 Event received: new_email")
print("  - You should see a notification banner appear")
print("  - Dashboard should auto-refresh after 3 seconds")
print()
print("If you DON'T see anything in the browser:")
print("  1. Check browser console for connection errors")
print("  2. Make sure you restarted the Flask server")
print("  3. Hard refresh the browser (Ctrl+Shift+R)")
print("=" * 60)
