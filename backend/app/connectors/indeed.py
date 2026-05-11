"""
Indeed Resume Search connector using Playwright.

First-time setup:
  Run:  python scripts/indeed_login.py
  This saves cookies to INDEED_SESSION_FILE (default: indeed_session.json).
  Requires a free Indeed employer account at employers.indeed.com.

Note:
  Indeed Resume Search (resumes.indeed.com) shows job-seeker profiles.
  Free accounts can view a limited number of resumes per month.
"""

import asyncio
import json
import random
from pathlib import Path
from urllib.parse import quote_plus, urlencode

from app.config import get_settings
from app.connectors.base import BasePlatformConnector, RawCandidate, RecruitmentCriteria
from app.utils.text_utils import parse_experience_years

settings = get_settings()

_ENRICH_LIMIT = 8
_SEARCH_BASE = "https://resumes.indeed.com/search"
_LOGIN_CHECK_URL = "https://resumes.indeed.com/search"


class IndeedConnector(BasePlatformConnector):
    PLATFORM_NAME = "indeed"

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
                    print("[Indeed] Session expired or not found. Run scripts/indeed_login.py first.")
                    return []

                for i, query in enumerate(queries):
                    if len(all_cards) >= criteria.max_results:
                        break
                    remaining = criteria.max_results - len(all_cards)
                    print(f"[Indeed] Query {i+1}/{len(queries)}: '{query}'")
                    batch = await self._collect_cards(
                        page, query, criteria.location,
                        min(per_query, remaining), seen_urls,
                    )
                    all_cards.extend(batch)
                    print(f"[Indeed] → {len(batch)} new candidates (total: {len(all_cards)})")
                    if i < len(queries) - 1:
                        await self._random_delay()

                print(f"[Indeed] Collected {len(all_cards)} unique candidates across all queries")
                results = await self._enrich_candidates(context, all_cards)

            except Exception as e:
                print(f"[Indeed] Search failed: {e}")
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
                print(f"[Indeed] Profile fetch failed for {profile_url}: {e}")
                return None
            finally:
                await browser.close()

    # ── Internals ─────────────────────────────────────────────────────────────

    async def _load_session(self, browser):
        session_file = Path(settings.INDEED_SESSION_FILE)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
            locale="en-US",
        )
        if session_file.exists():
            cookies = json.loads(session_file.read_text())
            await context.add_cookies(cookies)
        else:
            print(f"[Indeed] No session file at '{session_file}'. Run scripts/indeed_login.py")
        return context

    async def _is_logged_in(self, page) -> bool:
        await page.goto(_LOGIN_CHECK_URL, wait_until="domcontentloaded", timeout=30_000)
        await asyncio.sleep(3)
        url = page.url
        return (
            "login" not in url
            and "signin" not in url
            and "account/login" not in url
            and "secure.indeed.com" not in url
        )

    async def _collect_cards(
        self,
        page,
        query: str,
        location: str | None,
        max_count: int,
        seen_urls: set[str],
    ) -> list[RawCandidate]:
        params = {"q": query, "radius": "50"}
        if location:
            params["l"] = location
        search_url = f"{_SEARCH_BASE}?{urlencode(params)}"

        await page.goto(search_url, wait_until="domcontentloaded", timeout=30_000)
        await asyncio.sleep(3)
        await self._scroll_page(page)
        await asyncio.sleep(2)

        candidates: list[RawCandidate] = []
        page_num = 0

        while len(candidates) < max_count:
            page_num += 1
            cards = await self._extract_cards_via_js(page)

            if not cards:
                if page_num == 1:
                    print("[Indeed] No resume cards found — check session or selectors.")
                break

            for raw in cards:
                if len(candidates) >= max_count:
                    break
                url = raw.profile_url or ""
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    candidates.append(raw)

            # Check for next page button
            has_next = await page.evaluate("""
                () => {
                    const next = document.querySelector(
                        'a[aria-label="Next"], a[data-testid="pagination-page-next"], '
                        + '.pagination-list .next a, [class*="nextPage"]:not(.disabled)'
                    );
                    return next !== null;
                }
            """)
            if not has_next:
                break

            await page.evaluate("""
                () => {
                    const next = document.querySelector(
                        'a[aria-label="Next"], a[data-testid="pagination-page-next"], '
                        + '.pagination-list .next a, [class*="nextPage"]:not(.disabled)'
                    );
                    if (next) next.click();
                }
            """)
            await asyncio.sleep(3)
            await self._scroll_page(page)
            await asyncio.sleep(2)

        return candidates

    async def _extract_cards_via_js(self, page) -> list[RawCandidate]:
        raw_list = await page.evaluate("""
            () => {
                const results = [];
                const getText = el => el ? el.innerText.trim() : null;

                // Indeed resume card selectors (try multiple)
                let containers = [];
                const selectors = [
                    '[data-testid="resume-card"]',
                    '.rezemp-ResumeCard',
                    '[class*="resumeCard"]',
                    '[class*="resume-card"]',
                    '.resume_list_item',
                    'article.result',
                    '[data-qa="resume-tile"]',
                ];
                for (const sel of selectors) {
                    const found = Array.from(document.querySelectorAll(sel));
                    if (found.length > 0) { containers = found; break; }
                }

                // Fallback: find resume links directly
                if (containers.length === 0) {
                    const resumeLinks = Array.from(
                        document.querySelectorAll('a[href*="/resume/"]')
                    ).filter(a => /\/resume\/[\w\-]+/.test(a.getAttribute("href") || ""));

                    const seen = new Set();
                    for (const link of resumeLinks) {
                        const href = (link.getAttribute("href") || "").split("?")[0];
                        if (!href || seen.has(href)) continue;
                        seen.add(href);
                        let card = link;
                        for (let i = 0; i < 6; i++) {
                            if (!card.parentElement) break;
                            card = card.parentElement;
                            if (["LI", "DIV", "ARTICLE"].includes(card.tagName)) break;
                        }
                        const nameEl = card.querySelector('h2, h3, [class*="name"], [class*="title"]');
                        const headlineEl = card.querySelector('[class*="headline"], [class*="jobTitle"], [class*="position"]');
                        const locationEl = card.querySelector('[class*="location"], [class*="city"]');
                        const expEl = card.querySelector('[class*="experience"], [class*="workExperience"]');
                        results.push({
                            profile_url: href.startsWith("http") ? href : "https://resumes.indeed.com" + href,
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
                    const linkEl = card.querySelector('a[href*="/resume/"]');
                    const href = linkEl ? (linkEl.getAttribute("href") || "").split("?")[0] : null;

                    const nameEl = card.querySelector(
                        'h2, h3, [data-testid="applicant-name"], [class*="resume-title"], [class*="candidateName"]'
                    );
                    const headlineEl = card.querySelector(
                        '[data-testid="applicant-headline"], [class*="headline"], [class*="jobTitle"], [class*="current-title"]'
                    );
                    const locationEl = card.querySelector(
                        '[data-testid="applicant-location"], [class*="location"], [class*="city"]'
                    );
                    const expEl = card.querySelector(
                        '[data-testid="applicant-experience"], [class*="experience"], [class*="workHistory"]'
                    );
                    const skillEls = Array.from(card.querySelectorAll(
                        '[data-testid="skill-tag"], [class*="skill"], [class*="tag"]'
                    )).slice(0, 10).map(el => getText(el)).filter(Boolean);

                    if (!href && !getText(nameEl)) continue;

                    results.push({
                        profile_url: href
                            ? (href.startsWith("http") ? href : "https://resumes.indeed.com" + href)
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

            platform_id = profile_url.rstrip("/").split("/")[-1] if profile_url else f"indeed_{len(candidates)}"

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
                    print(f"[Indeed] Profile enrich failed: {e}")
            enriched.append(c)
        return enriched

    async def _parse_profile_page(self, page, url: str) -> RawCandidate | None:
        from playwright.async_api import TimeoutError as PWTimeout
        base_url = url.split("?")[0].rstrip("/")
        try:
            await page.goto(base_url, wait_until="domcontentloaded", timeout=30_000)
            await asyncio.sleep(3)
            await self._scroll_page(page)
            await asyncio.sleep(1)
        except PWTimeout:
            return None

        data = await page.evaluate("""
            () => {
                const getText = el => el ? el.innerText.trim() : null;

                const nameEl = document.querySelector(
                    'h1, [data-testid="resume-name"], [class*="applicant-name"], [class*="resumeName"]'
                );
                const headlineEl = document.querySelector(
                    '[data-testid="resume-headline"], [class*="headline"], [class*="jobTitle"], h2'
                );
                const locationEl = document.querySelector(
                    '[data-testid="resume-location"], [class*="location"], [class*="city"]'
                );
                const summaryEl = document.querySelector(
                    '[data-testid="resume-summary"], [class*="summary"], [class*="objective"]'
                );
                const expEl = document.querySelector(
                    '[data-testid="total-experience"], [class*="totalExp"], [class*="yearsExp"]'
                );

                const skillEls = Array.from(document.querySelectorAll(
                    '[data-testid="skill-tag"], [class*="skill-name"], [class*="skillItem"] span, .skills li'
                )).slice(0, 25);
                const skills = skillEls.map(el => getText(el)).filter(t => t && t.length > 1 && t.length < 60);

                // Fallback: parse experience from work history section
                const expTexts = Array.from(document.querySelectorAll(
                    '[class*="workExperience"] span, [class*="duration"], [class*="dateRange"]'
                )).slice(0, 10).map(el => getText(el)).filter(Boolean);

                return {
                    full_name: getText(nameEl),
                    headline: getText(headlineEl),
                    location: getText(locationEl),
                    summary: getText(summaryEl),
                    exp_text: getText(expEl),
                    exp_texts: expTexts,
                    skills,
                };
            }
        """)

        if not data:
            return None

        exp_years: float | None = None
        if data.get("exp_text"):
            exp_years = parse_experience_years(data["exp_text"])
        if not exp_years:
            for text in (data.get("exp_texts") or []):
                parsed = parse_experience_years(text)
                if parsed:
                    exp_years = parsed
                    break

        platform_id = base_url.rstrip("/").split("/")[-1]

        return RawCandidate(
            platform=self.PLATFORM_NAME,
            platform_id=platform_id,
            full_name=data.get("full_name"),
            headline=data.get("headline"),
            location=data.get("location"),
            experience_years=exp_years,
            skills=data.get("skills") or [],
            profile_url=base_url,
            summary=data.get("summary"),
            raw_data={"source": "profile_page", "url": base_url},
        )

    async def _scroll_page(self, page) -> None:
        await page.evaluate("() => { window.scrollTo(0, 400); }")
        await asyncio.sleep(1)
        await page.evaluate("() => { window.scrollTo(0, document.body.scrollHeight / 2); }")
        await asyncio.sleep(1)
        await page.evaluate("() => { window.scrollTo(0, 0); }")
        await asyncio.sleep(0.5)

    async def _random_delay(self) -> None:
        await asyncio.sleep(random.uniform(settings.SCRAPE_DELAY_MIN, settings.SCRAPE_DELAY_MAX))
