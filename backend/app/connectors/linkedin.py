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
                channel="chrome",
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            context = await self._load_session(browser)
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
                channel="chrome",
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"],
            )
            context = await self._load_session(browser)
            page = await context.new_page()
            try:
                return await self._parse_profile_page(page, profile_url)
            except Exception as e:
                print(f"[LinkedIn] Profile fetch failed for {profile_url}: {e}")
                return None
            finally:
                await browser.close()

    async def enrich_single_profile(self, profile_url: str) -> RawCandidate | None:
        """
        Open one LinkedIn profile in a fresh browser and extract full data
        (name, headline, location, skills, experience, email from Contact Info).
        Used to backfill top-ranked candidates that were not enriched during search.
        """
        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                channel="chrome",
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"],
            )
            context = await self._load_session(browser)
            page = await context.new_page()
            try:
                return await self._parse_profile_page(page, profile_url)
            except Exception as e:
                print(f"[LinkedIn] enrich_single_profile failed for {profile_url}: {e}")
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
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){}, app: {} };
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            const _origQuery = window.navigator.permissions.query.bind(navigator.permissions);
            window.navigator.permissions.query = (p) =>
                p.name === 'notifications'
                    ? Promise.resolve({ state: Notification.permission })
                    : _origQuery(p);
        """)
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

        # Embed location in keywords — geoUrn is too restrictive for accounts
        # with few connections (returns 0 results outside your network).
        if not skip_loc:
            encoded = quote_plus(f"{query} {location}")
            print(f"[LinkedIn] Location filter: {location} (keyword)")
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
        tried_no_loc = skip_loc  # track whether we already dropped the location

        while len(candidates) < max_count:
            page_cards = await self._extract_cards_via_js(page)

            if not page_cards:
                if not tried_no_loc:
                    # Retry without location — new accounts see limited results
                    print(f"[LinkedIn] 0 results with location '{location}' — retrying without location")
                    tried_no_loc = True
                    encoded_no_loc = quote_plus(query)
                    search_url_no_loc = (
                        f"https://www.linkedin.com/search/results/people/"
                        f"?keywords={encoded_no_loc}&origin=GLOBAL_SEARCH_HEADER"
                    )
                    await page.goto(search_url_no_loc, wait_until="domcontentloaded", timeout=30_000)
                    await asyncio.sleep(2)
                    await self._scroll_page(page)
                    continue  # re-check page_cards after reload

                # Save screenshot to debug what LinkedIn is showing
                try:
                    screenshot_path = "linkedin_debug_headless.png"
                    await page.screenshot(path=screenshot_path, full_page=True)
                    print(f"[LinkedIn] No result cards found — screenshot saved to {screenshot_path}")
                except Exception:
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
        """
        Visit profile pages for top N candidates — 3 pages concurrently.
        3 concurrent visits keeps speed up without triggering LinkedIn rate limits.
        Cards beyond enrich_limit are returned as-is (card-level data only).
        """
        to_enrich = [c for c in cards[:enrich_limit] if c.profile_url]
        rest = cards[enrich_limit:]

        sem = asyncio.Semaphore(3)  # max 3 profile pages open at once

        async def _visit(card: RawCandidate) -> RawCandidate:
            async with sem:
                try:
                    profile_page = await context.new_page()
                    full = await self._parse_profile_page(profile_page, card.profile_url)
                    await profile_page.close()
                    await self._random_delay()
                    if full:
                        return RawCandidate(
                            platform=full.platform,
                            platform_id=full.platform_id,
                            full_name=full.full_name or card.full_name,
                            headline=full.headline or card.headline,
                            location=full.location or card.location,
                            experience_years=full.experience_years,
                            skills=full.skills if full.skills else card.skills,
                            profile_url=full.profile_url or card.profile_url,
                            summary=full.summary,
                            raw_data=full.raw_data,
                        )
                except Exception as e:
                    print(f"[LinkedIn] Profile enrich failed: {e}")
                return card

        enriched = list(await asyncio.gather(*[_visit(c) for c in to_enrich]))
        return enriched + rest

    async def _scroll_page(self, page) -> None:
        await page.evaluate("() => window.scrollTo(0, document.body.scrollHeight / 2)")
        await asyncio.sleep(0.8)
        await page.evaluate("() => window.scrollTo(0, 0)")
        await asyncio.sleep(0.5)

    async def _extract_cards_via_js(self, page) -> list[RawCandidate]:
        diag = await page.evaluate("""
            () => {
                const results = [];
                const seen = new Set();

                const nameFromLink = (a) => {
                    const sp = a.querySelector('span[aria-hidden="true"]');
                    if (sp) {
                        const t = sp.innerText.trim().split('\\n')[0].trim();
                        if (t.length > 1 && t.length < 80) return t;
                    }
                    const clone = a.cloneNode(true);
                    clone.querySelectorAll('[class*="visually-hidden"], .sr-only').forEach(e => e.remove());
                    const t = clone.innerText.trim().split('\\n')[0].trim();
                    return (t.length > 1 && t.length < 80) ? t : null;
                };

                const root = document.querySelector('main')
                    || document.querySelector('[class*="scaffold-layout__main"]')
                    || document.querySelector('[role="main"]')
                    || document.body;

                const allLinks = Array.from(root.querySelectorAll('a[href*="/in/"]'));
                let noNameCount = 0;

                for (const link of allLinks) {
                    const rawHref = (link.getAttribute('href') || '').split('?')[0];
                    if (!rawHref || seen.has(rawHref)) continue;

                    const name = nameFromLink(link);
                    if (!name) { noNameCount++; continue; }

                    seen.add(rawHref);
                    const url = rawHref.startsWith('http') ? rawHref : 'https://www.linkedin.com' + rawHref;

                    let headline = null, location = null;
                    let el = link.parentElement;
                    for (let i = 0; i < 12 && el; i++) {
                        const h = el.querySelector(
                            '[class*="primary-subtitle"],[class*="subline-level-1"],.entity-result__primary-subtitle'
                        );
                        if (h) {
                            headline = h.innerText.trim().split('\\n')[0].trim() || null;
                            const l = el.querySelector(
                                '[class*="secondary-subtitle"],[class*="subline-level-2"],.entity-result__secondary-subtitle'
                            );
                            if (l) location = l.innerText.trim().split('\\n')[0].trim() || null;
                            break;
                        }
                        el = el.parentElement;
                    }

                    results.push({ profile_url: url, full_name: name, headline, location });
                }
                return {
                    results,
                    rootTag: root.tagName,
                    totalLinks: allLinks.length,
                    namedLinks: results.length,
                    noNameLinks: noNameCount,
                    pageTitle: document.title,
                };
            }
        """)

        print(f"[LinkedIn] JS extract: root=<{diag.get('rootTag')}> "
              f"totalLinks={diag.get('totalLinks')} "
              f"named={diag.get('namedLinks')} noName={diag.get('noNameLinks')} "
              f"title='{diag.get('pageTitle','')[:60]}'")

        raw_list = diag.get("results", [])

        candidates: list[RawCandidate] = []
        seen_urls: set[str] = set()

        for item in (raw_list or []):
            profile_url = item.get("profile_url", "")
            full_name = item.get("full_name") or ""
            # Skip entries without a name — these are nav-bar links or other
            # non-result anchors that happen to match the /in/ pattern
            if not profile_url or profile_url in seen_urls or "/in/" not in profile_url:
                continue
            if not full_name.strip():
                continue
            seen_urls.add(profile_url)
            platform_id = profile_url.rstrip("/").split("/")[-1] or profile_url
            candidates.append(RawCandidate(
                platform=self.PLATFORM_NAME,
                platform_id=platform_id,
                full_name=full_name,
                headline=item.get("headline"),
                location=item.get("location"),
                experience_years=None,
                skills=[],
                profile_url=profile_url,
                summary=None,
                raw_data={"source": "search_card"},
            ))

        return candidates

    async def _get_contact_info_email(self, page) -> str | None:
        """Click the Contact info link, extract email from the modal, close it."""
        try:
            link = await page.query_selector('a[href*="overlay/contact-info"]')
            if not link:
                return None
            await link.click()
            await asyncio.sleep(1.5)
            email_el = await page.query_selector('a[href^="mailto:"]')
            email = None
            if email_el:
                href = await email_el.get_attribute("href") or ""
                candidate_email = href.replace("mailto:", "").strip()
                if "@" in candidate_email:
                    email = candidate_email.lower()
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.5)
            return email
        except Exception as e:
            print(f"[LinkedIn] Contact info extraction failed: {e}")
            return None

    async def _parse_profile_page(self, page, url: str) -> RawCandidate | None:
        from playwright.async_api import TimeoutError as PWTimeout

        base_url = url.split("?")[0].rstrip("/")

        try:
            await page.goto(base_url, wait_until="domcontentloaded", timeout=30_000)
            await asyncio.sleep(2)
            # Scroll to bottom so Experience/Skills lazy sections load, then back to top
            await page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1.5)
            await page.evaluate("() => window.scrollTo(0, 0)")
            await asyncio.sleep(0.5)
        except PWTimeout:
            return None

        data = await page.evaluate("""
            () => {
                const getText = el => el ? el.innerText.trim() : null;

                // Walk up from anchor to its containing section
                const getSection = id => {
                    const anchor = document.querySelector('#' + id);
                    if (!anchor) return null;
                    let el = anchor;
                    for (let i = 0; i < 6; i++) {
                        if (!el.parentElement) break;
                        el = el.parentElement;
                        if (el.tagName === 'SECTION') return el;
                    }
                    return anchor.parentElement;
                };

                // Try selectors in order, return first that has text
                const firstMatch = (...sels) => {
                    for (const s of sels) {
                        const el = document.querySelector(s);
                        if (el && el.innerText.trim()) return el;
                    }
                    return null;
                };

                // ── Name ──────────────────────────────────────────────────────
                const nameEl = firstMatch(
                    'h1.text-heading-xlarge',
                    'h1[class*="heading"]',
                    '.ph5 h1', 'h1'
                );

                // ── Headline ──────────────────────────────────────────────────
                const headlineEl = firstMatch(
                    '.text-body-medium.break-words',
                    '.pv-text-details__left-panel .text-body-medium',
                    '.ph5 .text-body-medium'
                );

                // ── Location ──────────────────────────────────────────────────
                const locationEl = firstMatch(
                    'span.text-body-small.inline.t-black--light.break-words',
                    'span[class*="t-black--light"][class*="break-words"]',
                    '.pv-text-details__left-panel span.t-black--light',
                    '.pv-top-card--list-bullet span',
                    '.ph5 span.t-black--light'
                );

                // ── About / Summary ───────────────────────────────────────────
                let summary = null;
                const aboutSec = getSection('about');
                if (aboutSec) {
                    const spans = Array.from(aboutSec.querySelectorAll('span[aria-hidden="true"]'));
                    for (const s of spans) {
                        const t = getText(s);
                        if (t && t.length > 30) { summary = t; break; }
                    }
                }

                // ── Skills ────────────────────────────────────────────────────
                const skills = [];
                const skillsSec = getSection('skills');
                if (skillsSec) {
                    // Strategy 1: bold spans (most common LinkedIn pattern)
                    let els = Array.from(skillsSec.querySelectorAll(
                        '.t-bold span[aria-hidden="true"]'
                    )).slice(0, 20);
                    // Strategy 2: any pvs-entity bold span
                    if (!els.length) {
                        els = Array.from(skillsSec.querySelectorAll(
                            '[class*="pvs-entity"] .t-bold span[aria-hidden="true"]'
                        )).slice(0, 20);
                    }
                    // Strategy 3: all aria-hidden spans that look like skill names
                    if (!els.length) {
                        els = Array.from(skillsSec.querySelectorAll(
                            'span[aria-hidden="true"]'
                        )).slice(0, 30);
                    }
                    for (const el of els) {
                        const txt = getText(el);
                        if (txt && txt.length > 1 && txt.length < 60
                                && !txt.includes(' · ') && !skills.includes(txt)) {
                            skills.push(txt);
                        }
                    }
                }

                // ── Experience date ranges ────────────────────────────────────
                let exp_texts = [];
                const expSec = getSection('experience');
                if (expSec) {
                    exp_texts = Array.from(expSec.querySelectorAll(
                        'span[aria-hidden="true"]'
                    )).map(el => getText(el))
                      .filter(t => t && /\\d{4}/.test(t))
                      .slice(0, 10);
                }
                // Fallback: scan whole page for date-range spans
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

        # Try to grab email from Contact Info modal (public emails only)
        contact_email = await self._get_contact_info_email(page)
        if contact_email:
            print(f"[LinkedIn] Contact info email found: {contact_email}")

        platform_id = base_url.rstrip("/").split("/")[-1]

        raw_data: dict = {"source": "profile_page", "url": base_url}
        if contact_email:
            raw_data["email"] = contact_email

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
            raw_data=raw_data,
        )

    async def _random_delay(self) -> None:
        await asyncio.sleep(random.uniform(settings.SCRAPE_DELAY_MIN, settings.SCRAPE_DELAY_MAX))
