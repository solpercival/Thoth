"""
Interactive runner to perform admin login using Playwright.
Always performs fresh login (no session caching).

Usage (PowerShell from `backend/automation`):
    python .\run_admin_login_prompt_2fa.py hahs_vic3495
"""
import asyncio
import logging

try:
    from .secrets import get_admin_credentials, get_admin_totp_code
    from .login_playwright import LoginAutomation
    from .website_configs_playwright import get_config
except (ImportError, ValueError):
    from secrets import get_admin_credentials, get_admin_totp_code
    from login_playwright import LoginAutomation
    from website_configs_playwright import get_config

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


async def run_prompt_login(service_name: str):
    """Perform fresh login with automatic TOTP code generation."""
    print(f"Attempting login for '{service_name}'...")
    
    # Try to fetch admin credentials from credentials API
    creds = get_admin_credentials(service_name)
    if not creds:
        print(f"Could not fetch admin credentials from credentials API for '{service_name}'.")
        print("Enter credentials manually:")
        username = input("Username: ").strip()
        password = getpass.getpass("Password: ")
        creds = {"username": username, "password": password}
    else:
        print(f"✓ Fetched credentials from API for '{service_name}'")

    # Generate TOTP code automatically from secret
    print("")
    two_fa_code = get_admin_totp_code(service_name)
    if not two_fa_code:
        print("⚠ Warning: Could not generate TOTP code from secrets.")
        print("Open your authenticator app on your phone and get the current 6-digit code.")
        two_fa = input("Enter the 2FA code (or press Enter to skip): ").strip()
        two_fa_code = two_fa if two_fa else None
    else:
        print(f"✓ Generated TOTP code automatically: {two_fa_code}")

    # Add two_fa_code into credentials dict expected by login_playwright
    creds_with_2fa = dict(creds)
    if two_fa_code:
        creds_with_2fa["two_fa_code"] = two_fa_code

    # Load website config
    try:
        config = get_config(service_name)
    except Exception as e:
        print(f"Failed to get website config for '{service_name}': {e}")
        return

    # Run Playwright login in visible mode
    async with LoginAutomation(headless=False, max_retries=1, session_dir=".sessions") as automation:
        print("Opening browser and attempting login...")
        success = await automation.login_with_retry(config=config, service_name=f"{service_name}_admin", llm_credentials=creds_with_2fa)
        if success:
            print("✓ Login successful!")
            print("\nBrowser window is open. Check if you're logged in properly.")
            print("Press Enter to close the browser...")
            input()
        else:
            print("✗ Login failed. Check the browser for errors and try again.")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python run_admin_login_prompt_2fa.py <service_name>")
        print("Example: python run_admin_login_prompt_2fa.py hahs_vic3495")
        sys.exit(1)

    svc = sys.argv[1]
    asyncio.run(run_prompt_login(svc))

