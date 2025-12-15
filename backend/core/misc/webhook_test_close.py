import requests

# End the call
response = requests.post('http://localhost:5000/webhook/call-ended', json={
    'call_id': 'test-call-123',
    'from': '0431256441'
})
print(response.json())