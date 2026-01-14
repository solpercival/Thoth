import requests
import urllib3
import os
from dotenv import load_dotenv
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()


PBX_URL = os.getenv('PBX_URL')
CLIENT_ID = os.getenv('CLIENT_ID')  # Your Client ID
CLIENT_SECRET = os.getenv('CLIENT_SECRET')  # Your API Key

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

def get_active_calls(extension, access_token):
    """Get all active participants for an extension"""
    url = f"{PBX_URL}/callcontrol/{extension}/participants"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    response = requests.get(url, headers=headers, verify=False)
    
    if response.status_code == 200:
        return response.json()
    return []

def drop_call(extension, participant_id, access_token):
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
        
        print(f"Dropping call from {caller} (participant {participant_id})")
        success = drop_call(extension, participant_id, token)
        
        if success:
            print(f"  ✅ Call dropped successfully")
        else:
            print(f"  ❌ Failed to drop call")
    
    return True

# Add this to call_flow_client.py

def answer_call(extension, participant_id, access_token):
    """Answer an incoming call"""
    url = f"{PBX_URL}/callcontrol/{extension}/participants/{participant_id}/answer"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    print(f"📡 Sending answer request to: {url}")
    response = requests.post(url, headers=headers, json={}, verify=False)
    
    print(f"📡 Response status: {response.status_code}")
    print(f"📡 Response text: {response.text}")
    
    return response.status_code in [200, 202]

def auto_answer_incoming_call(extension, caller_phone):
    """
    Auto-answer an incoming call from a specific caller
    Returns True if successful, False otherwise
    """
    print(f"\n{'='*60}")
    print(f"🔍 AUTO-ANSWER DEBUG for extension {extension}")
    print(f"🔍 Looking for caller: '{caller_phone}'")
    print(f"{'='*60}")
    
    # Get token
    token = get_access_token()
    if not token:
        print("❌ Failed to get access token")
        return False
    
    print("✅ Got access token")
    
    # Get active calls
    participants = get_active_calls(extension, token)
    
    print(f"\n📞 Found {len(participants)} participant(s)")
    
    if not participants:
        print(f"❌ No active calls for extension {extension}")
        return False
    
    # Print ALL participants with full details
    for i, participant in enumerate(participants, 1):
        print(f"\n--- Participant {i} ---")
        print(f"  ID: {participant.get('id')}")
        print(f"  Status: '{participant.get('status')}'")
        print(f"  Party Caller ID: '{participant.get('party_caller_id')}'")
        print(f"  Party DN: '{participant.get('party_dn')}'")
        print(f"  DN: '{participant.get('dn')}'")
    
    # Try to answer ANY participant (for debugging)
    for participant in participants:
        party_caller_id = participant.get('party_caller_id', '')
        participant_id = participant['id']
        status = participant.get('status', '').lower()
        
        print(f"\n🔎 Checking participant {participant_id}:")
        print(f"   Status: '{status}'")
        print(f"   Party Caller ID: '{party_caller_id}'")
        print(f"   Looking for: '{caller_phone}'")
        print(f"   Match? {party_caller_id == caller_phone}")
        
        # Try to answer if caller matches (regardless of status for now)
        if party_caller_id == caller_phone:
            print(f"🎯 MATCH FOUND! Attempting to answer...")
            success = answer_call(extension, participant_id, token)
            
            if success:
                print(f"✅✅✅ Call answered successfully!")
                return True
            else:
                print(f"❌ Answer API call failed")
                return False
    
    print(f"\n❌ No matching participant found")
    print(f"   Searched for: '{caller_phone}'")
    print(f"   Available caller IDs: {[p.get('party_caller_id') for p in participants]}")
    return False




# Usage Example:
if __name__ == '__main__':
    # Close all calls on extension 100
    close_all_calls_for_extension("0146")