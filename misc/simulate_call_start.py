# test_incoming_call.py
import requests
import time

def simulate_incoming_call(caller_phone="0415500152", caller_name="Test Caller"):
    """
    Simulate an incoming call by triggering the webhook
    
    Args:
        caller_phone: Phone number of the caller
        caller_name: Display name of the caller
    """
    
    webhook_url = "http://127.0.0.1:5000/webhook/call-started"
    
    # Parameters that 3CX sends
    params = {
        'call_id': caller_name,  # 3CX sends caller display name here
        'from': caller_phone      # Caller's phone number
    }
    
    print("=" * 60)
    print("🔔 SIMULATING INCOMING CALL")
    print(f"Caller: {caller_name}")
    print(f"Number: {caller_phone}")
    print(f"URL: {webhook_url}")
    print(f"Params: {params}")
    print("=" * 60)
    
    try:
        # Make GET request to webhook
        response = requests.get(webhook_url, params=params, timeout=10)
        
        print(f"\n✅ Webhook Response:")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text[:200]}...")  # First 200 chars
        
        if response.status_code == 200:
            print("\n✅ Call session started successfully!")
            print("\nThe assistant should now be:")
            print("  1. Playing opening greeting")
            print("  2. Listening for your voice")
            print("  3. Ready to respond")
            
            return True
        else:
            print(f"\n❌ Failed to start session: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Could not connect to Flask server")
        print("Make sure Flask is running on http://localhost:5000")
        return False
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False


def simulate_call_ended(caller_phone="0415500152"):
    """
    Simulate call ending by triggering the end webhook
    
    Args:
        caller_phone: Phone number of the caller to end
    """
    
    webhook_url = "http://127.0.0.1:5000/webhook/call-ended"
    
    params = {
        'from': caller_phone
    }
    
    print("\n" + "=" * 60)
    print("📞 SIMULATING CALL END")
    print(f"Number: {caller_phone}")
    print("=" * 60)
    
    try:
        response = requests.get(webhook_url, params=params, timeout=5)
        
        print(f"\n✅ End Webhook Response:")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("\n✅ Stop signal sent successfully!")
            return True
        else:
            print(f"\n⚠️ Response: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False


def check_server_status():
    """Check if Flask server is running"""
    try:
        response = requests.get("http://127.0.0.1:5000/health", timeout=2)
        if response.status_code == 200:
            print("✅ Flask server is running")
            return True
        else:
            print(f"⚠️ Server responded with: {response.status_code}")
            return False
    except:
        print("❌ Flask server is not running!")
        print("Please start it with: python app_v3.py")
        return False


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("CALL SIMULATION TEST")
    print("=" * 60)
    
    # Check if server is running
    if not check_server_status():
        exit(1)
    
    # Simulate incoming call
    print("\n[1/2] Starting call simulation...")
    success = simulate_incoming_call(
        caller_phone="0415500152",
        caller_name="Christopher Lesmana"
    )
    
    if not success:
        exit(1)
    
    # Wait for user input
    print("\n" + "=" * 60)
    input("Press ENTER to simulate ending the call... (or Ctrl+C to cancel)")
    
    # Simulate call ending
    print("\n[2/2] Ending call simulation...")
    simulate_call_ended(caller_phone="0415500152")
    
    print("\n" + "=" * 60)
    print("✅ Test complete!")
    print("=" * 60)