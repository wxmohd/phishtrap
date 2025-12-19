# main.py
from dashboard.app import create_app

app, socketio = create_app()

if __name__ == "__main__":
    # Run with SocketIO support for real-time updates
    # keep 127.0.0.1 because your Google redirect is http://localhost:5000/...
    # use_reloader=False prevents double-threading issues with background tasks
    if socketio:
        socketio.run(app, host="127.0.0.1", port=5000, debug=True, use_reloader=False, allow_unsafe_werkzeug=True)
    else:
        app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)
