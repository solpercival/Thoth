"""
BROWSER AUTOMATION & 2FA LOGIN MODULE

In the workflow:
    test_integrated_workflow.py
        ↓
        login_playwright.py ← YOU ARE HERE
            Uses:
            - website_configs_playwright.py (selectors + expected URLs)
            - secrets.py (get TOTP codes for 2FA)
        ↓
        Returns authenticated page object to test_integrated_workflow.py
            (which then uses it with staff_lookup.py and shift_date_reasoner.py)

Key Classes:
    - PlaywrightAutoLogin: Low-level browser automation
        Methods: login_standard(), login_with_llm_credentials(), login()
    
    - LoginAutomation: High-level orchestrator (context manager)
        Methods: login_with_retry(), get_page(), close()
        
Main Functions:
    - Handles website login (username/password)
    - Detects and fills 2FA codes automatically
    - Waits for page navigation to complete (key fix!)
    - Saves/loads session state for persistence
    - Takes screenshots on errors for debugging

Flow Within This Module:
    1. LoginAutomation.__init__()
        → Creates PlaywrightAutoLogin instance
    2. login_with_retry()
        → Calls login_with_llm_credentials()
        → Which calls PlaywrightAutoLogin.login()
        → Which calls login_standard()
    3. login_standard() does:
        → Check if already logged in (session cached)
        → Navigate to login URL (with timeout handling)
        → Fill username field
        → Fill password field
        → Click submit button
        → Detect and fill 2FA field
        → WAIT FOR NAVIGATION (this was the async bug!)
        → Verify login success
        → Save session for next time

Critical Fix Applied:
    Added: await self.page.wait_for_url("**/home**", timeout=10000)
    This ensures page completes navigation to home before returning.
    Without this, subsequent functions would fail with "Still on login page" errors.

Dependencies:
    - website_configs_playwright.py: Provides selector strings and expected URLs
    - secrets.py: Generates TOTP codes for 2FA
    - playwright library: Browser automation

Used By:
    - test_integrated_workflow.py: Main workflow orchestrator
    - Other test files that need to log in
"""

import os
import asyncio
import logging
import json
from typing import Dict, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path

from playwright.async_api import async_playwright, BrowserContext, Page, expect

from thoth.automation.secrets import get_admin_totp_code

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class LoginStrategy(Enum):
    """Different login strategies for various websites"""
    STANDARD = "standard"  # username/password form
    OAUTH = "oauth"  # OAuth-based login
    SSO = "sso"  # Single sign-on
    API = "api"  # Direct API authentication
    TWO_FACTOR = "2fa"  # Two-factor authentication


@dataclass
class Credentials:
    """Data class to hold user credentials (from LLM reasoning)"""
    username: str
    password: str
    email: Optional[str] = None
    extra_fields: Optional[Dict[str, str]] = None
    two_fa_code: Optional[str] = None  # For 2FA support

    @classmethod
    def from_llm_output(cls, llm_output: Dict) -> "Credentials":
        """
        Create Credentials object from LLM reasoning output
        
        Args:
            llm_output: Dictionary with LLM-reasoned credentials
                Expected keys: 'username', 'password', optionally 'email', 'extra_fields', 'two_fa_code'
                
        Returns:
            Credentials object
        """
        return cls(
            username=llm_output.get("username", ""),
            password=llm_output.get("password", ""),
            email=llm_output.get("email"),
            extra_fields=llm_output.get("extra_fields", {}),
            two_fa_code=llm_output.get("two_fa_code"),
        )


@dataclass
class WebsiteConfig:
    """Configuration for website login"""
    url: str
    strategy: LoginStrategy
    username_selector: str
    password_selector: str
    submit_selector: str
    expected_url_after_login: Optional[str] = None
    wait_timeout: int = 10
    extra_selectors: Optional[Dict[str, str]] = None
    two_fa_selector: Optional[str] = None  # Selector for 2FA code input


