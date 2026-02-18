"""
WEBSITE CONFIGURATION & SELECTORS

In the workflow:
    test_integrated_workflow.py
        ↓
        login_playwright.py (needs selectors to find form fields)
        ↓
        website_configs_playwright.py ← YOU ARE HERE
            Provides:
            - CSS selectors for username/password fields
            - Submit button selector
            - Expected URL after login (for verification)
            - 2FA field selector
            - Timeout values
        ↓
        Used to log in and navigate Ezaango
        ↓
        staff_lookup.py (uses authenticated page)

What This File Contains:
    - WebsiteConfig dataclass definitions
    - Selectors for each website's login form
    - Expected URLs after login (for verification)
    - 2FA field selectors (for TOTP entry)

Key Configs:
    - HAHS_VIC3495_CONFIG: Main Ezaango site configuration
        url: https://hahs-vic3495.ezaango.app/login
        strategy: TWO_FACTOR (requires 2FA)
        username_selector: input[id='email'][type='email']
        password_selector: input[id='password'][type='password']
        submit_selector: button[type='submit']
        two_fa_selector: input[id='one_time_password']
        expected_url_after_login: https://hahs-vic3495.ezaango.app/

To Add New Website:
    1. Inspect login form in browser (F12)
    2. Right-click form fields
    3. Copy CSS selector
    4. Create new WebsiteConfig with selectors
    5. Call get_config("service_name") to use it

Used By:
    - login_playwright.py: Gets config to know which selectors to use
    - test_integrated_workflow.py: Passes config to login
"""

try:
    from .login_playwright import WebsiteConfig, LoginStrategy
except ImportError:
    from login_playwright import WebsiteConfig, LoginStrategy


# GitHub Login Configuration
GITHUB_CONFIG = WebsiteConfig(
    url="https://github.com/login",
    strategy=LoginStrategy.STANDARD,
    username_selector="input[name='login']",
    password_selector="input[name='password']",
    submit_selector="button[type='submit']",
    expected_url_after_login="https://github.com/",
    wait_timeout=10,
)

# LinkedIn Login Configuration
LINKEDIN_CONFIG = WebsiteConfig(
    url="https://www.linkedin.com/login",
    strategy=LoginStrategy.STANDARD,
    username_selector="input[name='email']",
    password_selector="input[name='password']",
    submit_selector="button[type='submit']",
    expected_url_after_login="https://www.linkedin.com/feed/",
    wait_timeout=15,
)

# Example Generic Login Configuration
EXAMPLE_CONFIG = WebsiteConfig(
    url="https://example.com/login",
    strategy=LoginStrategy.STANDARD,
    username_selector="input[id='username']",
    password_selector="input[id='password']",
    submit_selector="button[id='login-btn']",
    expected_url_after_login="https://example.com/dashboard",
    wait_timeout=10,
)

# HAHS VIC3495 Login Configuration
HAHS_VIC3495_CONFIG = WebsiteConfig(
    url="https://hahs-vic3495.ezaango.app/login",
    strategy=LoginStrategy.TWO_FACTOR,  # This site uses 2FA
    username_selector="input[id='email'][type='email']",      # Visible email field (not the hidden one)
    password_selector="input[id='password'][type='password']",   # Password field
    submit_selector="button[type='submit']",    # Submit button
    expected_url_after_login="https://hahs-vic3495.ezaango.app/",
    wait_timeout=15,
    two_fa_selector="input[id='one_time_password']",  # 2FA code field
)

# Website with extra fields (security questions, etc.)
EXAMPLE_WITH_EXTRAS = WebsiteConfig(
    url="https://example.com/login",
    strategy=LoginStrategy.STANDARD,
    username_selector="input[name='username']",
    password_selector="input[name='password']",
    submit_selector="button[type='submit']",
    expected_url_after_login="https://example.com/home",
    wait_timeout=10,
    extra_selectors={
        "security_answer": "input[name='security_answer']",
    }
)

# Website with Two-Factor Authentication (2FA)
EXAMPLE_WITH_2FA = WebsiteConfig(
    url="https://example.com/login",
    strategy=LoginStrategy.TWO_FACTOR,
    username_selector="input[name='username']",
    password_selector="input[name='password']",
    submit_selector="button[type='submit']",
    expected_url_after_login="https://example.com/dashboard",
    wait_timeout=10,
    two_fa_selector="input[name='otp'], input[placeholder='Enter 2FA code']",
)

# Mapping of service names to their configurations
WEBSITE_CONFIGS = {
    "github": GITHUB_CONFIG,
    "linkedin": LINKEDIN_CONFIG,
    "example_service": EXAMPLE_CONFIG,
    "hahs_vic3495": HAHS_VIC3495_CONFIG,
    "example_with_extras": EXAMPLE_WITH_EXTRAS,
    "example_with_2fa": EXAMPLE_WITH_2FA,
}


def get_config(service_name: str) -> WebsiteConfig:
    """Get website configuration by service name"""
    if service_name not in WEBSITE_CONFIGS:
        raise ValueError(f"Unknown service: {service_name}")
    return WEBSITE_CONFIGS[service_name]
