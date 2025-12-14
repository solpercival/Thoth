#!/usr/bin/env python3
"""
Test: Search for shifts by staff name.

Usage:
    python test_shift_search.py "Alannah Courtnay"
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from staff_lookup import search_staff_shifts_by_name
from login_playwright import LoginAutomation
from website_configs_playwright import get_config
from secrets import get_admin_credentials, get_admin_totp_code


async def test_shift_search(staff_name: str):
    """Test searching for shifts by staff name"""
    print(f"\n[*] Searching for shifts by staff: {staff_name}")
    print("[*] Opening browser... (headless=False for visibility)\n")
    
    try:
        # Step 1: Get admin credentials and TOTP
        print("[Step 1] Getting admin credentials...")
        admin_creds = get_admin_credentials("hahs_vic3495")
        if not admin_creds:
            print("[!] Admin credentials not configured in .env")
            return None
        print("[+] Got credentials")
        
        print("[Step 2] Generating TOTP code...")
        two_fa_code = get_admin_totp_code("hahs_vic3495")
        if not two_fa_code:
            print("[!] Could not generate TOTP code")
            return None
        print(f"[+] Generated TOTP code: {two_fa_code}")
        
        # Step 3: Add 2FA code to credentials
        creds_with_2fa = dict(admin_creds)
        creds_with_2fa["two_fa_code"] = two_fa_code
        
        # Step 4: Get config
        config = get_config("hahs_vic3495")
        
        # Step 5: Login with TOTP
        print("[Step 3] Logging in to Ezaango (with TOTP)...")
        async with LoginAutomation(headless=False, max_retries=1) as automation:
            success = await automation.login_with_retry(
                config=config,
                service_name="hahs_vic3495_admin",
                llm_credentials=creds_with_2fa
            )
            
            if not success:
                print("[!] Login failed")
                return None
            
            print("[+] Login successful!")
            
            # Step 6: Wait for session to stabilize
            print("[Step 4] Waiting for session to stabilize...")
            await asyncio.sleep(2)
            
            # Step 7: Search for shifts
            print(f"[Step 5] Searching for shifts by staff: {staff_name}...\n")
            page = await automation.get_page()
            shifts = await search_staff_shifts_by_name(page, staff_name)
            
            if not shifts:
                print("=" * 70)
                print("[!] No shifts found")
                print("=" * 70 + "\n")
                return []
            
            print("=" * 70)
            print(f"[+] FOUND {len(shifts)} SHIFT(S)!")
            print("=" * 70)
            
            for i, shift in enumerate(shifts, 1):
                print(f"\n[Shift {i}]")
                print(f"  Type:         {shift.get('type', 'N/A')}")
                print(f"  Staff:        {shift.get('staff_name', 'N/A')}")
                print(f"  Client:       {shift.get('client_name', 'N/A')}")
                print(f"  Date:         {shift.get('date', 'N/A')}")
                print(f"  Time:         {shift.get('time', 'N/A')}")
                print(f"  Shift ID:     {shift.get('shift_id', 'N/A')}")
                print(f"  URL:          {shift.get('shift_url', 'N/A')}")
            
            print("\n" + "=" * 70 + "\n")
            return shifts
                
    except Exception as e:
        print(f"[!] Error: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_shift_search.py <staff_name>")
        print("\nExamples:")
        print("  python test_shift_search.py 'Alannah Courtnay'")
        print("  python test_shift_search.py 'John Smith'")
        sys.exit(1)
    
    staff_name = sys.argv[1]
    result = asyncio.run(test_shift_search(staff_name))
    
    if result:
        sys.exit(0)
    else:
        sys.exit(1)
