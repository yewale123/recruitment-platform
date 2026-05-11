"""
Diagnostic script for the Naukri connector.

Run this to verify your Naukri session works and see what the scraper sees.
A browser window opens so you can inspect the page yourself.

Usage:
    python scripts/test_naukri.py
"""

import asyncio
import json
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

SESSION_FILE = os.getenv("NAUKRI_SESSION_FILE", "naukri_session.json")
SCREENSHOT_FILE = "debug_naukri.png"
TEST_QUERY = "Python Developer"
TEST_LOCATION = "Bangalore"


async def main():
    from playwright.async_api import async_playwright

    print("=" * 55)
    print("  Naukri Connector Diagnostic")
    print("=" * 55)

    if not Path(SESSION_FILE).exists():
        print(f"\n[ERROR] No session file found at '{SESSION_FILE}'")
        print("  Run this first:  python scripts/naukri_login.py")
        return

    print(f"\n[OK] Session file found: {SESSION_FILE}")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=False,   # visible so you can see what's happening
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
        await page.goto("https://www.naukri.com/mnjuser/homepage", wait_until="domcontentloaded", timeout=30_000)
        await asyncio.sleep(4)
        print(f"    Current URL: {page.url}")

        if "login" in page.url or "nlogin" in page.url:
            print("\n[FAIL] Not logged in — session expired.")
            print("  Run:  python scripts/naukri_login.py")
            await page.screenshot(path=SCREENSHOT_FILE)
            print(f"  Screenshot saved: {SCREENSHOT_FILE}")
            await browser.close()
            return
        print("    [OK] Logged in")

        # Step 2: Try form-based search
        print(f"\n[2] Searching for '{TEST_QUERY}' in '{TEST_LOCATION}'...")
        try:
            # Wait for the search input to appear
            await page.wait_for_selector(
                'input[placeholder*="keyword"], input[placeholder*="Keyword"], '
                'input[name*="keyword"], input[id*="keyword"], input[class*="keyword"]',
                timeout=10_000,
            )
            kw_input = await page.query_selector(
                'input[placeholder*="keyword"], input[placeholder*="Keyword"], '
                'input[name*="keyword"], input[id*="keyword"], input[class*="keyword"]'
            )
            if kw_input:
                await kw_input.triple_click()
                await kw_input.type(TEST_QUERY)
                print(f"    Typed query into keywords field")

            loc_input = await page.query_selector(
                'input[placeholder*="location"], input[placeholder*="Location"], '
                'input[name*="location"], input[id*="location"], input[class*="location"]'
            )
            if loc_input:
                await loc_input.triple_click()
                await loc_input.type(TEST_LOCATION)
                print(f"    Typed location")

            # Submit
            submit_btn = await page.query_selector(
                'button[type="submit"], button[class*="search"], input[type="submit"]'
            )
            if submit_btn:
                await submit_btn.click()
                print("    Clicked search button")
            else:
                await page.keyboard.press("Enter")
                print("    Pressed Enter to search")

            await asyncio.sleep(5)
        except Exception as e:
            print(f"    Form-based search failed: {e}")
            print("    Trying URL fragment approach...")
            from urllib.parse import quote_plus
            url = (
                f"https://www.naukri.com/mnjuser/homepage"
                f"#resumesearch/keywords={quote_plus(TEST_QUERY)}"
                f"/location={quote_plus(TEST_LOCATION)}/"
            )
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            await asyncio.sleep(5)

        print(f"    Current URL: {page.url}")

        # Step 3: Screenshot
        await page.screenshot(path=SCREENSHOT_FILE, full_page=False)
        print(f"\n[3] Screenshot saved: {SCREENSHOT_FILE}")

        # Step 4: Try to find cards
        print("\n[4] Attempting to extract candidate cards...")
        result = await page.evaluate("""
            () => {
                const selectors = [
                    '.resume-card', '.candidate-tuple', '[class*="resumeCard"]',
                    '[class*="candidate-card"]', '[class*="candidateTuple"]',
                    '.srp-tuple', '[data-context="resume"]',
                ];
                for (const sel of selectors) {
                    const els = document.querySelectorAll(sel);
                    if (els.length > 0) return { selector: sel, count: els.length };
                }

                // Count all links that look like profiles
                const links = Array.from(document.querySelectorAll(
                    'a[href*="resumedetail"], a[href*="mnjuser/profile"]'
                ));
                if (links.length > 0) return { selector: 'profile links', count: links.length };

                return { selector: null, count: 0, html_snippet: document.body.innerHTML.slice(0, 500) };
            }
        """)

        if result["count"] > 0:
            print(f"    [OK] Found {result['count']} cards using selector: {result['selector']}")
        else:
            print("    [WARN] No candidate cards found.")
            print("    Page HTML snippet:")
            print("   ", result.get("html_snippet", "")[:300])

        print("\nDone. Check the browser window and screenshot for details.")
        input("\nPress Enter to close the browser...")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
