"""Check what shifts actually exist for the staff"""
import asyncio

from backend.automation.login_playwright import LoginAutomation
from backend.automation.staff_lookup import lookup_staff_by_phone, search_staff_shifts_by_name
from backend.automation.secrets import get_admin_creds

async def main():
    login = LoginAutomation(use_saved_session=False)
    
    # Import get configuration from test_integrated_workflow
    creds = get_admin_creds()
    
    # Use the same login as test_integrated_workflow
    try:
        # Get login details from test
        success = await login.login_with_retry(
            login.auto_login.website_config,  
            'Ezaango',
            {
                'username': creds['username'],
                'password': creds['password'],
                'email': creds.get('email', '')
            }
        )
        
        page = await login.get_page()
        if not page:
            print("Failed to get page")
            return
            
        staff = await lookup_staff_by_phone(page, '0431256441')
        if staff:
            # Get ALL shifts (no date filtering)
            shifts = await search_staff_shifts_by_name(page, staff['full_name'])
            print(f'Total shifts: {len(shifts)}')
            if shifts:
                print(f'\nFirst 10 shifts:')
                for i, shift in enumerate(shifts[:10]):
                    print(f'  {i+1}. {shift.get("client_name")} on {shift.get("date")} at {shift.get("time")}')
    finally:
        await login.close()

asyncio.run(main())
