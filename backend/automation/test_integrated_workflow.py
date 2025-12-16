#!/usr/bin/env python3
"""
Comprehensive Integration Test - Complete Workflow

WORKFLOW ORCHESTRATOR - Coordinates all modules to process phone → staff → dates → shifts

Flow:
    test_integrated_workflow.py (this file - MAIN ENTRY POINT)
        ↓
        [1] login_playwright.py (LoginAutomation)
            - Logs in with 2FA
            - Credentials from secrets.py + website_configs_playwright.py
            - Returns authenticated page
        ↓
        [2] staff_lookup.py (lookup_staff_by_phone)
            - Uses authenticated page from login_playwright
            - Searches for staff by phone on Ezaango
            - Returns staff details (name, id, email, team)
        ↓
        [3] shift_date_reasoner.py (ShiftDateReasoner)
            - Takes user transcript
            - Sends to local Ollama LLM
            - Returns reasoned date range (start_date, end_date)
        ↓
        [4] staff_lookup.py (search_staff_shifts_by_name)
            - Uses authenticated page from login_playwright
            - Searches for shifts by staff name on Ezaango
            - Returns all shifts with dates/times
        ↓
        [5] Local filtering (this file)
            - Filters shifts to only those within reasoned date range
            - Returns relevant shifts to user
        ↓
        Final Output: staff info + date interpretation + filtered shifts

Dependencies:
    - login_playwright.py → Authenticates and returns page object
    - website_configs_playwright.py → Provides Ezaango selectors
    - staff_lookup.py → Handles staff/shift searches
    - shift_date_reasoner.py → Interprets dates using LLM
    - secrets.py → Provides credentials and TOTP codes

Usage:
    python test_integrated_workflow.py --phone "0431256441" --transcript "Hi I would like to cancel my shift tomorrow"
    python test_integrated_workflow.py --phone "0490024573" --transcript "When is my shift next week?"
"""
import asyncio
import sys
import os
import argparse
from datetime import datetime

# Add parent directories to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Try both relative and absolute imports
try:
    from backend.automation.staff_lookup import lookup_staff_by_phone, search_staff_shifts_by_name, search_staff_shifts_by_date
    from backend.automation.login_playwright import LoginAutomation
    from backend.automation.website_configs_playwright import get_config
    from backend.automation.secrets import get_admin_credentials, get_admin_totp_code
    from backend.core.call_assistant.shift_date_reasoner import ShiftDateReasoner
except ModuleNotFoundError:
    from staff_lookup import lookup_staff_by_phone, search_staff_shifts_by_name, search_staff_shifts_by_date
    from login_playwright import LoginAutomation
    from website_configs_playwright import get_config
    from secrets import get_admin_credentials, get_admin_totp_code
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'core', 'call_assistant'))
    from shift_date_reasoner import ShiftDateReasoner


def get_date_range(start_date_str: str, end_date_str: str) -> list:
    """
    Generate a list of dates between start and end dates (inclusive).
    
    Args:
        start_date_str: Start date in DD-MM-YYYY format
        end_date_str: End date in DD-MM-YYYY format
    
    Returns:
        List of dates in DD-MM-YYYY format
    """
    from datetime import timedelta
    
    # Parse dates
    start_parts = start_date_str.split("-")
    start = datetime(int(start_parts[2]), int(start_parts[1]), int(start_parts[0]))
    
    end_parts = end_date_str.split("-")
    end = datetime(int(end_parts[2]), int(end_parts[1]), int(end_parts[0]))
    
    # Generate date range
    dates = []
    current = start
    while current <= end:
        dates.append(current.strftime("%d-%m-%Y"))
        current += timedelta(days=1)
    
    return dates


