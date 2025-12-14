"""
Test script for staff lookup by phone number.

Usage:
    python test_staff_lookup.py
    
    Then enter a phone number when prompted (e.g., "+61412345678" or "0412345678")
"""
import asyncio
import logging
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from staff_lookup import lookup_staff_by_phone
from login_playwright import LoginAutomation
from website_configs_playwright import get_config
from secrets import get_admin_credentials

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def test_staff_lookup(phone_number: str, service_name: str = "hahs_vic3495"):
    """
    Test staff lookup by phone number.
    
    Args:
        phone_number: Phone number to search for
        service_name: Ezaango service name
    """
    logger.info(f"Starting staff lookup test for phone: {phone_number}")
    
    # Get credentials
    admin_creds = get_admin_credentials(service_name)
    if not admin_creds:
        logger.error("Admin credentials not available")
        return None
    
    # Get config
    try:
        config = get_config(service_name)
    except Exception as e:
        logger.error(f"Could not get config for {service_name}: {e}")
        return None
    
    # Login and lookup
    try:
        async with LoginAutomation(headless=False) as automation:
            # Login
            logger.info("Logging in to Ezaango...")
            success = await automation.login_with_retry(
                config=config,
                service_name=f"{service_name}_admin",
                llm_credentials=admin_creds
            )
            
            if not success:
                logger.error("Login failed")
                return None
            
            logger.info("Login successful! Navigating to staff page...")
            
            # Get page object
            page = await automation.get_page()
            if not page:
                logger.error("Could not get page object")
                return None
            
            # Look up staff
            logger.info(f"Looking up staff with phone: {phone_number}")
            staff_info = await lookup_staff_by_phone(page, phone_number)
            
            if staff_info:
                logger.info("\n" + "="*60)
                logger.info("✓ STAFF FOUND!")
                logger.info("="*60)
                logger.info(f"Full Name:  {staff_info.get('full_name')}")
                logger.info(f"ID:         {staff_info.get('id')}")
                logger.info(f"Mobile:     {staff_info.get('mobile')}")
                logger.info(f"Email:      {staff_info.get('email')}")
                logger.info(f"Team:       {staff_info.get('team')}")
                logger.info(f"Status:     {staff_info.get('status')}")
                logger.info(f"Address:    {staff_info.get('address')}")
                logger.info("="*60 + "\n")
                
                return staff_info
            else:
                logger.warning(f"\n✗ No staff found for phone: {phone_number}\n")
                return None
            
    except Exception as e:
        logger.error(f"Error during staff lookup: {e}")
        import traceback
        traceback.print_exc()
        return None


async def interactive_test():
    """
    Interactive testing mode - ask user for phone number
    """
    print("\n" + "="*60)
    print("STAFF LOOKUP TEST")
    print("="*60)
    print("\nThis script will help you test staff lookup by phone number.")
    print("The browser will open and you can watch as it searches.")
    print("\nSupported phone formats:")
    print("  - +61412345678")
    print("  - +61 412 345 678")
    print("  - 0412345678")
    print("  - 0412 345 678")
    print("\n" + "="*60 + "\n")
    
    while True:
        phone = input("Enter phone number to search (or 'quit' to exit): ").strip()
        
        if phone.lower() in ('quit', 'exit', 'q'):
            print("Exiting...")
            break
        
        if not phone:
            print("Please enter a phone number\n")
            continue
        
        print(f"\nSearching for staff with phone: {phone}")
        result = await test_staff_lookup(phone)
        
        if result:
            print(f"\n✓ SUCCESS! Found: {result['full_name']}")
        else:
            print(f"\n✗ NOT FOUND - No staff member with phone: {phone}")
        
        print()


async def batch_test(phone_numbers: list):
    """
    Test multiple phone numbers
    
    Args:
        phone_numbers: List of phone numbers to test
    """
    logger.info(f"Testing {len(phone_numbers)} phone numbers")
    
    results = []
    for phone in phone_numbers:
        logger.info(f"\n--- Testing: {phone} ---")
        result = await test_staff_lookup(phone)
        results.append({
            "phone": phone,
            "found": result is not None,
            "staff_name": result.get('full_name') if result else None,
            "staff_id": result.get('id') if result else None,
        })
    
    # Print summary
    print("\n" + "="*60)
    print("BATCH TEST SUMMARY")
    print("="*60)
    for r in results:
        status = "✓" if r['found'] else "✗"
        name = r['staff_name'] or "NOT FOUND"
        print(f"{status} {r['phone']:20} → {name}")
    print("="*60 + "\n")
    
    return results


async def main():
    """Main entry point"""
    import sys
    
    if len(sys.argv) > 1:
        # Non-interactive mode: test provided phone numbers
        phone_numbers = sys.argv[1:]
        logger.info(f"Testing {len(phone_numbers)} phone number(s)")
        await batch_test(phone_numbers)
    else:
        # Interactive mode
        await interactive_test()


if __name__ == "__main__":
    asyncio.run(main())
