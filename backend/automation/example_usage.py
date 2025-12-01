"""
Integration example - demonstrates how login automation integrates with LLM core pipeline
The LLM reasons credentials from transcribed calls and passes them to login automation
"""

import os
import logging
from typing import Dict

try:
    from .login import LoginAutomation, WebsiteConfig, LoginStrategy
    from .website_configs import get_config
except ImportError:
    from login import LoginAutomation, WebsiteConfig, LoginStrategy
    from website_configs import get_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def login_from_llm_reasoning(
    website_config: WebsiteConfig,
    llm_reasoned_credentials: Dict,
    headless: bool = True,
) -> Dict:
    """
    Login to website using LLM-reasoned credentials
    This function is called by the LLM core pipeline
    
    Args:
        website_config: Website configuration (selectors, URLs, etc)
        llm_reasoned_credentials: Credentials reasoned out by LLM
            Format: {
                "username": "...",
                "password": "...",
                "email": "...",
                "extra_fields": {...}
            }
        headless: Run browser in headless mode
        
    Returns:
        Dictionary with results:
            {
                "success": bool,
                "scraped_content": str (page content after login),
                "error": str (if failed)
            }
    """
    try:
        logger.info(f"Starting login automation from LLM reasoning")
        
        with LoginAutomation(headless=headless, max_retries=3) as automation:
            # Attempt login with LLM credentials
            success = automation.login_with_retry(
                config=website_config,
                llm_credentials=llm_reasoned_credentials,
            )
            
            if success:
                logger.info("Login successful, scraping page content")
                
                # Scrape the page after successful login
                # This content will be processed by LLM for text-to-speech
                scraped_content = automation.scrape_page_content()
                
                return {
                    "success": True,
                    "scraped_content": scraped_content,
                    "message": "Successfully logged in and scraped content"
                }
            else:
                return {
                    "success": False,
                    "scraped_content": None,
                    "error": "Login failed after retries"
                }
                
    except Exception as e:
        logger.error(f"Login automation failed: {e}")
        return {
            "success": False,
            "scraped_content": None,
            "error": str(e)
        }


def llm_integration_pipeline(
    transcribed_call: str,
    llm_reasoning_output: Dict,
) -> Dict:
    """
    Complete pipeline integration point
    Called by LLM core after reasoning out credentials
    
    Args:
        transcribed_call: Transcribed audio from call (context)
        llm_reasoning_output: LLM's output containing:
            {
                "service_name": "website_service",
                "credentials": {
                    "username": "...",
                    "password": "...",
                    ...
                },
                "action": "login_and_scrape"
            }
            
    Returns:
        Dictionary with:
            {
                "success": bool,
                "scraped_content": str,
                "error": str (if any)
            }
    """
    try:
        service_name = llm_reasoning_output.get("service_name")
        credentials = llm_reasoning_output.get("credentials", {})
        
        if not service_name or not credentials:
            return {
                "success": False,
                "error": "Invalid LLM reasoning output format"
            }
        
        logger.info(f"LLM pipeline: Login to {service_name}")
        
        # Get website configuration
        config = get_config(service_name)
        
        # Login with LLM-reasoned credentials
        result = login_from_llm_reasoning(
            website_config=config,
            llm_reasoned_credentials=credentials,
            headless=os.getenv("HEADLESS", "true").lower() == "true"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"LLM pipeline failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


# Example usage showing how this integrates with LLM core
if __name__ == "__main__":
    # Simulated LLM reasoning output after transcription
    llm_reasoning = {
        "service_name": "example_service",
        "credentials": {
            "username": "demo_user",
            "password": "demo_pass",
            "email": "demo@example.com",
            "extra_fields": {}
        },
        "action": "login_and_scrape"
    }
    
    # Simulated transcribed call (context for LLM)
    transcribed_call = "Login to example service with credentials"
    
    # Execute pipeline
    print("="*60)
    print("LLM CORE PIPELINE INTEGRATION EXAMPLE")
    print("="*60)
    
    result = llm_integration_pipeline(
        transcribed_call=transcribed_call,
        llm_reasoning_output=llm_reasoning,
    )
    
    print(f"\nResult: {result['success']}")
    if result.get('error'):
        print(f"Error: {result['error']}")
    if result.get('scraped_content'):
        print(f"Scraped content length: {len(result['scraped_content'])} characters")