async def test_integrated_workflow(phone_number: str, transcript: str):
    """
    Complete workflow: phone → staff → dates → filtered shifts
    
    Args:
        phone_number: Phone number to lookup
        transcript: User transcript for date reasoning
    
    Returns:
        dict with staff, dates, and filtered shifts
    """
    
    print("\n" + "="*70)
    print("COMPREHENSIVE INTEGRATION TEST")
    print("="*70)
    print(f"Phone Number: {phone_number}")
    print(f"User Transcript: {transcript}")
    print("="*70 + "\n")
    
    # ===== STEP 1: Login =====
    print("[STEP 1] Logging into Ezaango...")
    try:
        admin_creds = get_admin_credentials("hahs_vic3495")
        if not admin_creds:
            print("[!] Admin credentials not found in .env")
            return None
        
        # Add TOTP code
        code = get_admin_totp_code("hahs_vic3495")
        admin_creds["two_fa_code"] = code
        print(f"[+] Generated TOTP code: {code}")
        
        config = get_config("hahs_vic3495")
        
    except Exception as e:
        print(f"[!] Login setup failed: {e}")
        return None
    
    # ===== STEP 2-4: All operations while logged in =====
    try:
        async with LoginAutomation(headless=False, use_saved_session=False) as auto:
            # STEP 2: Login
            print("\n[STEP 2] Authenticating...")
            print("[*] Browser window will now open - you can watch the automation")
            success = await auto.login_with_retry(
                config=config,
                service_name="hahs_vic3495_admin",
                llm_credentials=admin_creds
            )
            
            if not success:
                print("[!] Login failed")
                return None
            
            page = await auto.get_page()
            
            # STEP 3: Staff Lookup
            print("\n[STEP 3] Looking up staff by phone...")
            print(f"[*] Searching for phone: {phone_number}")
            staff = await lookup_staff_by_phone(page, phone_number)
            
            if not staff:
                print(f"[!] Staff NOT FOUND for phone: {phone_number}")
                return None
            
            print(f"[+] FOUND Staff:")
            print(f"    Name: {staff['full_name']}")
            print(f"    ID: {staff['id']}")
            print(f"    Email: {staff['email']}")
            print(f"    Team: {staff['team']}")
            print(f"    Mobile: {staff['mobile']}")
            
            # STEP 4: Date Reasoning (LLM - no page needed)
            print("\n[STEP 4] Reasoning dates from transcript...")
            reasoner = ShiftDateReasoner(model="llama2")
            print(f"[*] Asking LLM: \"{transcript}\"")
            
            date_info = reasoner.reason_dates(transcript)
            
            print(f"[+] LLM Analysis:")
            print(f"    Is Shift Query: {date_info['is_shift_query']}")
            print(f"    Date Range Type: {date_info['date_range_type']}")
            print(f"    Start Date: {date_info['start_date']}")
            print(f"    End Date: {date_info['end_date']}")
            print(f"    Reasoning: {date_info['reasoning']}")
            
            # STEP 5: Shift Search with Date Filtering
            print("\n[STEP 5] Searching for shifts and filtering by date range...")
            print(f"[*] Searching shifts for: {staff['full_name']}")
            print(f"[*] Filtering to date range: {date_info['start_date']} to {date_info['end_date']}")
            
            # First, navigate to staff search to get all their shifts
            search_name = staff['full_name'].replace(" ", "+")
            search_url = f"https://hahs-vic3495.ezaango.app/search?keyword={search_name}"
            print(f"[*] Navigating to search results: {search_url}")
            await page.goto(search_url, wait_until="networkidle")
            await page.wait_for_selector("table tbody tr", timeout=10000)
            print(f"[+] Staff search page loaded")
            
            # Check if it's a date range (multiple days) or single day
            start_date = date_info['start_date']
            end_date = date_info['end_date']
            
            all_shifts = []
            
            if start_date == end_date:
                # Single day: filter by that date only
                print(f"[*] Single day filter: {start_date}")
                shifts_for_date = await search_staff_shifts_by_date(page, start_date)
                all_shifts = shifts_for_date
            else:
                # Date range: filter by each date individually
                print(f"[*] Date range detected: filtering by each date")
                dates_to_search = get_date_range(start_date, end_date)
                print(f"[*] Dates to filter: {', '.join(dates_to_search)}")
                
                for search_date in dates_to_search:
                    print(f"[*] Filtering for {staff['full_name']} on {search_date}...")
                    shifts_for_date = await search_staff_shifts_by_date(page, search_date)
                    all_shifts.extend(shifts_for_date)
                    print(f"    Found {len(shifts_for_date)} shifts on {search_date}")
            
            if not all_shifts:
                print(f"[!] No shifts found for {staff['full_name']}")
                return {
                    'staff': staff,
                    'dates': date_info,
                    'reasoning': date_info.get('reasoning', 'Unknown'),
                    'all_shifts': [],
                    'filtered_shifts': []
                }
            
            print(f"[+] Found {len(all_shifts)} total shifts in date range")
            
            # Results are already filtered by date using the input field
            # No additional filtering needed
            filtered_shifts = all_shifts
            start_date_display = date_info['start_date']
            end_date_display = date_info['end_date']
            
            print(f"[+] Filtered to {len(filtered_shifts)} shifts in date range ({start_date_display} to {end_date_display}):")
            
            if filtered_shifts:
                for i, shift in enumerate(filtered_shifts[:5], 1):
                    print(f"\n    Shift {i}:")
                    print(f"      Client: {shift['client_name']}")
                    print(f"      Type: {shift['type']}")
                    print(f"      Date: {shift['date']}")
                    print(f"      Time: {shift['time']}")
                    print(f"      Shift ID: {shift['shift_id']}")
                
                if len(filtered_shifts) > 5:
                    print(f"\n    ... and {len(filtered_shifts) - 5} more shifts")
            else:
                print("    (No shifts in this date range)")
            
            # STEP 6: Results Summary
            print("\n" + "="*70)
            print("INTEGRATION TEST RESULTS")
            print("="*70)
            print(f"[OK] Staff Found: {staff['full_name']} (ID: {staff['id']})")
            print(f"[OK] Date Range Reasoned: {start_date} to {end_date}")
            print(f"[OK] Total Shifts: {len(all_shifts)}")
            print(f"[OK] Shifts in Date Range: {len(filtered_shifts)}")
            print("="*70)
            print("\n[*] Browser will stay open for 10 seconds for inspection...")
            print("[*] Check the browser window to see if login and TOTP were successful")
            await asyncio.sleep(10)
            print("[*] Closing browser...\n")
            
            return {
                'staff': staff,
                'dates': date_info,
                'reasoning': date_info.get('reasoning', 'Unknown'),
                'all_shifts': all_shifts,
                'filtered_shifts': filtered_shifts
            }
    
    except Exception as e:
        print(f"\n[!] Error during workflow: {e}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    parser = argparse.ArgumentParser(
        description="Comprehensive integration test for staff lookup + date reasoning + shift filtering",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_integrated_workflow.py --phone "0431256441" --transcript "Hi I would like to cancel my shift tomorrow"
  python test_integrated_workflow.py --phone "0490024573" --transcript "When is my shift next week?"
  python test_integrated_workflow.py --phone "0431256441" --transcript "What shifts do I have?"
        """
    )
    
    parser.add_argument(
        "--phone",
        required=True,
        help="Phone number to lookup (e.g., 0431256441)"
    )
    parser.add_argument(
        "--transcript",
        required=True,
        help="User transcript for date reasoning (e.g., 'When is my shift tomorrow?')"
    )
    
    args = parser.parse_args()
    
    result = await test_integrated_workflow(args.phone, args.transcript)
    
    if result:
        print("\n[SUCCESS] Integration test completed successfully!")
        return 0
    else:
        print("\n[FAILED] Integration test failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
