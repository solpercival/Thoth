"""
Test script for the /debug endpoint
Sends a POST request with sample data to verify the endpoint works.
"""

import requests

URL = "http://localhost:5000/debug"

def test_debug_endpoint():
    """Send test data to the debug endpoint"""
    test_data = {
        "message": "Hello from test script!"
    }

    try:
        response = requests.post(URL, json=test_data)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to server. Make sure app_v2.py is running.")

if __name__ == "__main__":
    test_debug_endpoint()
