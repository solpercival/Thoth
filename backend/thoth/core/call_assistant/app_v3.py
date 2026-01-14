import sys
from pathlib import Path

# Add backend root to Python path
# app_v3.py is at: backend/thoth/core/call_assistant/app_v3.py
backend_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(backend_root))

from flask import Flask, request, jsonify
from threading import Thread, Event
from thoth.core.call_assistant.call_assistant_v3 import CallAssistantV3
import time
import os
import uuid


RING_DURATION = 1.0
EXTENSION = "0147"

app = Flask(__name__)


# Store active assistant sessions
active_sessions = {}


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint for Electron app startup verification"""
    return jsonify({'status': 'ok'}), 200


@app.route('/webhook/call-started', methods=['GET', 'POST'])
def call_started():
    """Webhook endpoint triggered when a call starts via Custom URL"""
    print("\n" + "=" * 60)
    print("DEBUG: /webhook/call-started endpoint called")
    print("=" * 60)

    # Get parameters from Custom URL
    caller_display = request.args.get('call_id', 'unknown')
    caller_phone = request.args.get('from')
    
    # Create UNIQUE call_id to prevent blocking repeat calls
    call_id = f"{caller_phone}_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    print(f"DEBUG: display={caller_display}, call_id={call_id}, caller={caller_phone}")

    # Check if call already in progress
    if call_id in active_sessions:
        return "<script>window.close();</script>", 200

    # ============= AUTO-ANSWER THE CALL =============
    print(f"DEBUG: Auto-answering call from {caller_phone} on extension {EXTENSION}...")
    
    from thoth.core.call_assistant.call_flow_client import auto_answer_incoming_call
    
    time.sleep(RING_DURATION)
    
    answer_success = auto_answer_incoming_call(EXTENSION, caller_phone)
    
    if answer_success:
        print("✅ Call answered successfully via API")
    else:
        print("⚠️ Failed to auto-answer call (will continue anyway)")
    # ================================================

    # Create and start assistant
    print("DEBUG: Creating CallAssistantV3 instance...")
    assistant = CallAssistantV3(caller_phone=caller_phone, extension=EXTENSION)
    stop_event = Event()

    def run_assistant():
        print("DEBUG: run_assistant thread started")
        try:
            assistant.run_with_event(stop_event)
        except Exception as e:
            print(f"!!! Assistant error for call {call_id}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            print(f"Removing session for call {call_id}")
            if call_id in active_sessions:
                del active_sessions[call_id]
            print(f"✅ Session removed. Active sessions: {len(active_sessions)}")

    print("DEBUG: Starting assistant thread...")
    thread = Thread(target=run_assistant, daemon=True)
    thread.start()

    # Store session
    active_sessions[call_id] = {
        'assistant': assistant,
        'thread': thread,
        'stop_event': stop_event,
        'started_at': time.time(),
        'version': 'v3',
        'answered': answer_success,
        'caller_phone': caller_phone
    }

    # Return simple HTML that closes immediately
    return "<script>setTimeout(function(){window.close();}, 1000);</script>", 200


@app.route('/webhook/call-ended', methods=['GET', 'POST'])
@app.route('/webhook/call-ended', methods=['GET'])
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
        print(f"⚠️ No active session found for caller {caller_phone}")
        return "<script>window.close();</script>", 404

    # Signal the assistant to stop
    stop_event = session_to_end['stop_event']
    stop_event.set()
    
    print(f"✅ Stop signal sent for call {call_id_to_end}")

    return "<script>window.close();</script>", 200


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
        print("=" * 60)
        print("Starting Flask app with CallAssistantV3")
        print("LLM-driven conversation flow - no state machine!")
        print("=" * 60)
        print("\nEndpoints:")
        print("  GET/POST /webhook/call-started - Start a call session")
        print("  GET/POST /webhook/call-ended - End a call session")
        print("  GET /status - View active sessions")
        print("\nSupports both:")
        print("  - Custom URL (GET with query params)")
        print("  - CFD (POST with JSON body)")
        print("\nServer running on http://localhost:5000\n")
        print("=" * 60 + "\n")

        app.run(debug=True, port=5000, use_reloader=False)  # disable reloader for cleaner shutdown
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
        # Stop all active sessions
        for call_id, session in list(active_sessions.items()):
            session['stop_event'].set()
            session['thread'].join(timeout=5)
        print("All sessions stopped.")