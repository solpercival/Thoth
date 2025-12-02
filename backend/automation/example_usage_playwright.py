"""
Integration example - demonstrates Playwright login automation with session persistence and 2FA handling
Shows how login automation integrates with LLM core pipeline
"""

import asyncio
import os
import logging
from typing import Dict

try:
    from .login_playwright import LoginAutomation, WebsiteConfig, LoginStrategy
    from .website_configs_playwright import get_config
except ImportError:
    from login_playwright import LoginAutomation, WebsiteConfig, LoginStrategy
    from website_configs_playwright import get_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def login_from_llm_reasoning(
    website_config: WebsiteConfig,
    service_name: str,
    llm_reasoned_credentials: Dict,
    headless: bool = True,
) -> Dict:
    """
    Login to website using LLM-reasoned credentials
    This function is called by the LLM core pipeline
    
    **Key Feature: Session Persistence**
    After successful login, the browser context is saved to disk.
    On next call with same service_name, it will reuse the authenticated session!
    
    Args:
        website_config: Website configuration (selectors, URLs, etc)
        service_name: Service identifier (used for session file)
        llm_reasoned_credentials: Credentials reasoned out by LLM
            Format: {
                "username": "...",
                "password": "...",
                "email": "...",
                "extra_fields": {...},
                "two_fa_code": "..."  # Optional: for 2FA
            }
        headless: Run browser in headless mode
        
    Returns:
        Dictionary with results:
            {
                "success": bool,
                "scraped_content": str (page content after login),
                "message": str,
                "error": str (if failed)
            }
    """
    try:
        logger.info(f"Starting Playwright login automation from LLM reasoning")
        
        async with LoginAutomation(
            headless=headless, 
            max_retries=3,
            session_dir=os.getenv("SESSION_DIR", ".sessions")
        ) as automation:
            # Attempt login with LLM credentials
            success = await automation.login_with_retry(
                config=website_config,
                service_name=service_name,
                llm_credentials=llm_reasoned_credentials,
            )
            
            if success:
                logger.info("Login successful, scraping page content")
                
                # Scrape the page after successful login
                # This content will be processed by LLM for text-to-speech
                scraped_content = await automation.scrape_page_content()
                
                return {
                    "success": True,
                    "scraped_content": scraped_content,
                    "message": "Successfully logged in and scraped content (session saved for future use)"
                }
            else:
                return {
                    "success": False,
                    "scraped_content": None,
                    "message": None,
                    "error": "Login failed after retries"
                }
                
    except Exception as e:
        logger.error(f"Login automation failed: {e}")
        return {
            "success": False,
            "scraped_content": None,
            "message": None,
            "error": str(e)
        }


async def llm_integration_pipeline(
    transcribed_call: str,
    llm_reasoning_output: Dict,
) -> Dict:
    """
    Complete pipeline integration point
    Called by LLM core after reasoning out credentials
    
    **Session Persistence Flow:**
    1. First call: Performs login with credentials, saves session
    2. Subsequent calls: Reuses saved session, skips login if already authenticated
    
    Args:
        transcribed_call: Transcribed audio from call (context)
        llm_reasoning_output: LLM's output containing:
            {
                "service_name": "website_service",
                "credentials": {
                    "username": "...",
                    "password": "...",
                    "two_fa_code": "..."  # Optional
                    ...
                },
                "action": "login_and_scrape"
            }
            
    Returns:
        Dictionary with:
            {
                "success": bool,
                "scraped_content": str,
                "message": str,
                "error": str (if any)
            }
    """
    try:
        service_name = llm_reasoning_output.get("service_name")
        credentials = llm_reasoning_output.get("credentials", {})
        
        if not service_name or not credentials:
            return {
                "success": False,
                "message": None,
                "error": "Invalid LLM reasoning output format"
            }
        
        logger.info(f"LLM pipeline: Login to {service_name}")
        
        # Get website configuration
        config = get_config(service_name)
        
        # Login with LLM-reasoned credentials (or reuse saved session)
        result = await login_from_llm_reasoning(
            website_config=config,
            service_name=service_name,
            llm_reasoned_credentials=credentials,
            headless=os.getenv("HEADLESS", "true").lower() == "true"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"LLM pipeline failed: {e}")
        return {
            "success": False,
            "message": None,
            "error": str(e)
        }


