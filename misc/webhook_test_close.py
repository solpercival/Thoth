import requests

# End the call
try:
    response = requests.post('http://localhost:5000/webhook/call-ended', json={
        'call_id': 'test-call-123',
        'from': '0490024573'
    }, timeout=5)

    print(f"Status Code: {response.status_code}")
    print(f"Response Text: {response.text}")

    if response.text:
        print(f"Response JSON: {response.json()}")
    else:
        print("ERROR: Empty response from server")

except requests.exceptions.ConnectionError as e:
    print(f"ERROR: Cannot connect to server at http://localhost:5000")
    print(f"Make sure the Flask app is running (python backend/odin/app.py)")
    print(f"Details: {e}")
except requests.exceptions.Timeout:
    print("ERROR: Request timed out")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")