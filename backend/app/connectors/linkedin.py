"""
LinkedIn platform connector using Playwright.

First-time setup:
  Run:  python scripts/linkedin_login.py
  This saves cookies to LINKEDIN_SESSION_FILE (default: linkedin_session.json).
  Rerun the login script if the session expires.
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

# UI noise words to strip from skill lists
_SKILL_NOISE = {
    'follow', 'connect', 'message', 'more', 'save', 'view', 'see all',
    'show more', 'hide', 'edit', 'add', 'remove', 'endorse', 'pending',
    'withdraw', 'mutual connection', 'mutual connections',
}

# LinkedIn geoUrn IDs for common locations
_GEO_URN = {
    # India
    "bangalore": "105214831", "bengaluru": "105214831",
    "mumbai": "103371022", "bombay": "103371022",
    "delhi": "102442376", "new delhi": "102442376",
    "hyderabad": "106750394",
    "chennai": "106049236", "madras": "106049236",
    "pune": "106399029",
    "kolkata": "103598838", "calcutta": "103598838",
    "noida": "106164952",
    "gurgaon": "106478283", "gurugram": "106478283",
    "ahmedabad": "106564383",
    "india": "102713980",
    # USA
    "san francisco": "90000084",
    "new york": "102571732",
    "seattle": "101209277",
    "austin": "103573404",
    "boston": "101957769",
    "chicago": "103112276",
    "los angeles": "102448103",
    # Others
    "london": "90009496",
    "toronto": "101174742",
    "sydney": "104769905",
    "melbourne": "103105990",
    "berlin": "106967730",
    "singapore": "102454443",
    "dubai": "106204383",
}


def _geo_param(location: str) -> str:
    """Return URL-encoded geoUrn param string for known locations, else ''."""
    geo_id = _GEO_URN.get(location.strip().lower())
    if geo_id:
        return quote_plus(f'["urn:li:geo:{geo_id}"]')
    return ""


class LinkedInConnector(BasePlatformConnector):
    PLATFORM_NAME = "linkedin"

    # ── Public API ────────────────────────────────────────────────────────────

    async def search(self, criteria: RecruitmentCriteria) -> list[RawCandidate]:
        from playwright.async_api import async_playwright

        queries = criteria.search_queries if criteria.search_queries else [self.build_search_query(criteria)]
        per_query = max(10, criteria.max_results // len(queries))
        enrich_limit = settings.SCRAPE_ENRICH_LIMIT

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
                    print("[LinkedIn] Session expired. Run scripts/linkedin_login.py first.")
                    return []

                for i, query in enumerate(queries):
                    if len(all_cards) >= criteria.max_results:
                        break
                    remaining = criteria.max_results - len(all_cards)
                    print(f"[LinkedIn] Query {i+1}/{len(queries)}: '{query}'")
                    batch = await self._collect_cards(
                        page, query, min(per_query, remaining), seen_urls, criteria.location
                    )
                    all_cards.extend(batch)
                    print(f"[LinkedIn] → {len(batch)} new candidates (total: {len(all_cards)})")
                    if i < len(queries) - 1:
                        await self._random_delay()

                print(f"[LinkedIn] Enriching top {min(enrich_limit, len(all_cards))} profiles...")
                results = await self._enrich_candidates(context, all_cards, enrich_limit)

            except Exception as e:
                print(f"[LinkedIn] Search failed: {e}")
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
            await context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            page = await context.new_page()
            try:
                return await self._parse_profile_page(page, profile_url)
            except Exception as e:
                print(f"[LinkedIn] Profile fetch failed for {profile_url}: {e}")
                return None
            finally:
                await browser.close()

    # ── Internals ─────────────────────────────────────────────────────────────

    async def _load_session(self, browser):
        session_file = Path(settings.LINKEDIN_SESSION_FILE)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="en-US",
        )
        if session_file.exists():
            cookies = json.loads(session_file.read_text())
            await context.add_cookies(cookies)
        else:
            print(f"[LinkedIn] No session file at '{session_file}'. Run scripts/linkedin_login.py")
        return context

    async def _is_logged_in(self, page) -> bool:
        await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=20_000)
        await asyncio.sleep(2)
        url = page.url
        return "login" not in url and "checkpoint" not in url and "authwall" not in url

    async def _collect_cards(
        self,
        page,
        query: str,
        max_count: int,
        seen_urls: set[str],
        location: str | None = None,
    ) -> list[RawCandidate]:
        skip_loc = not location or location.lower() in ("remote", "any", "anywhere", "")
        if not skip_loc:
            geo = _geo_param(location)
            if geo:
                # Known city → use LinkedIn's geoUrn filter (most precise)
                encoded = quote_plus(query)
                search_url = (
                    f"https://www.linkedin.com/search/results/people/"
                    f"?keywords={encoded}&geoUrn={geo}&origin=GLOBAL_SEARCH_HEADER"
                )
                print(f"[LinkedIn] Location filter: {location} (geoUrn)")
            else:
                # Unknown city → append to keywords as fallback
                encoded = quote_plus(f"{query} {location}")
                search_url = (
                    f"https://www.linkedin.com/search/results/people/"
                    f"?keywords={encoded}&origin=GLOBAL_SEARCH_HEADER"
                )
                print(f"[LinkedIn] Location filter: {location} (keyword fallback)")
        else:
            encoded = quote_plus(query)
            search_url = (
                f"https://www.linkedin.com/search/results/people/"
                f"?keywords={encoded}&origin=GLOBAL_SEARCH_HEADER"
            )
        await page.goto(search_url, wait_until="domcontentloaded", timeout=30_000)
        await asyncio.sleep(2)
        await self._scroll_page(page)

        candidates: list[RawCandidate] = []

        while len(candidates) < max_count:
            page_cards = await self._extract_cards_via_js(page)

            if not page_cards:
                print("[LinkedIn] No result cards found — stopping.")
                break

            for raw in page_cards:
                if len(candidates) >= max_count:
                    break
                url = raw.profile_url or ""
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    candidates.append(raw)

            has_next = await page.evaluate("""
                () => {
                    const btn = document.querySelector("button[aria-label='Next']");
                    return btn !== null && !btn.disabled;
                }
            """)
            if not has_next:
                break

            await page.evaluate("""
                () => {
                    const btn = document.querySelector("button[aria-label='Next']");
                    if (btn) btn.click();
                }
            """)
            await asyncio.sleep(2)
            await self._scroll_page(page)

        return candidates

    async def _enrich_candidates(
        self, context, cards: list[RawCandidate], enrich_limit: int
    ) -> list[RawCandidate]:
        """Visit profile pages for top N candidates. Merges with card data for any null fields."""
        enriched: list[RawCandidate] = []
        for i, c in enumerate(cards):
            if c.profile_url and i < enrich_limit:
                try:
                    profile_page = await context.new_page()
                    full = await self._parse_profile_page(profile_page, c.profile_url)
                    await profile_page.close()
                    if full:
                        # Profile page wins; card fills any nulls
                        merged = RawCandidate(
                            platform=full.platform,
                            platform_id=full.platform_id,
                            full_name=full.full_name or c.full_name,
                            headline=full.headline or c.headline,
                            location=full.location or c.location,
                            experience_years=full.experience_years,
                            skills=full.skills if full.skills else c.skills,
                            profile_url=full.profile_url or c.profile_url,
                            summary=full.summary,
                            raw_data=full.raw_data,
                        )
                        enriched.append(merged)
                        await self._random_delay()
                        continue
                except Exception as e:
                    print(f"[LinkedIn] Profile enrich failed: {e}")
            enriched.append(c)
        return enriched

    async def _scroll_page(self, page) -> None:
        await page.evaluate("() => window.scrollTo(0, document.body.scrollHeight / 2)")
        await asyncio.sleep(0.8)
        await page.evaluate("() => window.scrollTo(0, 0)")
        await asyncio.sleep(0.5)

    async def _extract_cards_via_js(self, page) -> list[RawCandidate]:
        raw_list = await page.evaluate("""
            () => {
                const results = [];
                const getText = el => el ? el.innerText.trim() : null;

                const getNameFromLink = (linkEl) => {
                    const ariaSpan = linkEl.querySelector('span[aria-hidden="true"]');
                    if (ariaSpan && ariaSpan.innerText.trim()) return ariaSpan.innerText.trim();
                    const clone = linkEl.cloneNode(true);
                    clone.querySelectorAll('.visually-hidden, [aria-hidden="false"]').forEach(el => el.remove());
                    return clone.innerText.trim() || null;
                };

                let containers = [];
                const containerSels = [
                    'li[class*="result-container"]',
                    'div.entity-result',
                    'li[class*="reusable-search"]',
                    '[data-view-name*="search-entity"]',
                    'li.search-result',
                ];
                for (const sel of containerSels) {
                    const found = Array.from(document.querySelectorAll(sel));
                    if (found.length > 0) { containers = found; break; }
                }

                if (containers.length === 0) {
                    const links = Array.from(document.querySelectorAll('a[href*="/in/"]'))
                        .filter(a => /\/in\/[\w\-]+/.test(a.getAttribute("href") || ""));
                    const seen = new Set();
                    for (const link of links) {
                        const href = link.getAttribute("href").split("?")[0];
                        if (seen.has(href)) continue;
                        seen.add(href);
                        let card = link;
                        for (let i = 0; i < 8; i++) {
                            if (!card.parentElement) break;
                            card = card.parentElement;
                            if (card.tagName === "LI") break;
                        }
                        const headlineEl = card.querySelector(
                            '[class*="subline-level-1"],[class*="primary-subtitle"],.entity-result__primary-subtitle'
                        );
                        const locationEl = card.querySelector(
                            '[class*="subline-level-2"],[class*="secondary-subtitle"],.entity-result__secondary-subtitle'
                        );
                        results.push({
                            profile_url: href.startsWith("http") ? href : "https://www.linkedin.com" + href,
                            full_name: getNameFromLink(link),
                            headline: getText(headlineEl),
                            location: getText(locationEl),
                        });
                    }
                    return results;
                }

                for (const card of containers) {
                    const linkEl = card.querySelector('a[href*="/in/"]');
                    if (!linkEl) continue;
                    const href = (linkEl.getAttribute("href") || "").split("?")[0];
                    if (!href) continue;

                    const headlineEl = card.querySelector(
                        '[class*="subline-level-1"],[class*="primary-subtitle"],.entity-result__primary-subtitle'
                    );
                    const locationEl = card.querySelector(
                        '[class*="subline-level-2"],[class*="secondary-subtitle"],.entity-result__secondary-subtitle'
                    );
                    results.push({
                        profile_url: href.startsWith("http") ? href : "https://www.linkedin.com" + href,
                        full_name: getNameFromLink(linkEl),
                        headline: getText(headlineEl),
                        location: getText(locationEl),
                    });
                }
                return results;
            }
        """)

        candidates: list[RawCandidate] = []
        seen_urls: set[str] = set()

        for item in (raw_list or []):
            profile_url = item.get("profile_url", "")
            if not profile_url or profile_url in seen_urls or "/in/" not in profile_url:
                continue
            seen_urls.add(profile_url)
            platform_id = profile_url.rstrip("/").split("/")[-1] or profile_url
            candidates.append(RawCandidate(
                platform=self.PLATFORM_NAME,
                platform_id=platform_id,
                full_name=item.get("full_name"),
                headline=item.get("headline"),
                location=item.get("location"),
                experience_years=None,
                skills=[],
                profile_url=profile_url,
                summary=None,
                raw_data={"source": "search_card"},
            ))

        return candidates

    async def _parse_profile_page(self, page, url: str) -> RawCandidate | None:
        from playwright.async_api import TimeoutError as PWTimeout

        base_url = url.split("?")[0].rstrip("/")

        try:
            await page.goto(base_url, wait_until="domcontentloaded", timeout=30_000)
            await asyncio.sleep(2)
            await self._scroll_page(page)
        except PWTimeout:
            return None

        data = await page.evaluate("""
            () => {
                const getText = el => el ? el.innerText.trim() : null;
                const firstMatch = (...sels) => {
                    for (const s of sels) {
                        const el = document.querySelector(s);
                        if (el && el.innerText.trim()) return el;
                    }
                    return null;
                };

                // Name
                const nameEl = firstMatch(
                    'h1.text-heading-xlarge', '.pv-top-card--list h1',
                    '.ph5 h1', 'h1[class*="heading"]', 'h1'
                );

                // Headline
                const headlineEl = firstMatch(
                    '.text-body-medium.break-words',
                    '.pv-text-details__left-panel .text-body-medium',
                    '.ph5 .text-body-medium'
                );

                // Location
                const locationEl = firstMatch(
                    'span.text-body-small.inline.t-black--light.break-words',
                    '.pv-top-card--list .t-black--light.t-normal',
                    '.pv-text-details__left-panel .pb2 span',
                    '.ph5 span[class*="t-black--light"]'
                );

                // Summary
                let summary = null;
                const aboutSection = document.querySelector('#about');
                if (aboutSection) {
                    const parent = aboutSection.closest('section') || aboutSection.parentElement;
                    const span = parent && parent.querySelector('span[aria-hidden="true"]');
                    if (span) summary = getText(span);
                }

                // Skills — visible on main profile page (top 5 shown without navigating away)
                const skills = [];
                const skillsSec = document.querySelector('#skills');
                if (skillsSec) {
                    const parent = skillsSec.closest('section') || skillsSec.parentElement;
                    const skillEls = Array.from((parent || document).querySelectorAll(
                        '.pvs-list__item--line-separated .t-bold span[aria-hidden="true"], '
                        + '[class*="pvs-entity"] .t-bold span[aria-hidden="true"]'
                    )).slice(0, 15);
                    for (const el of skillEls) {
                        const txt = getText(el);
                        if (txt && txt.length > 1 && txt.length < 60 && !skills.includes(txt)) {
                            skills.push(txt);
                        }
                    }
                }

                // Experience date ranges for year calculation
                let exp_texts = [];
                const expSec = document.querySelector('#experience');
                if (expSec) {
                    const parent = expSec.closest('section') || expSec.parentElement;
                    exp_texts = Array.from((parent || document).querySelectorAll(
                        'span.t-14.t-normal.t-black--light, '
                        + '[class*="pvs-entity__caption"] span[aria-hidden="true"]'
                    )).slice(0, 20).map(el => getText(el)).filter(Boolean);
                }
                if (!exp_texts.length) {
                    exp_texts = Array.from(document.querySelectorAll(
                        'span.t-14.t-normal.t-black--light'
                    )).slice(0, 30).map(el => getText(el)).filter(Boolean);
                }

                return {
                    full_name: getText(nameEl),
                    headline: getText(headlineEl),
                    location: getText(locationEl),
                    summary,
                    skills,
                    exp_texts,
                };
            }
        """)

        if not data:
            return None

        # Filter noise from skills
        raw_skills = data.get("skills") or []
        clean_skills = [
            s for s in raw_skills
            if s and s.lower() not in _SKILL_NOISE and not s.isdigit()
        ]

        exp_years: float | None = None
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
            skills=clean_skills,
            profile_url=base_url,
            summary=data.get("summary"),
            raw_data={"source": "profile_page", "url": base_url},
        )

    async def _random_delay(self) -> None:
        await asyncio.sleep(random.uniform(settings.SCRAPE_DELAY_MIN, settings.SCRAPE_DELAY_MAX))
