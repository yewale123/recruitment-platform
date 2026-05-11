"""
Test LinkedIn scraping standalone — run this to diagnose issues.

Usage:
    python scripts/test_linkedin.py
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


async def main():
    from playwright.async_api import async_playwright
    import json
    from pathlib import Path

    SESSION_FILE = os.getenv("LINKEDIN_SESSION_FILE", "linkedin_session.json")

    print("\n=== LinkedIn Scraper Test ===\n")

    # Step 1: Check session file
    if not Path(SESSION_FILE).exists():
        print(f"[FAIL] Session file '{SESSION_FILE}' not found.")
        print("       Run: python scripts/linkedin_login.py")
        return
    print(f"[OK]  Session file found: {SESSION_FILE}")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=False,  # visible so you can see what's happening
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        # Load cookies
        cookies = json.loads(Path(SESSION_FILE).read_text())
        await context.add_cookies(cookies)
        print(f"[OK]  Loaded {len(cookies)} cookies")

        page = await context.new_page()

        # Step 2: Check login
        print("\n[...] Checking LinkedIn login...")
        await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30_000)
        await asyncio.sleep(3)
        url = page.url
        print(f"      Current URL: {url}")

        if "login" in url or "checkpoint" in url or "authwall" in url:
            print("[FAIL] Not logged in — session expired.")
            print("       Run: python scripts/linkedin_login.py")
            await browser.close()
            return
        print("[OK]  Logged in successfully")

        # Step 3: Try a simple search
        print("\n[...] Testing people search...")
        await page.goto(
            "https://www.linkedin.com/search/results/people/?keywords=Python+Developer",
            wait_until="domcontentloaded",
            timeout=30_000,
        )
        print("      Waiting 4s for JS rendering...")
        await asyncio.sleep(4)

        # Scroll to trigger lazy loading
        await page.evaluate("() => { window.scrollTo(0, 300); }")
        await asyncio.sleep(1)
        await page.evaluate("() => { window.scrollTo(0, document.body.scrollHeight / 2); }")
        await asyncio.sleep(1)
        await page.evaluate("() => { window.scrollTo(0, 0); }")
        await asyncio.sleep(1)

        print(f"      Search URL: {page.url}")

        # Take a screenshot
        await page.screenshot(path="scripts/debug_screenshot.png")
        print("[OK]  Screenshot saved: scripts/debug_screenshot.png")

        # Step 4: Try CSS selectors (old approach)
        print("\n[...] CSS selector results (old approach):")
        selectors_to_try = [
            "li[class*='result-container']",
            "div.entity-result",
            "li[class*='reusable-search']",
            ".search-results-container li",
            "[data-view-name='search-entity-result-universal-template']",
            "ul[class*='list'] > li",
        ]
        for sel in selectors_to_try:
            cards = await page.query_selector_all(sel)
            print(f"      '{sel}': {len(cards)} results")

        # Step 5: JS evaluation approach (new approach used in linkedin.py)
        print("\n[...] JS evaluation approach (new approach):")
        js_result = await page.evaluate("""
            () => {
                const getText = el => el ? el.innerText.trim() : null;

                // Try container selectors
                let containers = [];
                const selectors = [
                    'li[class*="result-container"]',
                    'div.entity-result',
                    'li[class*="reusable-search"]',
                    '[data-view-name*="search-entity"]',
                ];
                let usedSel = '';
                for (const sel of selectors) {
                    const found = Array.from(document.querySelectorAll(sel));
                    if (found.length > 0) { containers = found; usedSel = sel; break; }
                }

                // Fallback: find /in/ profile links
                const profileLinks = Array.from(
                    document.querySelectorAll('a[href*="/in/"]')
                ).filter(a => /\/in\/[\w\-]+/.test(a.getAttribute("href") || ""));

                const results = [];
                if (containers.length === 0) {
                    const seen = new Set();
                    for (const link of profileLinks) {
                        const href = link.getAttribute("href").split("?")[0];
                        if (seen.has(href)) continue;
                        seen.add(href);

                        let card = link;
                        for (let i = 0; i < 6; i++) {
                            if (!card.parentElement) break;
                            card = card.parentElement;
                            if (card.tagName === "LI" || card.tagName === "DIV") break;
                        }

                        const nameEl = card.querySelector('span[aria-hidden="true"]') ||
                                       card.querySelector('[class*="actor-name"]');
                        const headlineEl = card.querySelector('[class*="subline-level-1"]') ||
                                           card.querySelector('[class*="primary-subtitle"]');
                        const locationEl = card.querySelector('[class*="subline-level-2"]') ||
                                           card.querySelector('[class*="secondary-subtitle"]');

                        results.push({
                            href,
                            full_name: getText(nameEl),
                            headline: getText(headlineEl),
                            location: getText(locationEl),
                        });
                    }
                } else {
                    for (const card of containers) {
                        const linkEl = card.querySelector('a[href*="/in/"]');
                        if (!linkEl) continue;
                        const href = (linkEl.getAttribute("href") || "").split("?")[0];
                        results.push({ href, full_name: null, headline: null, location: null });
                    }
                }

                return {
                    container_selector: usedSel,
                    container_count: containers.length,
                    profile_link_count: profileLinks.length,
                    results: results.slice(0, 5),
                    page_title: document.title,
                    all_link_hrefs: Array.from(document.querySelectorAll('a[href*="/in/"]'))
                        .map(a => a.getAttribute("href"))
                        .filter(h => h && /\/in\/[\w\-]+/.test(h))
                        .slice(0, 10),
                };
            }
        """)

        print(f"      Page title: {js_result['page_title']}")
        print(f"      Container selector: '{js_result['container_selector']}' → {js_result['container_count']} containers")
        print(f"      /in/ profile links found: {js_result['profile_link_count']}")
        print(f"      Sample /in/ hrefs: {js_result['all_link_hrefs'][:5]}")
        print(f"      Extracted candidates: {len(js_result['results'])}")

        if js_result['results']:
            print("\n      First candidate:")
            r = js_result['results'][0]
            for k, v in r.items():
                print(f"        {k}: {v}")
            print("\n[OK]  JS approach works! linkedin.py should find candidates.")
        else:
            print("\n[WARN] JS approach also found 0 candidates.")
            print("       Possible causes:")
            print("       1. Session expired / LinkedIn showing captcha — check the browser window")
            print("       2. LinkedIn using shadow DOM or iframes — check page source")

            # Extra debug: dump page HTML snippet
            body_snippet = await page.evaluate("() => document.body.innerHTML.slice(0, 2000)")
            print("\n      Page body snippet (first 2000 chars):")
            print(body_snippet)

        print("\n[...] Browser stays open 15s for manual inspection...")
        await asyncio.sleep(15)
        await browser.close()

    print("\n=== Test Complete ===")


if __name__ == "__main__":
    asyncio.run(main())
