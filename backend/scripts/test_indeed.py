"""
Diagnostic script for the Indeed connector.

Run this to verify your Indeed session works and see what the scraper sees.

Usage:
    python scripts/test_indeed.py
"""

import asyncio
import json
from pathlib import Path
from dotenv import load_dotenv
import os
from urllib.parse import urlencode

load_dotenv()

SESSION_FILE = os.getenv("INDEED_SESSION_FILE", "indeed_session.json")
SCREENSHOT_FILE = "debug_indeed.png"
TEST_QUERY = "Python Developer"
TEST_LOCATION = "Bangalore"


async def main():
    from playwright.async_api import async_playwright

    print("=" * 55)
    print("  Indeed Connector Diagnostic")
    print("=" * 55)

    if not Path(SESSION_FILE).exists():
        print(f"\n[ERROR] No session file found at '{SESSION_FILE}'")
        print("  Run this first:  python scripts/indeed_login.py")
        return

    print(f"\n[OK] Session file found: {SESSION_FILE}")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=False,
            args=["--start-maximized"],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        cookies = json.loads(Path(SESSION_FILE).read_text())
        await context.add_cookies(cookies)

        page = await context.new_page()

        # Step 1: Check login
        print("\n[1] Checking login status...")
        await page.goto("https://resumes.indeed.com/search", wait_until="domcontentloaded", timeout=30_000)
        await asyncio.sleep(4)
        print(f"    Current URL: {page.url}")

        if any(x in page.url for x in ["login", "signin", "secure.indeed.com", "account/login"]):
            print("\n[FAIL] Not logged in — session expired.")
            print("  Run:  python scripts/indeed_login.py")
            await page.screenshot(path=SCREENSHOT_FILE)
            print(f"  Screenshot saved: {SCREENSHOT_FILE}")
            await browser.close()
            return
        print("    [OK] Logged in")

        # Step 2: Search
        params = {"q": TEST_QUERY, "l": TEST_LOCATION, "radius": "50"}
        search_url = f"https://resumes.indeed.com/search?{urlencode(params)}"
        print(f"\n[2] Navigating to search: {search_url}")
        await page.goto(search_url, wait_until="domcontentloaded", timeout=30_000)
        await asyncio.sleep(4)
        print(f"    Current URL: {page.url}")

        # Step 3: Screenshot
        await page.screenshot(path=SCREENSHOT_FILE, full_page=False)
        print(f"\n[3] Screenshot saved: {SCREENSHOT_FILE}")

        # Step 4: Try to find cards
        print("\n[4] Attempting to extract resume cards...")
        result = await page.evaluate("""
            () => {
                const selectors = [
                    '[data-testid="resume-card"]',
                    '.rezemp-ResumeCard',
                    '[class*="resumeCard"]',
                    '[class*="resume-card"]',
                    '.resume_list_item',
                    'article.result',
                    '[data-qa="resume-tile"]',
                    '[class*="ResumeCard"]',
                    '[class*="resumeTile"]',
                ];
                for (const sel of selectors) {
                    const els = document.querySelectorAll(sel);
                    if (els.length > 0) return { selector: sel, count: els.length };
                }

                const links = Array.from(document.querySelectorAll('a[href*="/resume/"]'));
                if (links.length > 0) return { selector: 'resume links', count: links.length };

                return { selector: null, count: 0, html_snippet: document.body.innerHTML.slice(0, 500) };
            }
        """)

        if result["count"] > 0:
            print(f"    [OK] Found {result['count']} cards using selector: {result['selector']}")
        else:
            print("    [WARN] No resume cards found.")
            print("    Page HTML snippet:")
            print("   ", result.get("html_snippet", "")[:300])

        print("\nDone. Check the browser window and screenshot for details.")
        input("\nPress Enter to close the browser...")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
