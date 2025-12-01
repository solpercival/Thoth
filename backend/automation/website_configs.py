"""
Example configuration file for different websites
Customize selectors based on actual website structure
"""

from automation.login import WebsiteConfig, LoginStrategy


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

# Website with extra fields (security questions, 2FA code, etc.)
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
        "2fa_code": "input[name='otp']",
    }
)

# Mapping of service names to their configurations
WEBSITE_CONFIGS = {
    "github": GITHUB_CONFIG,
    "linkedin": LINKEDIN_CONFIG,
    "example_service": EXAMPLE_CONFIG,
    "example_with_extras": EXAMPLE_WITH_EXTRAS,
}


def get_config(service_name: str) -> WebsiteConfig:
    """Get website configuration by service name"""
    if service_name not in WEBSITE_CONFIGS:
        raise ValueError(f"Unknown service: {service_name}")
    return WEBSITE_CONFIGS[service_name]
