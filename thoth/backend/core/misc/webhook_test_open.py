import requests

# Start a call
response = requests.post('http://localhost:5000/webhook/call-started', json={
    'call_id': 'test-call-123',
    'from': '0490024573'
})
print(response.json())
