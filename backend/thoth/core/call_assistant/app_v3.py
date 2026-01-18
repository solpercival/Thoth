import sys
from pathlib import Path

# Add backend root to Python path
# app_v3.py is at: backend/thoth/core/call_assistant/app_v3.py
backend_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(backend_root))

from flask import Flask, request, jsonify
from threading import Thread, Event
import time
import os
import uuid

from thoth.core.call_assistant.call_3cx_client import close_all_calls_for_extension, is_call_active
from thoth.core.call_assistant.call_assistant_v3 import CallAssistantV3

ESTABLISH_DELAY = 1.0  # Delay before the greeting is played and the transcriber is activated
EXTENSION = os.getenv('USED_EXTENSION')  # Extension of target number
CALL_STATUS_POLL_FREQ = 2.0  # How often should we poll the current call to see if it is still active

# For testing
TEST_MODE = True  # Set to true to use test phone number (as the caller number)
TEST_NUMBER = "0415500152"  

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
    

    # Get parameters from Custom URL
    caller_display = request.args.get('call_id', 'unknown')
    caller_phone = request.args.get('from')

    # Use test number if in test mode
    if TEST_MODE:
        caller_phone = TEST_NUMBER
        print(f"APP.PY: TEST MODE - Using preset number: {caller_phone}")

    # Create UNIQUE call_id to prevent blocking repeat calls
    call_id = f"{caller_phone}_{int(time.time())}_{uuid.uuid4().hex[:6]}"

    print(f"APP.PY: /webhook/call-started endpoint called. Caller: {caller_phone}, caller display: {caller_display}")

    # Check if call already in progress
    if call_id in active_sessions:
        return "<script>window.close();</script>", 200

    # NOTE: Auto-answer is configured in the 3CX user menu. If auto-answer from API is wanted,
    # do it here. Add "if" statement to continue if auto-asnwer API Call is succesful, break otherwise.
    # ============= AUTO-ANSWER THE CALL =============
    # ================================================

    # Create and start assistant
    print("APP.PY: Creating agent")
    assistant = CallAssistantV3(caller_phone=caller_phone, extension=EXTENSION)
    stop_event = Event()

    def run_assistant():
        try:
            # Only monitor real calls, not test calls
            if not TEST_MODE:
                def monitor_call():
                    while not stop_event.is_set():
                        time.sleep(2)
                        if not is_call_active(EXTENSION, caller_phone):
                            print(f"APP.PY: Call disconnected by {caller_phone}. Session stopped.")
                            stop_event.set()
                            break
                
                monitor_thread = Thread(target=monitor_call, daemon=True)
                monitor_thread.start()
            else:
                print("APP.PY: TEST MODE - Call monitoring disabled")
            
            assistant.run_with_event(stop_event)

        except Exception as e:
            print(f"[ERROR] {e}")
        finally:
            if call_id in active_sessions:
                del active_sessions[call_id]

    print("APP.PY: Starting assitant thread.")
    thread = Thread(target=run_assistant, daemon=True)
    thread.start()

    # Store session
    active_sessions[call_id] = {
        'assistant': assistant,
        'thread': thread,
        'stop_event': stop_event,
        'started_at': time.time(),
        'version': 'v3',
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
        print(f"APP.PY: ⚠️ No active session found for caller {caller_phone}")
        return "<script>window.close();</script>", 404

    # Signal the assistant to stop
    stop_event = session_to_end['stop_event']
    stop_event.set()
    
    print(f"APP.PY: Stop call requested for caller: {caller_phone}, call id: {call_id_to_end}")

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
        print("=" * 60)
        print("\nEndpoints:")
        print("  GET/POST /webhook/call-started - Start a call session")
        print("  GET/POST /webhook/call-ended - End a call session")
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