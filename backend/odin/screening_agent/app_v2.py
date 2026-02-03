# HOW TO RUN:
# 1. cd to backend/odin/screening_agent
# 2. Run python app_v2.py

import sys
from pathlib import Path

# Fix import paths FIRST (3 levels up: screening_agent -> odin -> backend)
backend_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_root))

from flask import Flask, request, jsonify
from threading import Thread, Event
import time
import uuid

from odin.screening_agent.screening_agent_v2 import ScreeningAgentV2

# For testing
TEST_MODE = True  # Set to true to use test phone number (as the caller number)
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
Odin Screening Agent V2 is running!

Endpoints:
  POST /start - Start a screening session
  POST /stop  - Stop a screening session
  GET  /status - Get active sessions
  GET  /health - Health check
"""


@app.route('/start', methods=['POST'])
def start_screening():
    """Start a new screening session"""

    # Get parameters from request
    data = request.get_json() or {}
    caller_id = data.get('caller_id', f"call_{uuid.uuid4().hex[:8]}")
    caller_phone = data.get('caller_phone', 'unknown')

    # Use test number if in test mode
    if TEST_MODE:
        caller_phone = TEST_NUMBER
        print(f"[APP_V2] TEST MODE - Using preset number: {caller_phone}")

    # Create unique session ID
    session_id = f"{caller_phone}_{int(time.time())}_{uuid.uuid4().hex[:6]}"

    # Check if session already exists for this phone
    for sid, session in active_sessions.items():
        if session.get('caller_phone') == caller_phone:
            return jsonify({
                'error': 'Session already active for this phone number',
                'session_id': sid
            }), 409

    # Create the screening agent
    print(f"[APP_V2] Creating ScreeningAgentV2 for {caller_phone}")
    agent = ScreeningAgentV2(caller_id=caller_id, caller_number=caller_phone)
    stop_event = Event()

    def run_agent():
        """Run the agent in a thread"""
        try:
            agent.start()

            # Wait for agent to finish or stop event
            while agent._agent_thread and agent._agent_thread.is_alive():
                if stop_event.is_set():
                    agent.stop()
                    break
                time.sleep(0.5)

        except Exception as e:
            print(f"[APP_V2] ERROR: {e}")
        finally:
            # Clean up session
            if session_id in active_sessions:
                del active_sessions[session_id]
            print(f"[APP_V2] Session {session_id} ended")

    # Start the agent thread
    print(f"[APP_V2] Starting agent thread for session {session_id}")
    thread = Thread(target=run_agent, daemon=True)
    thread.start()

    # Store session
    active_sessions[session_id] = {
        'agent': agent,
        'thread': thread,
        'stop_event': stop_event,
        'started_at': time.time(),
        'caller_phone': caller_phone,
        'caller_id': caller_id
    }

    return jsonify({
        'status': 'started',
        'session_id': session_id,
        'caller_phone': caller_phone,
        'caller_id': caller_id
    }), 200


@app.route('/stop', methods=['POST'])
def stop_screening():
    """Stop a screening session"""

    data = request.get_json() or {}
    session_id = data.get('session_id')
    caller_phone = data.get('caller_phone')

    # Find session by ID or phone number
    session_to_end = None
    session_id_to_end = None

    if session_id and session_id in active_sessions:
        session_to_end = active_sessions[session_id]
        session_id_to_end = session_id
    elif caller_phone:
        for sid, session in active_sessions.items():
            if session.get('caller_phone') == caller_phone:
                session_to_end = session
                session_id_to_end = sid
                break

    if not session_to_end:
        return jsonify({
            'error': 'No active session found',
            'session_id': session_id,
            'caller_phone': caller_phone
        }), 404

    # Signal the agent to stop
    print(f"[APP_V2] Stopping session {session_id_to_end}")
    session_to_end['stop_event'].set()
    session_to_end['agent'].stop()

    return jsonify({
        'status': 'stopped',
        'session_id': session_id_to_end
    }), 200


@app.route('/status', methods=['GET'])
def status():
    """Get status of all active sessions"""
    sessions_info = []
    for session_id, session in active_sessions.items():
        agent = session['agent']
        sessions_info.append({
            'session_id': session_id,
            'caller_phone': session.get('caller_phone'),
            'caller_id': session.get('caller_id'),
            'state': agent.state.name,
            'call_status': agent.call_status,
            'questions_answered': len(agent.answers),
            'total_questions': len(agent.questions),
            'uptime': time.time() - session['started_at'],
            'started_at': time.ctime(session['started_at'])
        })

    return jsonify({
        'active_sessions': len(active_sessions),
        'sessions': sessions_info
    }), 200


@app.route('/session/<session_id>', methods=['GET'])
def get_session(session_id):
    """Get details of a specific session"""

    if session_id not in active_sessions:
        return jsonify({'error': 'Session not found'}), 404

    session = active_sessions[session_id]
    agent = session['agent']

    return jsonify({
        'session_id': session_id,
        'caller_phone': session.get('caller_phone'),
        'caller_id': session.get('caller_id'),
        'state': agent.state.name,
        'call_status': agent.call_status,
        'current_question_index': agent.current_question_index,
        'questions_answered': len(agent.answers),
        'total_questions': len(agent.questions),
        'answers': agent.answers,
        'callback_time': agent.callback_time,
        'uptime': time.time() - session['started_at'],
        'started_at': time.ctime(session['started_at'])
    }), 200


if __name__ == "__main__":
    try:
        print("=" * 60)
        print("Starting Odin Screening Agent V2 Flask app")
        print("=" * 60)
        print("\nEndpoints:")
        print("  POST /start   - Start a screening session")
        print("  POST /stop    - Stop a screening session")
        print("  GET  /status  - Get all active sessions")
        print("  GET  /session/<id> - Get specific session details")
        print("  GET  /health  - Health check")
        print(f"\nTEST_MODE: {TEST_MODE}")
        print("\nServer running on http://localhost:5001\n")
        print("=" * 60 + "\n")

        app.run(debug=True, port=5001, use_reloader=False)
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
        # Stop all active sessions
        for session_id, session in list(active_sessions.items()):
            session['stop_event'].set()
            session['agent'].stop()
            session['thread'].join(timeout=5)
        print("All sessions stopped.")
