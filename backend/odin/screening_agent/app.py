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
/webhook/call-started - to start a call. Args: 'call_id', 'from'
/webhook/call-ended - to end a call. Args: 'from'
/status - get active sessions
"""


@app.route('/webhook/call-started', methods=['GET', 'POST'])
def call_started():
    """Webhook endpoint triggered when a call starts via Custom URL"""

    # Get parameters from Custom URL
    caller_phone = request.args.get('from')

    # Use test number if in test mode
    if TEST_MODE:
        caller_phone = TEST_NUMBER
        print(f"APP.PY: TEST MODE - Using preset number: {caller_phone}")

    # Create UNIQUE call_id to prevent blocking repeat calls
    call_id = f"{caller_phone}_{int(time.time())}_{uuid.uuid4().hex[:6]}"

    # Check if call already in progress
    if call_id in active_sessions:
        return "<script>window.close();</script>", 200

    # Create and start screening agent
    print(f"APP.PY: Creating screening agent for {caller_phone}")
    screening_agent = ScreeningAgent(call_id, caller_phone)

    def run_agent():
        try:
            screening_agent.start()
            # Wait for the agent thread to complete
            if screening_agent._agent_thread:
                screening_agent._agent_thread.join()
        except Exception as e:
            print(f"[ERROR] {e}")
        finally:
            if call_id in active_sessions:
                del active_sessions[call_id]

    print("APP.PY: Starting screening agent thread.")
    thread = Thread(target=run_agent, daemon=True)
    thread.start()

    # Store session
    active_sessions[call_id] = {
        'agent': screening_agent,
        'thread': thread,
        'started_at': time.time(),
        'caller_phone': caller_phone
    }

    # Return simple HTML that closes immediately
    return "<script>setTimeout(function(){window.close();}, 1000);</script>", 200


@app.route('/webhook/call-ended', methods=['GET', 'POST'])
def call_ended():
    """Webhook endpoint triggered when a call ends"""
    caller_phone = request.args.get('from')

    # Find session by caller phone
    session_to_end = None
    call_id_to_end = None

    for cid, session in active_sessions.items():
        if session.get('caller_phone') == caller_phone:
            session_to_end = session
            call_id_to_end = cid
            break

    if not session_to_end:
        print(f"APP.PY: No active session found for caller {caller_phone}")
        return "<script>window.close();</script>", 404

    # Stop the screening agent
    agent = session_to_end['agent']
    agent.stop()

    print(f"APP.PY: Stop call requested for caller: {caller_phone}, call id: {call_id_to_end}")

    return "<script>window.close();</script>", 200


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
        print("  GET/POST /webhook/call-started - Start a screening session")
        print("  GET/POST /webhook/call-ended - End a screening session")
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
