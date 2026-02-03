import requests
import urllib3
import os
from dotenv import load_dotenv
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()


PBX_URL = os.getenv('PBX_URL')
CLIENT_ID = os.getenv('CLIENT_ID')  # API CLient ID
CLIENT_SECRET = os.getenv('CLIENT_SECRET')  # API Key

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
        return None
    
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
    
    if response.status_code in [200, 202]:
        return response.json()
    return None


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

#####################################################################################################################

# Testing
if __name__ == '__main__':
    # Close all calls on extension 100
    make_call("0147", "0415500152")

    