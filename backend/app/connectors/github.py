"""
GitHub platform connector — uses the official GitHub REST API (no browser needed).

Why GitHub:
  - Free public API, no scraping/Playwright required
  - Developers often have public email, location, bio
  - Repo languages reveal tech stack (better than self-reported skills)
  - Fast: 30-50 candidates in ~5 seconds vs 60s for LinkedIn

Rate limits:
  - No token: 60 requests/hour  (use for testing only)
  - With token: 5000 requests/hour (set GITHUB_TOKEN in .env — free to generate)

Setup:
  github.com → Settings → Developer settings → Personal access tokens → Fine-grained
  Scope: Public repos (read-only) is enough. No special permissions needed.
"""

import asyncio
import json
import re
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from app.config import get_settings
from app.connectors.base import BasePlatformConnector, RawCandidate, RecruitmentCriteria
from app.utils.text_utils import parse_experience_years

settings = get_settings()

_BASE = "https://api.github.com"

# Map common skill names → GitHub language names
_SKILL_TO_LANG: dict[str, str] = {
    "python": "Python",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "java": "Java",
    "kotlin": "Kotlin",
    "swift": "Swift",
    "go": "Go",
    "golang": "Go",
    "rust": "Rust",
    "ruby": "Ruby",
    "php": "PHP",
    "c#": "C#",
    "csharp": "C#",
    "c++": "C++",
    "cpp": "C++",
    "scala": "Scala",
    "dart": "Dart",
    "r": "R",
    "matlab": "MATLAB",
    "shell": "Shell",
    "bash": "Shell",
    "html": "HTML",
    "css": "CSS",
    "vue": "Vue",
    "react": "JavaScript",
    "node": "JavaScript",
    "node.js": "JavaScript",
    "django": "Python",
    "flask": "Python",
    "fastapi": "Python",
    "spring": "Java",
    "spring boot": "Java",
    "flutter": "Dart",
    "android": "Kotlin",
    "ios": "Swift",
}


