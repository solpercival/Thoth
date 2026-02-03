# Simple test script to start a screening session via API
# Make sure app_v2.py is running first: python app_v2.py

import requests

API_URL = "http://localhost:5001"

def start_session(caller_id="test_call", caller_phone="0411222333"):
    """Start a new screening session"""
    response = requests.post(
        f"{API_URL}/start",
        json={
            "caller_id": caller_id,
            "caller_phone": caller_phone
        }
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    return response.json()


def check_status():
    """Check all active sessions"""
    response = requests.get(f"{API_URL}/status")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    return response.json()


def stop_session(session_id=None, caller_phone=None):
    """Stop a screening session"""
    payload = {}
    if session_id:
        payload["session_id"] = session_id
    if caller_phone:
        payload["caller_phone"] = caller_phone

    response = requests.post(f"{API_URL}/stop", json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    return response.json()


if __name__ == "__main__":
    print("=" * 50)
    print("Starting screening session...")
    print("=" * 50)

    result = start_session()

    print("\n" + "=" * 50)
    print("Session started! Check app_v2.py terminal for activity.")
    print("=" * 50)
