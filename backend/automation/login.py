"""
Automated Login Script - Receives LLM-reasoned credentials and logs into websites
Integrates with core LLM pipeline for credential reasoning and web scraping
"""

import os
import time
import logging
from typing import Dict, Optional, List
from dataclasses import dataclass
from enum import Enum

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    WebDriverException,
)

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


@dataclass
class Credentials:
    """Data class to hold user credentials (from LLM reasoning)"""
    username: str
    password: str
    email: Optional[str] = None
    extra_fields: Optional[Dict[str, str]] = None

    @classmethod
    def from_llm_output(cls, llm_output: Dict) -> "Credentials":
        """
        Create Credentials object from LLM reasoning output
        
        Args:
            llm_output: Dictionary with LLM-reasoned credentials
                Expected keys: 'username', 'password', optionally 'email', 'extra_fields'
                
        Returns:
            Credentials object
        """
        return cls(
            username=llm_output.get("username", ""),
            password=llm_output.get("password", ""),
            email=llm_output.get("email"),
            extra_fields=llm_output.get("extra_fields", {}),
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


class WebsiteAutoLogin:
    """Handles automated website login using Selenium"""

    def __init__(
        self,
        headless: bool = True,
        implicit_wait: int = 10,
        user_agent: Optional[str] = None,
    ):
        """
        Initialize the web automation client
        
        Args:
            headless: Run browser in headless mode
            implicit_wait: Implicit wait time in seconds
            user_agent: Custom user agent string (optional)
        """
        self.headless = headless
        self.implicit_wait = implicit_wait
        self.user_agent = user_agent or self._default_user_agent()
        self.driver: Optional[webdriver.Chrome] = None

    @staticmethod
    def _default_user_agent() -> str:
        """Get a default user agent"""
        return (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )

    def _initialize_driver(self):
        """Initialize Selenium WebDriver"""
        try:
            options = webdriver.ChromeOptions()
            if self.headless:
                options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument(f"user-agent={self.user_agent}")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option(
                "excludeSwitches", ["enable-automation"]
            )
            options.add_experimental_option("useAutomationExtension", False)

            self.driver = webdriver.Chrome(options=options)
            self.driver.implicitly_wait(self.implicit_wait)
            logger.info("WebDriver initialized successfully")
        except WebDriverException as e:
            logger.error(f"Failed to initialize WebDriver: {e}")
            raise

    def _find_element(self, selector: str, by: str = By.CSS_SELECTOR, timeout: int = 10):
        """
        Find element with explicit wait
        
        Args:
            selector: CSS selector or XPath
            by: By method (default: CSS_SELECTOR)
            timeout: Wait timeout in seconds
            
        Returns:
            WebElement
        """
        if not self.driver:
            raise RuntimeError("WebDriver not initialized")

        wait = WebDriverWait(self.driver, timeout)
        return wait.until(EC.presence_of_element_located((by, selector)))

    def login_standard(
        self, config: WebsiteConfig, credentials: Credentials
    ) -> bool:
        """
        Standard username/password login
        
        Args:
            config: Website configuration
            credentials: User credentials
            
        Returns:
            True if login successful, False otherwise
        """
        try:
            logger.info(f"Attempting login to {config.url}")
            if self.driver is None:
                self._initialize_driver()
            if self.driver is None:
                logger.error("WebDriver failed to initialize.")
                return False
            self.driver.get(config.url)
            time.sleep(2)  # Wait for page to load

            # Fill username field
            username_element = self._find_element(
                config.username_selector, timeout=config.wait_timeout
            )
            username_element.clear()
            username_element.send_keys(credentials.username)
            logger.debug("Username entered")

            # Fill password field
            password_element = self._find_element(
                config.password_selector, timeout=config.wait_timeout
            )
            password_element.clear()
            password_element.send_keys(credentials.password)
            logger.debug("Password entered")

            # Handle extra fields if present
            if config.extra_selectors and credentials.extra_fields:
                for field_name, selector in config.extra_selectors.items():
                    if field_name in credentials.extra_fields:
                        extra_element = self._find_element(selector)
                        extra_element.clear()
                        extra_element.send_keys(credentials.extra_fields[field_name])
                        logger.debug(f"Extra field '{field_name}' entered")

            # Submit form
            submit_element = self._find_element(
                config.submit_selector, timeout=config.wait_timeout
            )
            submit_element.click()
            logger.debug("Form submitted")

            time.sleep(3)  # Wait for login to complete

            # Verify login if expected URL provided
            if config.expected_url_after_login:
                if self.driver and config.expected_url_after_login in self.driver.current_url:
                    logger.info(f"Login successful. Current URL: {self.driver.current_url}")
                    return True
                else:
                    current_url = self.driver.current_url if self.driver else "Driver not initialized"
                    logger.warning(
                        f"Expected URL '{config.expected_url_after_login}' "
                        f"not found. Current URL: {current_url}"
                    )
                    return False
            else:
                current_url = self.driver.current_url if self.driver else "Driver not initialized"
                logger.info(f"Login form submitted. Current URL: {current_url}")
                return True

        except TimeoutException:
            logger.error(f"Timeout waiting for element during login to {config.url}")
            return False
        except NoSuchElementException as e:
            logger.error(f"Element not found during login: {e}")
            return False
        except Exception as e:
            logger.error(f"Login failed with error: {e}")
            return False

    def login(self, config: WebsiteConfig, credentials: Credentials) -> bool:
        """
        Main login method that dispatches to appropriate strategy
        
        Args:
            config: Website configuration
            credentials: User credentials
            
        Returns:
            True if login successful, False otherwise
        """
        if not self.driver:
            self._initialize_driver()

        if config.strategy == LoginStrategy.STANDARD:
            return self.login_standard(config, credentials)
        else:
            logger.warning(f"Strategy {config.strategy} not yet implemented")
            return False

    def take_screenshot(self, filename: str):
        """Take a screenshot for debugging"""
        if self.driver:
            self.driver.save_screenshot(filename)
            logger.info(f"Screenshot saved to {filename}")

    def get_page_source(self) -> str:
        """Get the current page source"""
        if self.driver:
            return self.driver.page_source
        return ""

    def close(self):
        """Close the WebDriver"""
        if self.driver:
            self.driver.quit()
            logger.info("WebDriver closed")

    def __enter__(self):
        """Context manager entry"""
        if not self.driver:
            self._initialize_driver()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


class LoginAutomation:
    """Main orchestrator for login automation - receives LLM-reasoned credentials"""

    def __init__(
        self,
        headless: bool = True,
        max_retries: int = 3,
        retry_delay: int = 5,
    ):
        """
        Initialize login automation
        
        Args:
            headless: Run browser in headless mode
            max_retries: Maximum number of login attempts
            retry_delay: Delay between retries in seconds
        """
        self.auto_login = WebsiteAutoLogin(headless=headless)
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.last_scraped_content: Optional[str] = None

    def login_with_llm_credentials(
        self, config: WebsiteConfig, llm_credentials: Dict
    ) -> bool:
        """
        Login using credentials reasoned out by LLM
        
        Args:
            config: Website configuration
            llm_credentials: Dictionary with LLM-reasoned credentials
                Expected keys: 'username', 'password', optionally 'email', 'extra_fields'
            
        Returns:
            True if login successful, False otherwise
        """
        try:
            # Convert LLM output to Credentials object
            credentials = Credentials.from_llm_output(llm_credentials)
            
            logger.info(f"Attempting login to {config.url} with LLM-reasoned credentials")
            return self.auto_login.login(config, credentials)
            
        except Exception as e:
            logger.error(f"Login failed with error: {e}")
            return False

    def login_with_retry(
        self,
        config: WebsiteConfig,
        llm_credentials: Dict,
        attempt: int = 1,
    ) -> bool:
        """
        Login with automatic retry on failure
        
        Args:
            config: Website configuration
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
            
            success = self.login_with_llm_credentials(config, llm_credentials)
            
            if success:
                logger.info("Successfully logged in")
                return True
            else:
                if attempt < self.max_retries:
                    logger.warning(f"Login attempt {attempt} failed")
                    logger.info(f"Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                    return self.login_with_retry(config, llm_credentials, attempt + 1)
                return False
                
        except Exception as e:
            logger.error(f"Attempt {attempt} failed with error: {e}")
            if attempt < self.max_retries:
                time.sleep(self.retry_delay)
                return self.login_with_retry(config, llm_credentials, attempt + 1)
            return False

    def scrape_page_content(self) -> str:
        """
        Scrape current page content after login
        Called by web scraper component of pipeline
        
        Returns:
            Page content/HTML
        """
        try:
            content = self.auto_login.get_page_source()
            self.last_scraped_content = content
            logger.info("Page content scraped successfully")
            return content
        except Exception as e:
            logger.error(f"Failed to scrape page: {e}")
            return ""

    def take_screenshot(self, filename: str):
        """Take a screenshot for debugging"""
        if self.auto_login.driver:
            self.auto_login.driver.save_screenshot(filename)
            logger.info(f"Screenshot saved to {filename}")

    def close(self):
        """Close the WebDriver"""
        self.auto_login.close()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()





# Example usage - receives credentials from LLM core
if __name__ == "__main__":
    # Example LLM-reasoned credentials output
    example_llm_credentials = {
        "username": "test_user",
        "password": "test_password",
        "email": "user@example.com",
        "extra_fields": {}
    }

    # Example configuration
    example_config = WebsiteConfig(
        url="https://example.com/login",
        strategy=LoginStrategy.STANDARD,
        username_selector="input[name='username']",
        password_selector="input[name='password']",
        submit_selector="button[type='submit']",
        expected_url_after_login="https://example.com/dashboard",
    )

    # Initialize automation
    with LoginAutomation(headless=False, max_retries=3) as automation:
        success = automation.login_with_retry(
            config=example_config,
            llm_credentials=example_llm_credentials,
        )
        
        if success:
            print("Login successful!")
            automation.take_screenshot("login_success.png")
            
            # Scrape page content for LLM processing
            content = automation.scrape_page_content()
            print(f"Scraped {len(content)} characters")
        else:
            print("Login failed!")
