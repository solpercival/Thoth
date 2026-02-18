# Test script to verify make_call + auto-answer flow
#
# Flow:
# 1. make_call() - initiates call (rings your extension)
# 2. Poll get_active_calls() - wait for the incoming call to appear
# 3. answer_call() - auto-answer it
# 4. Call should connect to the destination

import time
import sys
from call_3cx_client import make_call, get_access_token, get_active_calls, answer_call

# Configuration
EXTENSION = "0147"  # Your extension
TEST_NUMBER = "0415500152"  # Number to call


def test_auto_answer_flow(destination: str = TEST_NUMBER):
    """Test the full make_call -> auto-answer flow"""

    print("=" * 60)
    print("3CX Auto-Answer Test")
    print("=" * 60)
    print(f"Extension: {EXTENSION}")
    print(f"Destination: {destination}")
    print("=" * 60)

    # Step 1: Initiate the call
    print("\n[1] Initiating call...")
    call_result = make_call(EXTENSION, destination)

    if not call_result:
        print("ERROR: Failed to initiate call")
        return False

    print(f"    Call initiated: {call_result}")

    # Step 2: Poll for the incoming call
    print("\n[2] Waiting for incoming call to appear...")

    token = get_access_token()
    if not token:
        print("ERROR: Failed to get access token")
        return False

    participant_id = None
    max_attempts = 10

    for attempt in range(max_attempts):
        print(f"    Polling attempt {attempt + 1}/{max_attempts}...")

        participants = get_active_calls(EXTENSION, token)

        if participants:
            print(f"    Found {len(participants)} participant(s):")
            for p in participants:
                print(f"      - ID: {p.get('id')}")
                print(f"        State: {p.get('state')}")
                print(f"        Caller ID: {p.get('party_caller_id')}")
                print(f"        Direction: {p.get('direction')}")

                # Look for a ringing/incoming call
                state = p.get('state', '').lower()
                if state in ['ringing', 'alerting', 'incoming']:
                    participant_id = p.get('id')
                    print(f"\n    Found ringing call! Participant ID: {participant_id}")
                    break

        if participant_id:
            break

        time.sleep(0.5)

    if not participant_id:
        print("\nWARNING: No ringing call found. Checking all participants...")
        # Try to answer the first participant anyway
        participants = get_active_calls(EXTENSION, token)
        if participants:
            participant_id = participants[0].get('id')
            print(f"    Using first participant: {participant_id}")
        else:
            print("ERROR: No participants found at all")
            return False

    # Step 3: Answer the call
    print(f"\n[3] Answering call (participant {participant_id})...")

    answer_result = answer_call(EXTENSION, participant_id)

    if answer_result:
        print("    SUCCESS! Call answered via API")
        print("\n" + "=" * 60)
        print("The call should now be connecting to the destination.")
        print("=" * 60)
        return True
    else:
        print("    FAILED to answer call via API")
        return False


if __name__ == "__main__":
    # Get destination from command line or use default
    destination = sys.argv[1] if len(sys.argv) > 1 else TEST_NUMBER

    success = test_auto_answer_flow(destination)

    print(f"\nResult: {'SUCCESS' if success else 'FAILED'}")