async def demo_session_persistence():
    """
    Demonstrates the session persistence feature:
    1. First login: Authenticates and saves session
    2. Second request: Reuses saved session without login
    """
    
    logger.info("=" * 60)
    logger.info("DEMO: Session Persistence with Playwright")
    logger.info("=" * 60)
    
    # LLM-reasoned credentials (first login only)
    llm_credentials_first = {
        "username": "test_user",
        "password": "test_password",
        "email": "user@example.com",
        "extra_fields": {}
    }
    
    # Get configuration
    config = get_config("hahs_vic3495")
    
    logger.info("\n--- FIRST REQUEST: Login with credentials ---")
    result1 = await login_from_llm_reasoning(
        website_config=config,
        service_name="hahs_vic3495",
        llm_reasoned_credentials=llm_credentials_first,
        headless=False,
    )
    
    if result1["success"]:
        logger.info(f"✓ First login successful")
        logger.info(f"  Message: {result1['message']}")
        logger.info(f"  Content scraped: {len(result1['scraped_content'])} chars")
    else:
        logger.error(f"✗ First login failed: {result1['error']}")
        return
    
    logger.info("\n--- SECOND REQUEST: Reuse saved session (no login needed) ---")
    
    # Second request could have minimal credentials or empty
    # The system will try to load the saved session first
    llm_credentials_second = {
        "username": "test_user",  # Could even be empty for session reuse
        "password": "test_password",
    }
    
    result2 = await login_from_llm_reasoning(
        website_config=config,
        service_name="hahs_vic3495",
        llm_reasoned_credentials=llm_credentials_second,
        headless=False,
    )
    
    if result2["success"]:
        logger.info(f"✓ Second access successful (reused session)")
        logger.info(f"  Message: {result2['message']}")
        logger.info(f"  Content scraped: {len(result2['scraped_content'])} chars")
    else:
        logger.error(f"✗ Second access failed: {result2['error']}")
    
    logger.info("\n" + "=" * 60)
    logger.info("Session file location: .sessions/hahs_vic3495_auth.json")
    logger.info("=" * 60)


async def demo_2fa_handling():
    """
    Demonstrates 2FA handling with three approaches:
    1. Automatic: 2FA code provided in credentials
    2. Manual: 60-second wait for user to enter 2FA code
    """
    
    logger.info("=" * 60)
    logger.info("DEMO: 2FA Handling with Playwright")
    logger.info("=" * 60)
    
    # Option 1: Automatic 2FA (if you have the code)
    logger.info("\n--- Option 1: Automatic 2FA with code ---")
    llm_credentials_with_2fa = {
        "username": "user@example.com",
        "password": "secure_password",
        "two_fa_code": "123456"  # Provided by LLM or other system
    }
    
    config_2fa = WebsiteConfig(
        url="https://example.com/login",
        strategy=LoginStrategy.TWO_FACTOR,
        username_selector="input[name='email']",
        password_selector="input[name='password']",
        submit_selector="button[type='submit']",
        two_fa_selector="input[name='otp']",
        expected_url_after_login="https://example.com/dashboard",
    )
    
    logger.info("With 2FA code in credentials, login will:")
    logger.info("  1. Fill username and password")
    logger.info("  2. Submit form")
    logger.info("  3. Detect 2FA code input field")
    logger.info("  4. Automatically fill and submit 2FA code")
    logger.info("  5. Save session for future use")
    
    # Option 2: Manual 2FA (60-second window)
    logger.info("\n--- Option 2: Manual 2FA intervention ---")
    llm_credentials_manual_2fa = {
        "username": "user@example.com",
        "password": "secure_password",
        # two_fa_code not provided - will wait for manual entry
    }
    
    logger.info("Without 2FA code, login will:")
    logger.info("  1. Fill username and password")
    logger.info("  2. Submit form")
    logger.info("  3. Wait 60 seconds for manual 2FA entry")
    logger.info("  4. Save session after manual completion")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "demo-persistence":
        asyncio.run(demo_session_persistence())
    elif len(sys.argv) > 1 and sys.argv[1] == "demo-2fa":
        asyncio.run(demo_2fa_handling())
    else:
        print("Available demos:")
        print("  python example_usage_playwright.py demo-persistence  - Session persistence demo")
        print("  python example_usage_playwright.py demo-2fa          - 2FA handling demo")
