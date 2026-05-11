"""
One-time LinkedIn login script.

Run this ONCE to log in to LinkedIn manually and save the session cookies.
The scraper reuses these cookies until the session expires (~few weeks).

Usage:
    python scripts/linkedin_login.py
"""

import asyncio
import json
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

SESSION_FILE = os.getenv("LINKEDIN_SESSION_FILE", "linkedin_session.json")


async def main():
    from playwright.async_api import async_playwright

    print("=" * 50)
    print("  LinkedIn Session Login")
    print("=" * 50)
    print("\nA browser window will open.")
    print("1. Log in to LinkedIn manually")
    print("2. Wait until you see your LinkedIn feed")
    print("3. Come back here and press Enter\n")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=False,
            args=["--start-maximized"],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()
        await page.goto("https://www.linkedin.com/login")

        input("Press Enter AFTER you see your LinkedIn feed (fully logged in)...")

        # Verify login succeeded
        current_url = page.url
        if "linkedin.com/login" in current_url or "linkedin.com/checkpoint" in current_url:
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
