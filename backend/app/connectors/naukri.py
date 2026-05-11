"""
Naukri connector using Playwright.

First-time setup:
  Run:  python scripts/naukri_login.py
  This saves cookies to NAUKRI_SESSION_FILE (default: naukri_session.json).
  Requires a free Naukri recruiter account at www.naukri.com.
"""

import asyncio
import json
import random
from pathlib import Path
from urllib.parse import quote_plus

from app.config import get_settings
from app.connectors.base import BasePlatformConnector, RawCandidate, RecruitmentCriteria
from app.utils.text_utils import parse_experience_years

settings = get_settings()

_ENRICH_LIMIT = 8
_BASE = "https://www.naukri.com"
_LOGIN_CHECK_URL = f"{_BASE}/mnjuser/homepage"


class NaukriConnector(BasePlatformConnector):
    PLATFORM_NAME = "naukri"

    # ── Public API ────────────────────────────────────────────────────────────

    async def search(self, criteria: RecruitmentCriteria) -> list[RawCandidate]:
        from playwright.async_api import async_playwright

        queries = criteria.search_queries if criteria.search_queries else [self.build_search_query(criteria)]
        per_query = max(10, criteria.max_results // len(queries))

        all_cards: list[RawCandidate] = []
        seen_urls: set[str] = set()

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            context = await self._load_session(browser)
            await context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            page = await context.new_page()

            try:
                if not await self._is_logged_in(page):
                    print("[Naukri] Session expired or not found. Run scripts/naukri_login.py first.")
                    return []

                for i, query in enumerate(queries):
                    if len(all_cards) >= criteria.max_results:
                        break
                    remaining = criteria.max_results - len(all_cards)
                    print(f"[Naukri] Query {i+1}/{len(queries)}: '{query}'")
                    batch = await self._collect_cards(
                        page, query, criteria.location,
                        criteria.experience_min, criteria.experience_max,
                        min(per_query, remaining), seen_urls,
                    )
                    all_cards.extend(batch)
                    print(f"[Naukri] → {len(batch)} new candidates (total: {len(all_cards)})")
                    if i < len(queries) - 1:
                        await self._random_delay()

                print(f"[Naukri] Collected {len(all_cards)} unique candidates across all queries")
                results = await self._enrich_candidates(context, all_cards)

            except Exception as e:
                print(f"[Naukri] Search failed: {e}")
                results = all_cards
            finally:
                await browser.close()

        return results

    async def get_profile(self, profile_url: str) -> RawCandidate | None:
        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
            context = await self._load_session(browser)
            page = await context.new_page()
            try:
                return await self._parse_profile_page(page, profile_url)
            except Exception as e:
                print(f"[Naukri] Profile fetch failed for {profile_url}: {e}")
                return None
            finally:
                await browser.close()

    # ── Internals ─────────────────────────────────────────────────────────────

    async def _load_session(self, browser):
        session_file = Path(settings.NAUKRI_SESSION_FILE)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
            locale="en-IN",
        )
        if session_file.exists():
            cookies = json.loads(session_file.read_text())
            await context.add_cookies(cookies)
        else:
            print(f"[Naukri] No session file at '{session_file}'. Run scripts/naukri_login.py")
        return context

    async def _is_logged_in(self, page) -> bool:
        await page.goto(_LOGIN_CHECK_URL, wait_until="domcontentloaded", timeout=30_000)
        await asyncio.sleep(3)
        url = page.url
        return "login" not in url and "nlogin" not in url and "signup" not in url

    async def _collect_cards(
        self,
        page,
        query: str,
        location: str | None,
        exp_min: int | None,
        exp_max: int | None,
        max_count: int,
        seen_urls: set[str],
    ) -> list[RawCandidate]:
        # Strategy 1: Use Naukri's recruiter candidate search URL
        exp_from = exp_min or 0
        exp_to = exp_max or 30
        loc_str = quote_plus(location or "")
        kw_str = quote_plus(query)

        search_url = (
            f"{_BASE}/mnjuser/search/resume"
            f"?keyword={kw_str}"
            f"&location={loc_str}"
            f"&expMin={exp_from}"
            f"&expMax={exp_to}"
        )
        await page.goto(search_url, wait_until="domcontentloaded", timeout=30_000)
        await asyncio.sleep(4)

        # If redirected to login or got a 404, try form-based search on homepage
        if "login" in page.url or "nlogin" in page.url or page.url == _LOGIN_CHECK_URL:
            await page.goto(_LOGIN_CHECK_URL, wait_until="domcontentloaded", timeout=30_000)
            await asyncio.sleep(3)
            await self._fill_search_form(page, query, location or "", exp_from, exp_to)

        await self._scroll_page(page)
        await asyncio.sleep(2)

        candidates: list[RawCandidate] = []
        page_num = 0

        while len(candidates) < max_count:
            page_num += 1
            cards = await self._extract_cards_via_js(page)

            if not cards:
                if page_num == 1:
                    print("[Naukri] No result cards found — check session or selectors.")
                break

            for raw in cards:
                if len(candidates) >= max_count:
                    break
                url = raw.profile_url or ""
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    candidates.append(raw)

            has_next = await page.evaluate("""
                () => {
                    const next = document.querySelector(
                        'a[title="Next"], button[title="Next"], '
                        + '.pagination-next:not(.disabled), [class*="nextBtn"]:not([disabled]), '
                        + 'a[class*="next"]:not(.disabled)'
                    );
                    return next !== null;
                }
            """)
            if not has_next:
                break

            await page.evaluate("""
                () => {
                    const next = document.querySelector(
                        'a[title="Next"], button[title="Next"], '
                        + '.pagination-next:not(.disabled), [class*="nextBtn"]:not([disabled]), '
                        + 'a[class*="next"]:not(.disabled)'
                    );
                    if (next) next.click();
                }
            """)
            await asyncio.sleep(3)
            await self._scroll_page(page)
            await asyncio.sleep(2)

        return candidates

    async def _fill_search_form(self, page, query: str, location: str, exp_min: int, exp_max: int) -> bool:
        """Fill and submit the Naukri recruiter search form. Returns True on success."""
        try:
            kw_sel = (
                'input[placeholder*="eyword"], input[name*="keyword"], '
                'input[id*="keyword"], input[class*="keyword"], '
                'input[placeholder*="kill"]'
            )
            await page.wait_for_selector(kw_sel, timeout=8_000)
            kw_input = await page.query_selector(kw_sel)
            if not kw_input:
                return False

            await kw_input.triple_click()
            await kw_input.type(query, delay=50)

            if location:
                loc_sel = (
                    'input[placeholder*="ocation"], input[name*="location"], '
                    'input[id*="location"], input[class*="location"]'
                )
                loc_input = await page.query_selector(loc_sel)
                if loc_input:
                    await loc_input.triple_click()
                    await loc_input.type(location, delay=50)
                    await asyncio.sleep(1)
                    await page.keyboard.press("Escape")

            submit = await page.query_selector(
                'button[type="submit"], button[class*="search"], input[type="submit"]'
            )
            if submit:
                await submit.click()
            else:
                await kw_input.press("Enter")

            await asyncio.sleep(5)
            return True
        except Exception as e:
            print(f"[Naukri] Form search failed: {e}")
            return False

    async def _extract_cards_via_js(self, page) -> list[RawCandidate]:
        raw_list = await page.evaluate("""
            () => {
                const results = [];
                const getText = el => el ? el.innerText.trim() : null;

                let containers = [];
                const selectors = [
                    '.resume-tuple',
                    '.candidate-tuple',
                    '.srp-tuple',
                    '[class*="resumeTuple"]',
                    '[class*="candidateTuple"]',
                    '[class*="resume-card"]',
                    '[class*="resumeCard"]',
                    '[data-context="resume"]',
                    'article[class*="tuple"]',
                ];
                for (const sel of selectors) {
                    const found = Array.from(document.querySelectorAll(sel));
                    if (found.length > 0) { containers = found; break; }
                }

                // Fallback: find profile links
                if (containers.length === 0) {
                    const profileLinks = Array.from(document.querySelectorAll(
                        'a[href*="/profile/"], a[href*="mnjuser/profile"], a[href*="/resume/"]'
                    )).filter(a => {
                        const href = a.getAttribute("href") || "";
                        return href.includes("/profile/") || href.includes("/resume/");
                    });

                    const seen = new Set();
                    for (const link of profileLinks) {
                        const href = (link.getAttribute("href") || "").split("?")[0];
                        if (!href || seen.has(href)) continue;
                        seen.add(href);
                        let card = link;
                        for (let i = 0; i < 8; i++) {
                            if (!card.parentElement) break;
                            card = card.parentElement;
                            if (["LI", "ARTICLE"].includes(card.tagName)) break;
                            if (card.tagName === "DIV" && card.children.length > 2) break;
                        }
                        const nameEl = card.querySelector('[class*="name"], h2, h3, h4');
                        const headlineEl = card.querySelector('[class*="desig"], [class*="title"], [class*="headline"]');
                        const locationEl = card.querySelector('[class*="loc"], [class*="city"]');
                        const expEl = card.querySelector('[class*="exp"], [class*="experience"]');
                        results.push({
                            profile_url: href.startsWith("http") ? href : "https://www.naukri.com" + href,
                            full_name: getText(nameEl),
                            headline: getText(headlineEl),
                            location: getText(locationEl),
                            exp_text: getText(expEl),
                            skills: [],
                        });
                    }
                    return results;
                }

                for (const card of containers) {
                    const linkEl = card.querySelector(
                        'a[href*="/profile/"], a[href*="mnjuser/profile"], a[href*="/resume/"], a.title'
                    );
                    const href = linkEl ? (linkEl.getAttribute("href") || "").split("?")[0] : null;

                    const nameEl = card.querySelector(
                        '[class*="name"], [class*="candidateName"], h2, h3, a.title'
                    );
                    const headlineEl = card.querySelector(
                        '[class*="desig"], [class*="designation"], [class*="title"]:not(a)'
                    );
                    const locationEl = card.querySelector('[class*="loc"], [class*="city"]');
                    const expEl = card.querySelector('[class*="exp"], [class*="experience"]');
                    const skillEls = Array.from(card.querySelectorAll(
                        '[class*="skill"], [class*="tag"], [class*="keyword"], li[class*="key"]'
                    )).slice(0, 10).map(el => getText(el)).filter(Boolean);

                    if (!href && !getText(nameEl)) continue;

                    results.push({
                        profile_url: href
                            ? (href.startsWith("http") ? href : "https://www.naukri.com" + href)
                            : null,
                        full_name: getText(nameEl),
                        headline: getText(headlineEl),
                        location: getText(locationEl),
                        exp_text: getText(expEl),
                        skills: skillEls,
                    });
                }
                return results;
            }
        """)

        candidates: list[RawCandidate] = []
        seen_urls: set[str] = set()

        for item in (raw_list or []):
            profile_url = item.get("profile_url") or ""
            if profile_url in seen_urls:
                continue
            if profile_url:
                seen_urls.add(profile_url)

            platform_id = profile_url.rstrip("/").split("/")[-1] if profile_url else f"naukri_{len(candidates)}"

            exp_years: float | None = None
            if item.get("exp_text"):
                exp_years = parse_experience_years(item["exp_text"])

            candidates.append(RawCandidate(
                platform=self.PLATFORM_NAME,
                platform_id=platform_id,
                full_name=item.get("full_name"),
                headline=item.get("headline"),
                location=item.get("location"),
                experience_years=exp_years,
                skills=item.get("skills") or [],
                profile_url=profile_url or None,
                summary=None,
                raw_data={"source": "search_card"},
            ))

        return candidates

    async def _enrich_candidates(self, context, cards: list[RawCandidate]) -> list[RawCandidate]:
        enriched: list[RawCandidate] = []
        for i, c in enumerate(cards):
            if c.profile_url and i < _ENRICH_LIMIT:
                try:
                    profile_page = await context.new_page()
                    full = await self._parse_profile_page(profile_page, c.profile_url)
                    await profile_page.close()
                    if full:
                        enriched.append(full)
                        await self._random_delay()
                        continue
                except Exception as e:
                    print(f"[Naukri] Profile enrich failed: {e}")
            enriched.append(c)
        return enriched

    async def _parse_profile_page(self, page, url: str) -> RawCandidate | None:
        from playwright.async_api import TimeoutError as PWTimeout
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            await asyncio.sleep(3)
            await self._scroll_page(page)
        except PWTimeout:
            return None

        data = await page.evaluate("""
            () => {
                const getText = el => el ? el.innerText.trim() : null;

                const nameEl = document.querySelector(
                    '[class*="name-heading"], [class*="candidate-name"], h1.nameDesig, h1'
                );
                const headlineEl = document.querySelector(
                    '[class*="designation"], [class*="current-title"], .nameDesig + div'
                );
                const locationEl = document.querySelector(
                    '[class*="location"], [class*="city"], [class*="loc-label"]'
                );
                const summaryEl = document.querySelector(
                    '[class*="summary"], [class*="objective"], [class*="profile-summary"]'
                );
                const expEl = document.querySelector(
                    '[class*="totalExp"], [class*="total-exp"], [class*="experience-label"]'
                );
                const skillEls = Array.from(document.querySelectorAll(
                    '[class*="keySkill"] span, [class*="skill-item"], [class*="chip"] span'
                )).slice(0, 25);
                const skills = skillEls.map(el => getText(el)).filter(t => t && t.length > 1 && t.length < 50);

                return {
                    full_name: getText(nameEl),
                    headline: getText(headlineEl),
                    location: getText(locationEl),
                    summary: getText(summaryEl),
                    exp_text: getText(expEl),
                    skills,
                };
            }
        """)

        if not data:
            return None

        exp_years: float | None = None
        if data.get("exp_text"):
            exp_years = parse_experience_years(data["exp_text"])

        platform_id = url.rstrip("/").split("/")[-1]
        return RawCandidate(
            platform=self.PLATFORM_NAME,
            platform_id=platform_id,
            full_name=data.get("full_name"),
            headline=data.get("headline"),
            location=data.get("location"),
            experience_years=exp_years,
            skills=data.get("skills") or [],
            profile_url=url,
            summary=data.get("summary"),
            raw_data={"source": "profile_page", "url": url},
        )

    async def _scroll_page(self, page) -> None:
        await page.evaluate("() => { window.scrollTo(0, 400); }")
        await asyncio.sleep(1)
        await page.evaluate("() => { window.scrollTo(0, document.body.scrollHeight / 2); }")
        await asyncio.sleep(1)
        await page.evaluate("() => { window.scrollTo(0, 0); }")

    async def _random_delay(self) -> None:
        await asyncio.sleep(random.uniform(settings.SCRAPE_DELAY_MIN, settings.SCRAPE_DELAY_MAX))
