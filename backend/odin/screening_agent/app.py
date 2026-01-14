# HOW TO RUN:
# 1. cd to root
# 2. Run python -m backend.screening_agent.app


import sys
from pathlib import Path
from backend.odin.screening_agent.screening_agent import ScreeningAgent

# Fix import paths
backend_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_root))

from flask import Flask, request, jsonify

app = Flask(__name__)

screening_agents = {}


@app.route('/')
def home():
    return "Hello World"


@app.route('/webhook/call-started', methods=['POST'])
def call_started():
    """Webhook endpoint triggered when a call starts"""
    data = request.json
    call_id = data.get('call_id')
    caller_phone = data.get('from')

    # Start the screening agent and add it into a dictionary
    # NOTE: Agent runs in a non blocking thread
    screening_agent:ScreeningAgent = ScreeningAgent(call_id, caller_phone)
    screening_agent.start()

    screening_agents[caller_phone] = screening_agent



    return jsonify({
        'status': 'success',
        'message': 'Call started webhook received',
        'call_id': call_id,
        'caller_phone': caller_phone
    }), 200


@app.route('/webhook/call-ended', methods=['POST'])
def call_ended():
    """Webhook endpoint triggered when a call ends"""
    data = request.json
    call_id = data.get('call_id')
    caller_phone = data.get('from')

    # End the agent
    agent: ScreeningAgent = screening_agents[caller_phone]
    agent.stop()


    return jsonify({
        'status': 'success',
        'message': 'Call ended webhook received',
        'call_id': call_id
    }), 200


@app.route('/status', methods=['GET'])
def status():
    """Get status of the server"""
    return jsonify({
        'status': 'running',
        'message': 'Odin server is running'
    }), 200


if __name__ == "__main__":
    print("=" * 60)
    print("Starting Odin Flask app")
    print("=" * 60)
    print("\nEndpoints:")
    print("  POST /webhook/call-started - Call started webhook")
    print("  POST /webhook/call-ended - Call ended webhook")
    print("  GET /status - Server status")
    print("\nServer running on http://localhost:5000\n")
    print("=" * 60 + "\n")

    app.run(debug=True, port=5000)
