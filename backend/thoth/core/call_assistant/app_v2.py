import sys
from pathlib import Path

# Add backend root to Python path
# app_v2.py is at: backend/thoth/core/call_assistant/app_v2.py
backend_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(backend_root))


from flask import Flask, request, jsonify
from threading import Thread, Event
from thoth.core.call_assistant.call_assistant_v2 import CallAssistantV2
import time
import os

app = Flask(__name__)

# Store active assistant sessions
active_sessions = {}


@app.route('/webhook/call-started', methods=['POST'])
def call_started():
    """Webhook endpoint triggered when a call starts"""
    data = request.json
    call_id = data.get('call_id')
    caller_phone = data.get('from')  # Extract caller phone number

    if not call_id:
        return jsonify({'error': 'call_id required'}), 400

    if call_id in active_sessions:
        return jsonify({'status': 'already running'}), 200

    # Use V2 assistant with multi-turn conversation support
    assistant = CallAssistantV2(caller_phone=caller_phone)
    stop_event = Event()

    def run_assistant():
        try:
            assistant.run_with_event(stop_event)
        except Exception as e:
            print(f"!!! Assistant error for call {call_id}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Always clean up the session
            print(f"Removing session for call {call_id}")
            if call_id in active_sessions:
                del active_sessions[call_id]

            os.system("cls" if os.name == "nt" else "clear")
            print(f"Session removed. Active sessions: {len(active_sessions)}")

    # Use daemon=True to prevent blocking Flask shutdown
    thread = Thread(target=run_assistant, daemon=True)
    thread.start()

    active_sessions[call_id] = {
        'assistant': assistant,
        'thread': thread,
        'stop_event': stop_event,
        'started_at': time.time(),
        'version': 'v2'  # Track which version is being used
    }

    return jsonify({
        'status': 'success',
        'message': f'Voice assistant V2 started for call {call_id}',
        'caller_phone': caller_phone,
        'version': 'v2'
    }), 200


@app.route('/webhook/call-ended', methods=['POST'])
def call_ended():
    """Webhook endpoint triggered when a call ends"""

    data = request.json
    call_id = data.get('call_id')

    if call_id not in active_sessions:
        return jsonify({'error': 'No active session found'}), 404

    # Get the stop event and signal it
    session = active_sessions[call_id]
    stop_event = session['stop_event']

    # Signal the assistant to stop (non-blocking)
    stop_event.set()

    # DON'T wait for cleanup - respond immediately
    return jsonify({
        'status': 'success',
        'message': f'Stop signal sent for call {call_id}',
        'version': session.get('version', 'unknown')
    }), 200


@app.route('/status', methods=['GET'])
def status():
    """Get status of all active sessions"""
    sessions_info = []
    for call_id, session in active_sessions.items():
        sessions_info.append({
            'call_id': call_id,
            'version': session.get('version', 'unknown'),
            'uptime': time.time() - session['started_at'],
            'started_at': time.ctime(session['started_at'])
        })

    return jsonify({
        'active_sessions': len(active_sessions),
        'sessions': sessions_info
    }), 200


if __name__ == '__main__':
    # Add shutdown handler
    try:
        print("Starting Flask app with CallAssistantV2 (multi-turn conversation support)")
        print("Endpoints:")
        print("  POST /webhook/call-started - Start a call session")
        print("  POST /webhook/call-ended - End a call session")
        print("  GET /status - View active sessions")
        print("\nServer running on http://localhost:5000\n")

        app.run(debug=True, port=5000, use_reloader=False)  # disable reloader for cleaner shutdown
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
        # Stop all active sessions
        for call_id, session in list(active_sessions.items()):
            session['stop_event'].set()
            session['thread'].join(timeout=5)
        print("All sessions stopped.")
