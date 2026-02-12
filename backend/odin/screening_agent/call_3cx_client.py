import requests
import urllib3
import os
from urllib.parse import quote
from dotenv import load_dotenv
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()


PBX_URL = os.getenv('PBX_URL')
CLIENT_ID = os.getenv('CLIENT_ID')  # API CLient ID
CLIENT_SECRET = os.getenv('CLIENT_SECRET')  # API Key

AGENT_START_DELAY = 2.0

def get_access_token():
    """Get access token for API calls"""
    token_url = f"{PBX_URL}/connect/token"
    
    data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'client_credentials'
    }
    
    response = requests.post(
        token_url,
        data=data,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        verify=False
    )
    
    if response.status_code == 200:
        return response.json()['access_token']
    return None

def get_active_calls(extension:str, access_token:str):
    """Get all active participants for an extension"""
    url = f"{PBX_URL}/callcontrol/{extension}/participants"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    response = requests.get(url, headers=headers, verify=False)
    
    if response.status_code == 200:
        return response.json()
    return []

def drop_call(extension:str, participant_id, access_token:str):
    """Drop/end a specific call"""
    url = f"{PBX_URL}/callcontrol/{extension}/participants/{participant_id}/drop"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(url, headers=headers, json={}, verify=False)
    return response.status_code in [200, 202]

def close_all_calls_for_extension(extension):
    """
    Simple function to close ALL ongoing calls for an extension
    """
    # Get token
    token = get_access_token()
    if not token:
        print("Failed to get access token")
        return False
    
    # Get active calls
    participants = get_active_calls(extension, token)
    
    if not participants:
        print(f"No active calls for extension {extension}")
        return True
    
    print(f"Found {len(participants)} active call(s)")
    
    # Drop each call
    for participant in participants:
        participant_id = participant['id']
        caller = participant.get('party_caller_id', 'Unknown')
        
        print(f"3CX_CLIENT.PY: Dropping call from {caller} (participant {participant_id})")
        success = drop_call(extension, participant_id, token)
        
        if success:
            print(f"  ✅ Call dropped successfully")
        else:
            print(f"  ❌ Failed to drop call")
    
    return True

def make_call(extension: str, destination: str, timeout: int = 30):
    """
    Initiate an outbound call from an extension to a destination number.

    Args:
        extension: The DN/extension number to call FROM
        destination: The phone number to call TO
        timeout: Call timeout in seconds (default 30)

    Returns:
        Response JSON on success, None on failure
    """

    token = get_access_token()
    if not token:
        print("[3CX] Failed to get access token")
        return None

    # Step 1: Initiate the call (this will ring the extension first)
    url = f"{PBX_URL}/callcontrol/{extension}/makecall"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = {
        "destination": destination,
        "timeout": timeout
    }

    response = requests.post(url, headers=headers, json=payload, verify=False)

    if response.status_code not in [200, 202]:
        print(f"[3CX] Failed to initiate call: {response.status_code}")
        return None

    call_result = response.json()
    print(f"[3CX] Call initiated to {destination}")
    return call_result


def answer_call(extension: str, participant_id: str, device_id: str = None):
    """Answer an incoming call"""
    token = get_access_token()
    if not token:
        return False

    # Try device-specific endpoint first if device_id provided
    if device_id:
        encoded_device_id = quote(device_id, safe='')
        url = f"{PBX_URL}/callcontrol/{extension}/devices/{encoded_device_id}/participants/{participant_id}/answer"
    else:
        url = f"{PBX_URL}/callcontrol/{extension}/participants/{participant_id}/answer"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    response = requests.post(url, headers=headers, json={}, verify=False)

    # If device-specific failed, try without device
    if response.status_code not in [200, 202] and device_id:
        url = f"{PBX_URL}/callcontrol/{extension}/participants/{participant_id}/answer"
        response = requests.post(url, headers=headers, json={}, verify=False)

    return response.status_code in [200, 202]



def is_call_active(extension: str, caller_phone: str) -> bool:
    """Check if a call from caller_phone is still active on extension"""
    token = get_access_token()
    if not token:
        return False
    
    participants = get_active_calls(extension, token)
    
    for p in participants:
        if p.get('party_caller_id') == caller_phone:
            return True
    return False


def poll_call_answered(extension: str, timeout: int = 30, poll_interval: float = 1.0) -> dict:
    """
    Poll to check if the outbound call has been answered by the target.

    Args:
        extension: The extension that initiated the call
        timeout: Max seconds to wait for answer
        poll_interval: Seconds between polls

    Returns:
        dict with 'status': 'answered' | 'ringing' | 'no_call' | 'timeout' | 'error'
        and 'participant' data if found
    """
    import time
    start_time = time.time()

    while time.time() - start_time < timeout:
        token = get_access_token()
        if not token:
            return {'status': 'error', 'reason': 'no_token'}

        participants = get_active_calls(extension, token)

        if not participants:
            # No active call found - might have ended or not started yet
            elapsed = time.time() - start_time
            if elapsed > 5:  # Give some grace period at start
                return {'status': 'no_call'}

        for p in participants:
            if p.get('status') == 'Connected':
                # Check if target has answered (external line connected)
                if p.get('party_dn_type') == 'Wexternalline':
                    return {'status': 'answered', 'participant': p}
                # Otherwise still waiting for target to pick up

        time.sleep(poll_interval)

    return {'status': 'timeout'}


#####################################################################################################################

# Testing
if __name__ == '__main__':
    extension = "0147"
    destination = "0415500152"

    print(f"Initiating call from {extension} to {destination}...")
    result = make_call(extension, destination)
    print(f"make_call response: {result}")

    if result and result.get('finalstatus') == 'Success':
        print("\nPolling for answer...")
        poll_result = poll_call_answered(extension, timeout=60, poll_interval=1.0)

        print(f"\n=== RESULT ===")
        print(f"Status: {poll_result['status']}")
        if poll_result.get('participant'):
            print(f"Participant: {poll_result['participant']}")
    else:
        print("Failed to initiate call")

    