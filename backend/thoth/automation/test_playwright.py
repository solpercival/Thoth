"""
Quick Playwright smoke test.
Checks that Playwright is installed and can open a browser.

Usage (from backend/):
    python -m thoth.automation.test_playwright
"""
import asyncio
from playwright.async_api import async_playwright


async def test_playwright():
    print("Starting Playwright smoke test...")

    async with async_playwright() as p:
        print("[OK] Playwright imported and started")

        browser = await p.chromium.launch(headless=False)
        print("[OK] Chromium browser launched")

        page = await browser.new_page()
        print("[OK] New page created")

        await page.goto("https://example.com")
        title = await page.title()
        print(f"[OK] Navigated to example.com — title: '{title}'")

        await page.screenshot(path="test_playwright_screenshot.png")
        print("[OK] Screenshot saved to test_playwright_screenshot.png")

        print("\nBrowser is open. Press Enter to close...")
        input()

        await browser.close()
        print("[OK] Browser closed")

    print("\nPlaywright is working correctly.")


if __name__ == "__main__":
    asyncio.run(test_playwright())