class PlaywrightAutoLogin:
    """Handles automated website login using Playwright with session persistence"""

    def __init__(
        self,
        headless: bool = True,
        user_agent: Optional[str] = None,
        session_dir: str = ".sessions",
    ):
        """
        Initialize the Playwright automation client
        
        Args:
            headless: Run browser in headless mode
            user_agent: Custom user agent string (optional)
            session_dir: Directory to store session authentication states
        """
        self.headless = headless
        self.user_agent = user_agent or self._default_user_agent()
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.browser = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    @staticmethod
    def _default_user_agent() -> str:
        """Get a default user agent"""
        return (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

    def _get_session_path(self, service_name: str) -> Path:
        """Get the session file path for a service"""
        return self.session_dir / f"{service_name}_auth.json"

    async def _initialize_browser(self):
        """Initialize Playwright browser"""
        try:
            p = await async_playwright().start()
            self.browser = await p.chromium.launch(headless=self.headless)
            logger.info("Playwright browser initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Playwright browser: {e}")
            raise

    async def _initialize_context(
        self, service_name: str, use_saved_session: bool = True
    ):
        """
        Initialize browser context, optionally loading saved session
        
        Args:
            service_name: Name of the service (used for session file)
            use_saved_session: Whether to load saved authentication state if available
        """
        if not self.browser:
            await self._initialize_browser()

        # Ensure browser is initialized
        if self.browser is None:
            logger.error("Browser is not initialized. Cannot create context.")
            raise RuntimeError("Browser is not initialized.")

        context_options = {
            "user_agent": self.user_agent,
            "viewport": {"width": 1280, "height": 720},
        }

        # Load saved session if available and requested
        session_path = self._get_session_path(service_name)
        if use_saved_session and session_path.exists():
            try:
                context_options["storage_state"] = str(session_path)
                logger.info(f"Loading saved session from {session_path}")
            except Exception as e:
                logger.warning(f"Failed to load session: {e}")

        self.context = await self.browser.new_context(**context_options)
        self.page = await self.context.new_page()
        logger.info("Playwright context initialized")

    async def _save_session(self, service_name: str):
        """Save current browser context/session for future use"""
        if not self.context:
            logger.warning("No context to save")
            return

        try:
            session_path = self._get_session_path(service_name)
            await self.context.storage_state(path=str(session_path))
            logger.info(f"Session saved to {session_path}")
        except Exception as e:
            logger.error(f"Failed to save session: {e}")

    async def _find_element(self, selector: str, timeout: int = 10):
        """
        Find element with explicit wait
        
        Args:
            selector: CSS selector or XPath
            timeout: Wait timeout in seconds
            
        Returns:
            Page locator
        """
        if not self.page:
            raise RuntimeError("Page not initialized")

        locator = self.page.locator(selector)
        await locator.wait_for(timeout=timeout * 1000)
        return locator

    async def login_standard(
        self, config: WebsiteConfig, credentials: Credentials, service_name: str, use_saved_session: bool = True
    ) -> bool:
        """
        Standard username/password login with optional 2FA.
        
        Multi-step flow:
        1. Fill username and password.
        2. Click the first form's submit button (specifically for the login form, not 2FA).
        3. Wait for 2FA modal/window to appear (if 2FA is enabled).
        4. Fill 2FA code and submit.
        5. Verify login success.
        
        Args:
            config: Website configuration
            credentials: User credentials
            service_name: Name of the service (for session management)
            
        Returns:
            True if login successful, False otherwise
        """
        try:
            logger.info(f"Attempting login to {config.url}")
            
            await self._initialize_context(service_name, use_saved_session=use_saved_session)
            
            if not self.page:
                logger.error("Page failed to initialize")
                return False

            await self.page.goto(config.url, wait_until="domcontentloaded", timeout=15000)
            logger.info(f"Navigated to login page: {self.page.url}")

            # Check if already logged in (saved session redirect)
            if self.page.url != config.url and config.expected_url_after_login:
                expected_path = config.expected_url_after_login.rstrip("/")
                current_path = self.page.url.rstrip("/")
                if expected_path == current_path or current_path.startswith(expected_path + "/"):
                    logger.info(f"✓ Already logged in! Skipping login form. Current URL: {self.page.url}")
                    return True

            # Step 1: Fill username field
            logger.info(f"Step 1: Looking for username field: {config.username_selector}")
            username_locator = await self._find_element(
                config.username_selector, timeout=config.wait_timeout
            )
            await username_locator.fill(credentials.username)
            logger.info("Username entered")

            # Step 2: Fill password field
            logger.info(f"Step 2: Looking for password field: {config.password_selector}")
            password_locator = await self._find_element(
                config.password_selector, timeout=config.wait_timeout
            )
            await password_locator.fill(credentials.password)
            logger.info("Password entered")

            # Step 3: Handle extra fields if present (security questions, etc.)
            if config.extra_selectors and credentials.extra_fields:
                for field_name, selector in config.extra_selectors.items():
                    if field_name in credentials.extra_fields:
                        try:
                            extra_locator = await self._find_element(selector)
                            await extra_locator.fill(credentials.extra_fields[field_name])
                            logger.info(f"Extra field '{field_name}' filled")
                        except Exception as e:
                            logger.warning(f"Failed to fill extra field '{field_name}': {e}")

            # Step 4: Click the login form's submit button (the "Log In" button, not 2FA)
            logger.info(f"Step 4: Looking for login form submit button: {config.submit_selector}")
            # Use first() to get the first match (avoid strict mode violation with multiple submit buttons)
            submit_locator = self.page.locator(config.submit_selector).first
            await submit_locator.wait_for(timeout=config.wait_timeout * 1000)
            await submit_locator.click()
            logger.info("Login form submitted, waiting for page transition...")

            # Step 5: Wait for navigation to complete (may be 2FA screen or dashboard)
            await self.page.wait_for_load_state("networkidle")
            logger.info(f"Page loaded after form submission. Current URL: {self.page.url}")

            # Step 6: Handle 2FA if expected
            if config.strategy == LoginStrategy.TWO_FACTOR or config.two_fa_selector:
                logger.info("Step 6: 2FA strategy detected, checking for 2FA modal/field...")
                
                # Wait for the 2FA input field to exist in DOM (may not be visible yet)
                try:
                    two_fa_selector = config.two_fa_selector or "input[id='one_time_password']"
                    logger.info(f"Waiting for 2FA field: {two_fa_selector}")
                    
                    # Wait up to 30 seconds for the 2FA input to exist in DOM (don't require visibility yet)
                    await self.page.wait_for_selector(two_fa_selector, timeout=30000)
                    logger.info("2FA input field found in DOM!")
                    
                    # Try to scroll it into view if it's hidden
                    try:
                        two_fa_locator = self.page.locator(two_fa_selector).first
                        await two_fa_locator.scroll_into_view_if_needed()
                    except:
                        pass  # Element might not support scrolling, continue anyway
                    
                    # Try to get 2FA code from credentials, or generate from TOTP secret
                    two_fa_code = credentials.two_fa_code
                    
                    if not two_fa_code:
                        # Try to generate TOTP code from stored secret
                        try:
                            logger.info(f"Generating TOTP code for {service_name}...")
                            two_fa_code = get_admin_totp_code(service_name)
                            logger.info("✓ TOTP code generated successfully")
                        except ValueError as e:
                            logger.warning(f"TOTP auto-generation failed: {e}")
                    
                    if two_fa_code:
                        # Fill the 2FA code (even if hidden, we can still fill it)
                        try:
                            two_fa_locator = self.page.locator(two_fa_selector).first
                            await two_fa_locator.fill(two_fa_code)
                            logger.info("2FA code entered")
                        except Exception as e:
                            logger.warning(f"Failed to fill 2FA code: {e}")
                        
                        # Find and click the 2FA submit button (use id selector for precision)
                        logger.info("Looking for 2FA submit button...")
                        try:
                            two_fa_submit = self.page.locator("#check_otp").first
                            await two_fa_submit.wait_for(timeout=10000)
                            await two_fa_submit.click()
                            logger.info("2FA form submitted")
                        except Exception as e:
                            logger.warning(f"Failed to click 2FA submit button: {e}")
                        
                        # Wait for post-2FA navigation
                        await self.page.wait_for_load_state("networkidle")
                        logger.info(f"Page loaded after 2FA. Current URL: {self.page.url}")
                        
                        # Explicitly wait for navigation to home page
                        try:
                            logger.info("Waiting for navigation to home page...")
                            await self.page.wait_for_url("**/home**", timeout=10000)
                            logger.info(f"✓ Successfully navigated to home. URL: {self.page.url}")
                        except Exception as e:
                            logger.warning(f"Did not reach /home within timeout: {e}")
                            logger.info(f"Current URL after 2FA: {self.page.url}")
                    else:
                        logger.info("2FA field found but no code available. Waiting for manual intervention (60 seconds)...")
                        await asyncio.sleep(60)
                        
                except Exception as e:
                    logger.warning(f"2FA modal did not appear or error occurred: {e}")
                    logger.info("Assuming manual 2FA intervention is required, waiting 60 seconds...")
                    await asyncio.sleep(60)  # Give user 60 seconds to manually enter 2FA
            else:
                logger.info("No 2FA strategy configured")

            # Step 7: Verify login success
            logger.info("Step 7: Verifying login success...")
            if config.expected_url_after_login:
                current_url = self.page.url
                # Check if the expected URL is the actual page (not just a substring)
                # This prevents false positives where /login contains /
                expected_path = config.expected_url_after_login.rstrip("/")
                current_path = current_url.rstrip("/")
                
                if expected_path == current_path or current_path.startswith(expected_path + "/"):
                    logger.info(f"✓ Login successful! Current URL: {current_url}")
                    await self._save_session(service_name)
                    return True
                else:
                    logger.warning(
                        f"✗ Expected URL '{config.expected_url_after_login}' but got '{current_url}'"
                    )
                    await self.take_screenshot(f"login_failed_{service_name}.png")
                    logger.info(f"Debug screenshot saved: login_failed_{service_name}.png")
                    return False
            else:
                current_url = self.page.url
                logger.info(f"✓ Login form completed. Current URL: {current_url}")
                await self._save_session(service_name)
                return True

        except asyncio.TimeoutError as e:
            logger.error(f"✗ Timeout during login to {config.url}: {e}")
            if self.page:
                await self.take_screenshot(f"timeout_{service_name}.png")
                logger.info(f"Debug screenshot saved: timeout_{service_name}.png")
            return False
        except Exception as e:
            logger.error(f"✗ Login failed with error: {e}", exc_info=True)
            if self.page:
                await self.take_screenshot(f"error_{service_name}.png")
                logger.info(f"Debug screenshot saved: error_{service_name}.png")
            return False

    async def login(
        self, config: WebsiteConfig, credentials: Credentials, service_name: str, use_saved_session: bool = True
    ) -> bool:
        """
        Main login method that dispatches to appropriate strategy
        
        Args:
            config: Website configuration
            credentials: User credentials
            service_name: Service name for session management
            use_saved_session: Whether to load and use saved sessions (default True)
            
        Returns:
            True if login successful, False otherwise
        """
        if not self.browser:
            await self._initialize_browser()

        if config.strategy in [LoginStrategy.STANDARD, LoginStrategy.TWO_FACTOR]:
            return await self.login_standard(config, credentials, service_name, use_saved_session=use_saved_session)
        else:
            logger.warning(f"Strategy {config.strategy} not yet implemented")
            return False

    async def take_screenshot(self, filename: str):
        """Take a screenshot for debugging"""
        if self.page:
            await self.page.screenshot(path=filename)
            logger.info(f"Screenshot saved to {filename}")

    async def get_page_source(self) -> str:
        """Get the current page source"""
        if self.page:
            return await self.page.content()
        return ""

    async def close(self):
        """Close the browser and context"""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        logger.info("Playwright browser closed")


class LoginAutomation:
    """Main orchestrator for login automation - receives LLM-reasoned credentials"""

    def __init__(
        self,
        headless: bool = True,
        max_retries: int = 3,
        retry_delay: int = 5,
        session_dir: str = ".sessions",
        use_saved_session: bool = True,
    ):
        """
        Initialize login automation
        
        Args:
            headless: Run browser in headless mode
            max_retries: Maximum number of login attempts
            retry_delay: Delay between retries in seconds
            session_dir: Directory to store session authentication states
            use_saved_session: Whether to load and use saved sessions (default True)
        """
        self.auto_login = PlaywrightAutoLogin(headless=headless, session_dir=session_dir)
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.use_saved_session = use_saved_session
        self.last_scraped_content: Optional[str] = None

    async def login_with_llm_credentials(
        self, config: WebsiteConfig, service_name: str, llm_credentials: Dict, use_saved_session: bool = True
    ) -> bool:
        """
        Login using credentials reasoned out by LLM
        
        Args:
            config: Website configuration
            service_name: Service name for session management
            llm_credentials: Dictionary with LLM-reasoned credentials
                Expected keys: 'username', 'password', optionally 'email', 'extra_fields', 'two_fa_code'
            use_saved_session: Whether to load and use saved sessions (default True)
            
        Returns:
            True if login successful, False otherwise
        """
        try:
            # Convert LLM output to Credentials object
            credentials = Credentials.from_llm_output(llm_credentials)
            
            logger.info(f"Attempting login to {config.url} with LLM-reasoned credentials")
            return await self.auto_login.login(config, credentials, service_name, use_saved_session=use_saved_session)
            
        except Exception as e:
            logger.error(f"Login failed with error: {e}")
            return False

    async def login_with_retry(
        self,
        config: WebsiteConfig,
        service_name: str,
        llm_credentials: Dict,
        attempt: int = 1,
    ) -> bool:
        """
        Login with automatic retry on failure
        
        Args:
            config: Website configuration
            service_name: Service name for session management
            llm_credentials: LLM-reasoned credentials dictionary
            attempt: Current attempt number (internal use)
            
        Returns:
            True if login successful, False otherwise
        """
        if attempt > self.max_retries:
            logger.error(f"Failed to login after {self.max_retries} attempts")
            return False

        try:
            logger.info(f"Login attempt {attempt}/{self.max_retries}")
            
            success = await self.login_with_llm_credentials(
                config, service_name, llm_credentials, use_saved_session=self.use_saved_session
            )
            
            if success:
                logger.info("Successfully logged in")
                return True
            else:
                if attempt < self.max_retries:
                    logger.warning(f"Login attempt {attempt} failed")
                    logger.info(f"Retrying in {self.retry_delay} seconds...")
                    await asyncio.sleep(self.retry_delay)
                    return await self.login_with_retry(
                        config, service_name, llm_credentials, attempt + 1
                    )
                return False
                
        except Exception as e:
            logger.error(f"Attempt {attempt} failed with error: {e}")
            if attempt < self.max_retries:
                await asyncio.sleep(self.retry_delay)
                return await self.login_with_retry(
                    config, service_name, llm_credentials, attempt + 1
                )
            return False

    async def scrape_page_content(self) -> str:
        """
        Scrape current page content after login
        Called by web scraper component of pipeline
        
        Returns:
            Page content/HTML
        """
        try:
            content = await self.auto_login.get_page_source()
            self.last_scraped_content = content
            logger.info("Page content scraped successfully")
            return content
        except Exception as e:
            logger.error(f"Failed to scrape page: {e}")
            return ""

    async def navigate_and_scrape(self, url: str) -> str:
        """
        Navigate to a specific URL and scrape page content
        
        Args:
            url: URL to navigate to
            
        Returns:
            Page content/HTML
        """
        try:
            if not self.auto_login.page:
                logger.error("No active page - login may have failed")
                return ""
            
            await self.auto_login.page.goto(url, wait_until="networkidle")
            content = await self.auto_login.get_page_source()
            self.last_scraped_content = content
            logger.info(f"Navigated to {url} and scraped successfully")
            return content
        except Exception as e:
            logger.error(f"Failed to navigate and scrape {url}: {e}")
            return ""

    async def get_page(self):
        """
        Get the underlying Playwright page object (for advanced operations like staff lookup)
        
        Returns:
            Playwright Page object or None
        """
        return self.auto_login.page if hasattr(self.auto_login, 'page') else None

    async def take_screenshot(self, filename: str):
        """Take a screenshot for debugging"""
        await self.auto_login.take_screenshot(filename)

    async def close(self):
        """Close the browser"""
        await self.auto_login.close()

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()


# Example usage - receives credentials from LLM core
async def main():
    """Example usage demonstrating session persistence and 2FA handling"""
    
    # Example LLM-reasoned credentials output
    example_llm_credentials = {
        "username": "test_user",
        "password": "test_password",
        "email": "user@example.com",
        "extra_fields": {},
        # Optional: if 2FA code is available
        # "two_fa_code": "123456"
    }

    # Example configuration
    example_config = WebsiteConfig(
        url="https://hahs-vic3495.ezaango.app/login",
        strategy=LoginStrategy.STANDARD,
        username_selector="input[name='username']",
        password_selector="input[name='password']",
        submit_selector="button[type='submit']",
        expected_url_after_login="https://hahs-vic3495.ezaango.app/",
        wait_timeout=15,
    )

    # Initialize automation with session directory
    async with LoginAutomation(headless=False, max_retries=3, session_dir=".sessions") as automation:
        success = await automation.login_with_retry(
            config=example_config,
            service_name="hahs_vic3495",
            llm_credentials=example_llm_credentials,
        )
        
        if success:
            print("Login successful!")
            await automation.take_screenshot("login_success.png")
            
            # Scrape page content for LLM processing
            content = await automation.scrape_page_content()
            print(f"Scraped {len(content)} characters")
        else:
            print("Login failed!")
        
        await automation.close()


if __name__ == "__main__":
    asyncio.run(main())
