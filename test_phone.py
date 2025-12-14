#!/usr/bin/env python3
"""
Ultra-simple staff lookup test.
Just run: python test_phone.py "0490024573"
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.automation.staff_lookup import lookup_staff_by_phone
from backend.automation.login_playwright import LoginAutomation
from backend.automation.website_configs_playwright import get_config
from backend.automation.secrets import get_admin_credentials


async def main():
    if len(sys.argv) < 2:
        print("Usage: python test_phone.py <phone_number>")
        print("Example: python test_phone.py 0490024573")
        return
    
    phone = sys.argv[1]
    print(f"\nSearching for staff with phone: {phone}\n")
    
    try:
        creds = get_admin_credentials("hahs_vic3495")
        config = get_config("hahs_vic3495")
        
        async with LoginAutomation(headless=False) as auto:
            await auto.login_with_retry(
                config=config,
                service_name="hahs_vic3495_admin",
                llm_credentials=creds
            )
            
            page = await auto.get_page()
            staff = await lookup_staff_by_phone(page, phone)
            
            if staff:
                print("\n✓ FOUND!\n")
                print(f"Full Name: {staff['full_name']}")
                print(f"ID: {staff['id']}")
                print(f"Mobile: {staff['mobile']}")
                print(f"Email: {staff['email']}")
                print(f"Team: {staff['team']}")
                print()
            else:
                print("\n✗ NOT FOUND\n")
                
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
