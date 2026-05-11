"""
One-time Naukri Resdex login script.

Run this ONCE to log in to Naukri manually and save the session cookies.
The scraper reuses these cookies until the session expires.

Requirements:
  - A Naukri recruiter account (free signup at www.naukri.com)
  - Free accounts get limited daily resume views (~5–10/day)
  - Paid Resdex subscription gives full access

Usage:
    python scripts/naukri_login.py
"""

import asyncio
import json
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

SESSION_FILE = os.getenv("NAUKRI_SESSION_FILE", "naukri_session.json")


async def main():
    from playwright.async_api import async_playwright

    print("=" * 55)
    print("  Naukri Resdex Session Login")
    print("=" * 55)
    print("\nA browser window will open.")
    print("1. Log in to your Naukri RECRUITER account")
    print("   (Sign up free at: https://www.naukri.com/)")
    print("2. Wait until you see the Resdex resume search page")
    print("3. Come back here and press Enter\n")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=False,
            args=["--start-maximized"],
        )
        context = await browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()
        await page.goto("https://www.naukri.com/nlogin/login")

        input("Press Enter AFTER you are fully logged in and can see the Naukri dashboard...")

        # Check current URL first — don't navigate if already on login page
        current_url = page.url
        print(f"\n  Current page: {current_url}")

        if "login" in current_url or "nlogin" in current_url:
            print("\n[WARNING] You don't appear to be logged in yet.")
            print("  Please log in fully in the browser, THEN press Enter.")
            input("  Press Enter again once logged in...")
            current_url = page.url

        # Try to navigate to recruiter dashboard to capture all session cookies
        if "login" not in current_url and "nlogin" not in current_url:
            try:
                await page.goto(
                    "https://www.naukri.com/mnjuser/homepage",
                    wait_until="domcontentloaded",
                    timeout=15_000,
                )
                await asyncio.sleep(2)
                current_url = page.url
            except Exception:
                # Navigation may be interrupted if redirected — that's OK, use current cookies
                current_url = page.url

        if "login" in current_url or "nlogin" in current_url:
            print("\n[ERROR] Still not logged in. Please run this script again after logging in.")
            await browser.close()
            return

        cookies = await context.cookies()
        Path(SESSION_FILE).write_text(json.dumps(cookies, indent=2))
        print(f"\n[OK] Session saved to '{SESSION_FILE}' ({len(cookies)} cookies)")
        print("You can now run the platform — the scraper will reuse this session.")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
