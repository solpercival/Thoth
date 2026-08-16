import sys
from pathlib import Path

# Add backend root to Python path
backend_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(backend_root))

from flask import Flask, request, jsonify
from threading import Thread, Event
import time
import os
import uuid
import logging

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("faster_whisper").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

from rostering_agent.core.call_assistant.call_3cx_client import close_all_calls_for_extension, is_call_active
from rostering_agent.core.call_assistant.call_assistant_v5 import CallAssistantV5

ESTABLISH_DELAY = 1.0
EXTENSION = os.getenv('USED_EXTENSION')
CALL_STATUS_POLL_FREQ = 2.0
TEST_MODE = False
TEST_NUMBER = "0415500152"

app = Flask(__name__)
active_sessions = {}


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'}), 200


@app.route('/')
def home():
    return """
Thoth is running!\n
Endpoints are:\n
/webhook/call-started - to start a call with. Args: 'call_id', 'from'\n
/webhook/call-ended - to end a call. Args: 'from'\n
"""


@app.route('/webhook/call-started', methods=['GET', 'POST'])
def call_started():
    caller_display = request.args.get('call_id', 'unknown')
    caller_phone = request.args.get('from')

    if TEST_MODE:
        caller_phone = TEST_NUMBER
        print(f"APP.PY: TEST MODE - Using preset number: {caller_phone}")

    call_id = f"{caller_phone}_{int(time.time())}_{uuid.uuid4().hex[:6]}"

    if call_id in active_sessions:
        return "<script>window.close();</script>", 200

    print("APP.PY: Creating agent")
    assistant = CallAssistantV5(caller_phone=caller_phone, extension=EXTENSION)
    stop_event = Event()

    def run_assistant():
        try:
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

    active_sessions[call_id] = {
        'assistant': assistant,
        'thread': thread,
        'stop_event': stop_event,
        'started_at': time.time(),
        'version': 'v5',
        'caller_phone': caller_phone
    }

    return "<script>setTimeout(function(){window.close();}, 1000);</script>", 200


@app.route('/webhook/call-ended', methods=['GET', 'POST'])
@app.route('/webhook/call-ended', methods=['GET'])
def call_ended():
    caller_phone = request.args.get('from')

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

    stop_event = session_to_end['stop_event']
    stop_event.set()

    print(f"APP.PY: Stop call requested for caller: {caller_phone}, call id: {call_id_to_end}")

    return "<script>window.close();</script>", 200


@app.route('/status', methods=['GET'])
def status():
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
    try:
        print("=" * 60)
        print("Starting Flask app with CallAssistantV5")
        print("=" * 60)
        print("\nEndpoints:")
        print("  GET/POST /webhook/call-started - Start a call session")
        print("  GET/POST /webhook/call-ended - End a call session")
        print("\nServer running on http://localhost:5000\n")
        print("=" * 60 + "\n")

        app.run(debug=True, port=5000, use_reloader=False)
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
        for call_id, session in list(active_sessions.items()):
            session['stop_event'].set()
            session['thread'].join(timeout=5)
        print("All sessions stopped.")


__all__ = ["app", "health", "home", "call_started", "call_ended", "status"]
