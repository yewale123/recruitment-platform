"""
One-time Indeed Resume Search login script.

Run this ONCE to log in to Indeed manually and save the session cookies.
The scraper reuses these cookies until the session expires.

Requirements:
  - A free Indeed employer account (signup at employers.indeed.com)
  - Indeed allows limited resume views on the free plan

Usage:
    python scripts/indeed_login.py
"""

import asyncio
import json
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

SESSION_FILE = os.getenv("INDEED_SESSION_FILE", "indeed_session.json")


async def main():
    from playwright.async_api import async_playwright

    print("=" * 55)
    print("  Indeed Resume Search Session Login")
    print("=" * 55)
    print("\nA browser window will open.")
    print("1. Log in to your Indeed EMPLOYER account")
    print("   (Sign up free at: https://employers.indeed.com/)")
    print("2. Wait until you see the Indeed employer dashboard")
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
        await page.goto("https://secure.indeed.com/account/login")

        input("Press Enter AFTER you are fully logged in and can see your Indeed dashboard...")

        # Navigate to resume search to capture those cookies too
        await page.goto("https://resumes.indeed.com/search")
        await asyncio.sleep(2)

        current_url = page.url
        if "login" in current_url or "signin" in current_url or "secure.indeed.com" in current_url:
            print("\n[WARNING] Looks like you may not be fully logged in.")
            print("  URL is:", current_url)
            confirm = input("  Save anyway? (y/n): ")
            if confirm.lower() != "y":
                await browser.close()
                return

        cookies = await context.cookies()
        Path(SESSION_FILE).write_text(json.dumps(cookies, indent=2))
        print(f"\n[OK] Session saved to '{SESSION_FILE}' ({len(cookies)} cookies)")
        print("You can now run the platform — the scraper will reuse this session.")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
