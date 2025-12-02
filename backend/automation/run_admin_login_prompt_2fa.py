"""
Interactive runner to perform first-time admin login using Playwright when
you only have username, password and an authenticator app on your phone.

Behavior:
- Attempts to fetch admin credentials from `credentials_api` for `service_name`.
- Opens a visible Playwright browser (headless=False).
- Prompts you on the terminal to read the current code from your authenticator app and paste it.
- Supplies the code to the Playwright login flow so the session is saved to `.sessions/{service_name}_admin_auth.json`.

Usage (PowerShell from `backend/automation`):
    python .\run_admin_login_prompt_2fa.py hahs_vic3495

If `CREDENTIALS_API_URL` is not running or you prefer to type credentials manually, the script will prompt for username/password.
"""
import os
import asyncio
import getpass
import logging
from typing import Optional

try:
    from .credentials_client import get_admin_credentials
    from .login_playwright import LoginAutomation
    from .website_configs_playwright import get_config
except Exception:
    from credentials_client import get_admin_credentials
    from login_playwright import LoginAutomation
    from website_configs_playwright import get_config

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


async def run_prompt_login(service_name: str):
    # Try to fetch admin credentials from credentials API
    creds = get_admin_credentials(service_name)
    if not creds:
        print(f"Could not fetch admin credentials for '{service_name}'.")
        print("You can either start your credentials API or enter credentials manually.")
        username = input("Username: ").strip()
        password = getpass.getpass("Password: ")
        creds = {"username": username, "password": password}

    # Prompt user for TOTP code
    print("")
    print("Open your authenticator app on your phone and get the current 6-digit code.")
    two_fa = input("Enter the 2FA code: ").strip()

    # Add two_fa_code into credentials dict expected by login_playwright
    creds_with_2fa = dict(creds)
    creds_with_2fa["two_fa_code"] = two_fa

    # Load website config
    try:
        config = get_config(service_name)
    except Exception as e:
        print(f"Failed to get website config for '{service_name}': {e}")
        return

    # Run Playwright login in visible mode to capture any UI differences
    async with LoginAutomation(headless=False, max_retries=1, session_dir=".sessions") as automation:
        print("Opening browser and attempting login. Watch the browser and enter the code if needed.")
        success = await automation.login_with_retry(config=config, service_name=f"{service_name}_admin", llm_credentials=creds_with_2fa)
        if success:
            print("Login successful — session saved to .sessions/")
        else:
            print("Login failed. Check the browser for errors and try again.")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python run_admin_login_prompt_2fa.py <service_name>")
        print("Example: python run_admin_login_prompt_2fa.py hahs_vic3495")
        sys.exit(1)

    svc = sys.argv[1]
    asyncio.run(run_prompt_login(svc))