class GitHubConnector(BasePlatformConnector):
    PLATFORM_NAME = "github"

    # ── Public API ────────────────────────────────────────────────────────────

    async def search(self, criteria: RecruitmentCriteria) -> list[RawCandidate]:
        token = getattr(settings, "GITHUB_TOKEN", "").strip()
        queries = self._build_gh_queries(criteria)
        max_results = min(criteria.max_results, 60)

        loop = asyncio.get_event_loop()

        seen_logins: set[str] = set()
        all_candidates: list[RawCandidate] = []

        for i, query in enumerate(queries):
            if len(all_candidates) >= max_results:
                break
            print(f"[GitHub] Query {i+1}/{len(queries)}: '{query}'")
            try:
                users = await loop.run_in_executor(
                    None, lambda q=query: self._search_users(q, per_page=30, token=token)
                )
            except Exception as e:
                print(f"[GitHub] Search failed: {e}")
                continue

            new_logins = [u["login"] for u in users if u["login"] not in seen_logins]
            seen_logins.update(new_logins)
            print(f"[GitHub] → {len(new_logins)} new users")

            # Fetch user details in batches (throttled to avoid rate limits)
            remaining = max_results - len(all_candidates)
            for login in new_logins[:remaining]:
                try:
                    candidate = await loop.run_in_executor(
                        None, lambda l=login: self._fetch_user(l, token=token)
                    )
                    if candidate:
                        all_candidates.append(candidate)
                    await asyncio.sleep(0.2)  # gentle throttle
                except Exception as e:
                    print(f"[GitHub] User fetch failed for {login}: {e}")

            if i < len(queries) - 1:
                await asyncio.sleep(1.0)  # pause between search queries

        print(f"[GitHub] Total candidates: {len(all_candidates)}")
        return all_candidates

    async def get_profile(self, profile_url: str) -> RawCandidate | None:
        login = profile_url.rstrip("/").split("/")[-1]
        token = getattr(settings, "GITHUB_TOKEN", "").strip()
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(
                None, lambda: self._fetch_user(login, token=token)
            )
        except Exception as e:
            print(f"[GitHub] get_profile failed for {profile_url}: {e}")
            return None

    # ── Query builder ─────────────────────────────────────────────────────────

    def _build_gh_queries(self, criteria: RecruitmentCriteria) -> list[str]:
        """
        Build up to 3 GitHub user search queries.
        GitHub search syntax: language:X location:Y followers:>N
        """
        skills = criteria.required_skills or []
        location = (criteria.location or "").strip()
        queries: list[str] = []

        loc_part = f"location:{location}" if location and location.lower() not in ("remote", "any") else ""

        # Query 1: primary language + location
        primary_lang = None
        for s in skills:
            lang = _SKILL_TO_LANG.get(s.lower())
            if lang:
                primary_lang = lang
                break

        if primary_lang:
            parts = [f"language:{primary_lang}"]
            if loc_part:
                parts.append(loc_part)
            parts.append("followers:>2")
            queries.append(" ".join(parts))

        # Query 2: title keywords + location
        title_words = criteria.title.split()[:3]
        parts2 = title_words[:]
        if loc_part:
            parts2.append(loc_part)
        parts2.append("repos:>2")
        queries.append(" ".join(parts2))

        # Query 3: secondary language or skill-based
        secondary_lang = None
        for s in skills[1:]:
            lang = _SKILL_TO_LANG.get(s.lower())
            if lang and lang != primary_lang:
                secondary_lang = lang
                break

        if secondary_lang:
            parts3 = [f"language:{secondary_lang}"]
            if loc_part:
                parts3.append(loc_part)
            parts3.append("followers:>2")
            q3 = " ".join(parts3)
            if q3 not in queries:
                queries.append(q3)
        elif criteria.search_queries:
            # Use first AI-generated query as keyword search
            kw = criteria.search_queries[0].split()[:3]
            parts3 = kw[:]
            if loc_part:
                parts3.append(loc_part)
            q3 = " ".join(parts3)
            if q3 not in queries:
                queries.append(q3)

        return queries[:3]

    # ── GitHub API calls (sync, run in executor) ──────────────────────────────

    def _gh_request(self, url: str, token: str) -> dict | list:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "recruitment-platform/1.0",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = Request(url, headers=headers)
        try:
            with urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        except HTTPError as e:
            if e.code == 403:
                raise RuntimeError("GitHub rate limit hit. Set GITHUB_TOKEN in .env for higher limits.")
            if e.code == 422:
                raise RuntimeError(f"GitHub search query invalid: {url}")
            raise

    def _search_users(self, query: str, per_page: int, token: str) -> list[dict]:
        from urllib.parse import urlencode
        params = urlencode({"q": f"{query} type:user", "per_page": per_page, "sort": "followers"})
        url = f"{_BASE}/search/users?{params}"
        data = self._gh_request(url, token)
        return data.get("items", [])

    def _fetch_user(self, login: str, token: str) -> RawCandidate | None:
        user = self._gh_request(f"{_BASE}/users/{login}", token)
        if not isinstance(user, dict) or user.get("type") == "Organization":
            return None

        # Infer skills from top repos' languages
        skills = self._get_repo_languages(login, token)

        # Experience estimation
        exp_years: float | None = None
        bio = user.get("bio") or ""
        if bio:
            exp_years = parse_experience_years(bio)
        if exp_years is None:
            created_str = user.get("created_at", "")
            if created_str:
                try:
                    created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                    account_age = (datetime.now(timezone.utc) - created).days / 365
                    # Only use if account is reasonably old (>1 year) and has repos
                    if account_age >= 1 and user.get("public_repos", 0) >= 3:
                        exp_years = round(min(account_age * 0.7, 15), 1)
                except Exception:
                    pass

        # Build headline from available fields
        headline_parts = []
        if bio:
            headline_parts.append(bio[:150])
        company = user.get("company", "") or ""
        if company:
            headline_parts.append(f"@ {company.lstrip('@').strip()}")
        headline = " | ".join(filter(None, headline_parts)) or None

        # Summary with repo/follower context
        summary_parts = []
        if bio:
            summary_parts.append(bio)
        repos = user.get("public_repos", 0)
        followers = user.get("followers", 0)
        if repos or followers:
            summary_parts.append(f"{repos} public repos · {followers} followers")
        blog = user.get("blog", "") or ""
        if blog and blog.startswith("http"):
            summary_parts.append(f"Website: {blog}")
        summary = "\n".join(summary_parts) or None

        # Email (public only — many devs set this)
        email = user.get("email") or ""

        return RawCandidate(
            platform=self.PLATFORM_NAME,
            platform_id=login,
            full_name=user.get("name") or login,
            headline=headline,
            location=user.get("location"),
            experience_years=exp_years,
            skills=skills,
            profile_url=user.get("html_url") or f"https://github.com/{login}",
            summary=summary,
            raw_data={
                "email": email,
                "company": company,
                "public_repos": user.get("public_repos", 0),
                "followers": user.get("followers", 0),
                "hireable": user.get("hireable"),
                "blog": blog,
            },
        )

    def _get_repo_languages(self, login: str, token: str) -> list[str]:
        """Get top programming languages from user's most recent repos."""
        try:
            repos = self._gh_request(
                f"{_BASE}/users/{login}/repos?sort=updated&per_page=10&type=owner",
                token,
            )
            if not isinstance(repos, list):
                return []

            lang_counts: dict[str, int] = {}
            for repo in repos:
                lang = repo.get("language")
                if lang:
                    lang_counts[lang] = lang_counts.get(lang, 0) + 1

            # Return languages sorted by frequency, top 8
            return [lang for lang, _ in sorted(lang_counts.items(), key=lambda x: -x[1])][:8]
        except Exception:
            return []
