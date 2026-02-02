# HOW TO RUN:
# 1. cd to backend/odin/screening_agent
# 2. Run python app.py

import sys
from pathlib import Path

# Fix import paths FIRST (3 levels up: screening_agent -> odin -> backend)
backend_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_root))

from flask import Flask, request, jsonify
from threading import Thread
import time
import uuid

from odin.screening_agent.screening_agent import ScreeningAgent

# For testing
TEST_MODE = False  # Set to true to use test phone number (as the caller number)
TEST_NUMBER = "0415500152"

app = Flask(__name__)

# Store active screening sessions
active_sessions = {}


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint for startup verification"""
    return jsonify({'status': 'ok'}), 200


@app.route('/')
def home():
    return """
Odin Screening Agent is running!

Endpoints:
/status - get active sessions
"""


@app.route('/status', methods=['GET'])
def status():
    """Get status of all active sessions"""
    sessions_info = []
    for call_id, session in active_sessions.items():
        sessions_info.append({
            'call_id': call_id,
            'caller_phone': session.get('caller_phone'),
            'uptime': time.time() - session['started_at'],
            'started_at': time.ctime(session['started_at'])
        })

    return jsonify({
        'active_sessions': len(active_sessions),
        'sessions': sessions_info
    }), 200


if __name__ == "__main__":
    try:
        print("=" * 60)
        print("Starting Odin Screening Agent Flask app")
        print("=" * 60)
        print("\nEndpoints:")
        print("  GET /status - Get active sessions")
        print("  GET /health - Health check")
        print("\nServer running on http://localhost:5000\n")
        print("=" * 60 + "\n")

        app.run(debug=True, port=5000, use_reloader=False)
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
        # Stop all active sessions
        for call_id, session in list(active_sessions.items()):
            session['agent'].stop()
            session['thread'].join(timeout=5)
        print("All sessions stopped.")
