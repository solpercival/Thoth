import sys
from pathlib import Path

backend_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(backend_root))

from flask import Flask, request, jsonify
from threading import Thread, Event
import logging
import time
import uuid
import os

from screening_agent.screening_agent.screening_agent_v2 import ScreeningAgentV2
from screening_agent.screening_agent.call_3cx_client import make_call, poll_call_answered, drop_call, get_access_token, get_active_calls

AGENT_START_DELAY = 2.0
TEST_MODE = False
TEST_NUMBER = "0415500152"

app = Flask(__name__)

class QuietStatusFilter(logging.Filter):
    def filter(self, record):
        msg = record.getMessage()
        return '/status' not in msg and '/health' not in msg

logging.getLogger('werkzeug').addFilter(QuietStatusFilter())

active_sessions = {}
call_results = {}


@app.route('/health', methods=['GET'])
def health():
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
    data = request.get_json() or {}
    caller_id = data.get('caller_id', f"call_{uuid.uuid4().hex[:8]}")
    caller_phone = data.get('caller_phone', 'unknown')

    if TEST_MODE:
        caller_phone = TEST_NUMBER
        print(f"[APP_V2] TEST MODE - Using preset number: {caller_phone}")

    stop_event = Event()
    session_id = f"{caller_phone}_{int(time.time())}_{uuid.uuid4().hex[:6]}"

    for sid, session in active_sessions.items():
        if session.get('caller_phone') == caller_phone:
            return jsonify({
                'error': 'Session already active for this phone number',
                'session_id': sid
            }), 409

    active_sessions[session_id] = {
        'agent': None,
        'thread': None,
        'stop_event': stop_event,
        'started_at': time.time(),
        'caller_phone': caller_phone,
        'caller_id': caller_id,
        'call_status': 'ringing'
    }

    def poll_and_start_agent():
        extension = os.getenv('USED_EXTENSION', '0147')
        call_result = make_call(extension, caller_phone)

        if not call_result:
            print(f"[APP_V2] make_call failed for {caller_phone} — skipping poll")
            call_results[session_id] = {
                'caller_phone': caller_phone,
                'result': 'failed',
                'call_status': 'make_call_failed',
            }
            if session_id in active_sessions:
                del active_sessions[session_id]
            return

        poll_result = poll_call_answered(extension, timeout=60, poll_interval=1.0)
        if poll_result['status'] != 'answered':
            print(f"[APP_V2] Call not answered: {poll_result['status']}")
            active_sessions[session_id]['call_status'] = poll_result['status']
            call_results[session_id] = {
                'caller_phone': caller_phone,
                'result': 'no_answer',
                'call_status': poll_result['status'],
            }
            if session_id in active_sessions:
                del active_sessions[session_id]
            return

        print(f"[APP_V2] Call answered! Waiting for connection to stabilize...")
        active_sessions[session_id]['call_status'] = 'answered'
        active_sessions[session_id]['participant'] = poll_result.get('participant')
        active_sessions[session_id]['extension'] = extension
        time.sleep(AGENT_START_DELAY)

        print(f"[APP_V2] Starting ScreeningAgentV2")
        agent = ScreeningAgentV2(caller_id=caller_id, caller_number=caller_phone)
        active_sessions[session_id]['agent'] = agent

        try:
            agent.start()
            call_check_counter = 0
            while agent._agent_thread and agent._agent_thread.is_alive():
                if stop_event.is_set():
                    agent.stop()
                    break
                call_check_counter += 1
                if call_check_counter >= 10:
                    call_check_counter = 0
                    token = get_access_token()
                    if token:
                        participants = get_active_calls(extension, token)
                        if not participants:
                            print(f"[APP_V2] Call dropped by remote party — stopping agent")
                            agent.stop()
                            break
                time.sleep(0.5)
        except Exception as e:
            print(f"[APP_V2] ERROR: {e}")
        finally:
            participant = active_sessions.get(session_id, {}).get('participant')
            if participant:
                token = get_access_token()
                if token:
                    participant_id = participant['id']
                    print(f"[APP_V2] Agent finished — dropping call participant {participant_id}")
                    drop_call(extension, participant_id, token)
                else:
                    print(f"[APP_V2] Agent finished — failed to get token to drop call")
            else:
                print(f"[APP_V2] Agent finished — no participant data, cannot drop call")

            if stop_event.is_set():
                result = 'stopped'
            elif agent and agent.callback_time:
                result = 'callback'
                print(f"[APP_V2] Agent finished — user busy, callback: {agent.callback_time}")
            elif agent and len(agent.answers) == 0:
                result = 'no_answer'
                print(f"[APP_V2] Agent finished with 0 answers")
            else:
                result = 'completed'
            call_results[session_id] = {
                'caller_phone': active_sessions.get(session_id, {}).get('caller_phone', 'unknown'),
                'result': result,
                'call_status': active_sessions.get(session_id, {}).get('call_status', 'unknown'),
            }

            if session_id in active_sessions:
                del active_sessions[session_id]

    thread = Thread(target=poll_and_start_agent, daemon=True)
    thread.start()
    active_sessions[session_id]['thread'] = thread

    return jsonify({
        'status': 'started',
        'session_id': session_id,
        'caller_phone': caller_phone,
        'caller_id': caller_id
    }), 200


@app.route('/stop', methods=['POST'])
def stop_screening():
    data = request.get_json() or {}
    session_id = data.get('session_id')
    caller_phone = data.get('caller_phone')

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

    print(f"[APP_V2] Stopping session {session_id_to_end}")
    session_to_end['stop_event'].set()
    if session_to_end['agent']:
        session_to_end['agent'].stop()

    extension = session_to_end.get('extension', os.getenv('USED_EXTENSION', '0147'))
    participant = session_to_end.get('participant')
    if participant:
        token = get_access_token()
        if token:
            participant_id = participant['id']
            print(f"[APP_V2] Dropping call participant {participant_id}")
            drop_call(extension, participant_id, token)
    else:
        print(f"[APP_V2] No participant data stored, cannot drop call")

    return jsonify({
        'status': 'stopped',
        'session_id': session_id_to_end,
        'caller_phone': caller_phone
    }), 200


@app.route('/status', methods=['GET'])
def status():
    return jsonify({
        'active_sessions': len(active_sessions),
        'sessions': [
            {
                'session_id': sid,
                'caller_phone': s.get('caller_phone'),
                'call_status': s.get('call_status')
            }
            for sid, s in active_sessions.items()
        ]
    }), 200


if __name__ == '__main__':
    try:
        print("=" * 60)
        print("Starting Odin Screening Agent Flask app")
        print("=" * 60)
        print("\nEndpoints:")
        print("  POST /start   - Start a screening session")
        print("  POST /stop    - Stop a screening session")
        print("  GET  /status  - Get all active sessions")
        print("  GET  /health  - Health check")
        print("\nServer running on http://localhost:5001\n")
        print("=" * 60 + "\n")

        app.run(debug=True, port=5001, use_reloader=False)
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
        for session_id, session in list(active_sessions.items()):
            session['stop_event'].set()
            if session.get('agent'):
                session['agent'].stop()
            if session.get('thread'):
                session['thread'].join(timeout=5)
        print("All sessions stopped.")


__all__ = ["app", "health", "home", "start_screening", "stop_screening", "status"]

