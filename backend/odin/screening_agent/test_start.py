# Simple test script to start a screening session via API
# Make sure app_v2.py is running first: python app_v2.py
#
# Usage: python test_start.py [phone_number]
# Example: python test_start.py 0415500152

import requests
import sys

API_URL = "http://localhost:5000"

# Default test number - change this or pass as command line argument
DEFAULT_NUMBER = "0415500152"

def start_session(caller_id="test_call", caller_phone=None):
    """Start a new screening session"""
    if caller_phone is None:
        caller_phone = DEFAULT_NUMBER

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
    # Get phone number from command line or use default
    phone_number = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_NUMBER

    print("=" * 50)
    print(f"Starting screening session for: {phone_number}")
    print("=" * 50)

    result = start_session(caller_phone=phone_number)

    print("\n" + "=" * 50)
    print("Session started! Check app_v2.py terminal for activity.")
    print("=" * 50)
