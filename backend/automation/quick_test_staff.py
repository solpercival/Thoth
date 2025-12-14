#!/usr/bin/env python3
"""
Quick test: Look up staff by phone number using proper login flow.

Usage:
    python quick_test_staff.py "0490024573"
    python quick_test_staff.py "+61412345678"
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from staff_lookup import lookup_staff_by_phone
from login_playwright import LoginAutomation
from website_configs_playwright import get_config
from secrets import get_admin_credentials, get_admin_totp_code


async def quick_lookup(phone_number: str):
    """Quick staff lookup using proper login flow (like run_admin_login_prompt_2fa.py)"""
    print(f"\n[*] Looking up staff with phone: {phone_number}")
    print("[*] Opening browser... (headless=False for visibility)\n")
    
    try:
        # Step 1: Get admin credentials
        print("[Step 1] Getting admin credentials...")
        admin_creds = get_admin_credentials("hahs_vic3495")
        
        if not admin_creds:
            print("[!] Admin credentials not configured in .env")
            return None
        
        print("[+] Got credentials")
        
        # Step 2: Generate TOTP code (like run_admin_login_prompt_2fa.py does)
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
            
            # Step 6: Wait a moment for session to stabilize
            print("[Step 4] Waiting for session to stabilize...")
            await asyncio.sleep(2)
            
            # Step 7: Get page and directly call lookup
            print(f"[Step 5] Looking up staff by phone: {phone_number}...\n")
            page = await automation.get_page()
            staff = await lookup_staff_by_phone(page, phone_number)
            
            if staff:
                print("=" * 70)
                print("[+] FOUND!")
                print("=" * 70)
                print(f"  Full Name:   {staff['full_name']}")
                print(f"  Staff ID:    {staff['id']}")
                print(f"  Mobile:      {staff['mobile']}")
                print(f"  Email:       {staff['email']}")
                print(f"  Team:        {staff['team']}")
                print(f"  Status:      {staff['status']}")
                print(f"  Address:     {staff['address']}")
                print("=" * 70 + "\n")
                return staff
            else:
                print("=" * 70)
                print("[!] NOT FOUND")
                print("=" * 70)
                print(f"No staff member found with phone: {phone_number}")
                print("=" * 70 + "\n")
                return None
                
    except Exception as e:
        print(f"[!] Error: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python quick_test_staff.py <phone_number>")
        print("\nExamples:")
        print("  python quick_test_staff.py '0490024573'")
        print("  python quick_test_staff.py '+61412345678'")
        sys.exit(1)
    
    phone = sys.argv[1]
    result = asyncio.run(quick_lookup(phone))
    
    if result:
        sys.exit(0)
    else:
        sys.exit(1)
