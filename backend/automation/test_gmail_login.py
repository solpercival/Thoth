"""
Test script for Gmail login automation
Simple script to test the login module with Gmail credentials
"""

import logging
import sys
from typing import Dict

try:
    from .login import LoginAutomation, WebsiteConfig, LoginStrategy
except ImportError:
    from login import LoginAutomation, WebsiteConfig, LoginStrategy

# Configure logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Gmail login configuration
GMAIL_CONFIG = WebsiteConfig(
    url="https://practicetestautomation.com/practice-test-login/",
    strategy=LoginStrategy.STANDARD,
    username_selector="input[name='username']",      # <input type="text" name="username" id="username">
    password_selector="input[name='password']",      # <input type="password" name="password" id="password">
    submit_selector="button[id='submit']",           # <button id="submit" class="btn">Submit</button>
    expected_url_after_login="https://practicetestautomation.com/logged-in-successfully/",
    wait_timeout=15,
)


def test_gmail_login(email: str, password: str) -> Dict:
    """
    Test Gmail login with provided credentials
    
    Args:
        email: Gmail email address
        password: Gmail password or app password
        
    Returns:
        Dictionary with test results
    """
    print("\n" + "="*70)
    print("GMAIL LOGIN TEST")
    print("="*70)
    
    # LLM-style credentials format
    llm_credentials = {
        "username": email,
        "password": password,
        "email": email,
        "extra_fields": {}
    }
    
    logger.info(f"Testing Gmail login for: {email}")
    logger.info("Running in non-headless mode so you can see what's happening...")
    
    try:
        with LoginAutomation(headless=False, max_retries=1) as automation:
            # Attempt login
            success = automation.login_with_retry(
                config=GMAIL_CONFIG,
                llm_credentials=llm_credentials,
            )
            
            if success:
                logger.info("✓ Login successful!")
                
                # Try to scrape page content
                try:
                    content = automation.scrape_page_content()
                    logger.info(f"✓ Scraped {len(content)} characters of page content")
                except Exception as e:
                    logger.warning(f"Could not scrape content: {e}")
                
                # Take screenshot for verification
                automation.take_screenshot("gmail_login_success.png")
                logger.info("✓ Screenshot saved to: gmail_login_success.png")
                
                return {
                    "success": True,
                    "message": "Successfully logged into Gmail",
                    "screenshot": "gmail_login_success.png"
                }
            else:
                logger.error("✗ Login failed")
                automation.take_screenshot("gmail_login_failed.png")
                logger.info("✗ Screenshot saved to: gmail_login_failed.png for debugging")
                
                return {
                    "success": False,
                    "message": "Login failed",
                    "screenshot": "gmail_login_failed.png"
                }
                
    except Exception as e:
        logger.error(f"✗ Test failed with error: {e}")
        return {
            "success": False,
            "message": f"Test failed: {e}"
        }


if __name__ == "__main__":
    # Get credentials from command line or prompt user
    if len(sys.argv) == 3:
        email = sys.argv[1]
        password = sys.argv[2]
    else:
        print("\nGmail Login Test Script")
        print("-" * 70)
        print("This script tests the login automation with real Gmail credentials")
        print("\nIMPORTANT SECURITY NOTES:")
        print("  • Use an App Password if you have 2FA enabled (recommended)")
        print("  • Never share your real password with anyone")
        print("  • This script runs locally and doesn't store credentials")
        print("  • See: https://support.google.com/accounts/answer/185833")
        print("-" * 70)
        
        email = input("\nEnter Gmail email address: ").strip()
        password = input("Enter Gmail password or app password: ").strip()
    
    if not email or not password:
        logger.error("Email and password are required")
        sys.exit(1)
    
    # Run the test
    result = test_gmail_login(email, password)
    
    # Print results
    print("\n" + "="*70)
    print("TEST RESULTS")
    print("="*70)
    print(f"Success: {result['success']}")
    print(f"Message: {result['message']}")
    if 'screenshot' in result:
        print(f"Screenshot: {result['screenshot']}")
    print("="*70 + "\n")
    
    sys.exit(0 if result['success'] else 1)
