"""
Ranking service — scores and ranks candidates for a recruitment request.

Scoring dimensions (total = 100 pts):
  Skills match    40 pts  — critical skills weighted higher, related skills get partial credit
  Experience      25 pts  — fit to requested years range with smooth curve
  Location        20 pts  — exact city / same state / remote / mismatch
  Context         15 pts  — seniority match, availability signals, keyword hits
"""

from app.models.candidate import Candidate
from app.models.recruitment_request import RecruitmentRequest
from app.utils.text_utils import normalize_skills, normalize_location, same_region

# Skills that are "close enough" to get partial credit.
# Parent language entries list their frameworks as aliases so that GitHub
# candidates (who have language names) match framework requirements.
# Framework entries list their parent language so LinkedIn candidates
# (who list frameworks) match language requirements — and vice versa.
_SKILL_ALIASES: dict[str, list[str]] = {
    # ── Language → frameworks (GitHub reports language names, not frameworks) ──
    "javascript": ["js", "ecmascript", "es6", "es2015",
                   "react", "reactjs", "react.js",
                   "angular", "angularjs",
                   "vue", "vuejs", "vue.js",
                   "node.js", "node", "nodejs",
                   "express", "expressjs",
                   "next.js", "nextjs", "nuxt",
                   "jquery", "svelte", "sveltekit"],
    "typescript": ["ts",
                   "angular", "angularjs",
                   "next.js", "nextjs"],
    "python":     ["py",
                   "django", "flask", "fastapi", "tornado",
                   "pandas", "numpy", "scipy",
                   "tensorflow", "tf", "pytorch", "keras",
                   "scikit-learn", "sklearn", "xgboost",
                   "jupyter notebook", "jupyter", "ipython",
                   "celery", "sqlalchemy", "pydantic"],
    "java":       ["spring", "spring boot", "springboot",
                   "hibernate", "maven", "gradle",
                   "micronaut", "quarkus"],
    "ruby":       ["rails", "ruby on rails", "sinatra"],
    "php":        ["laravel", "symfony", "codeigniter"],
    "go":         ["golang", "gin", "echo", "fiber"],
    "swift":      ["swiftui", "ios"],
    "kotlin":     ["android", "jetpack compose"],

    # ── Framework synonyms + parent language (bidirectional) ─────────────────
    "node.js":    ["node", "nodejs", "javascript", "js"],
    "react":      ["reactjs", "react.js", "javascript", "js"],
    "angular":    ["angularjs", "typescript", "ts", "javascript", "js"],
    "vue":        ["vuejs", "vue.js", "javascript", "js"],
    "next.js":    ["nextjs", "javascript", "js", "typescript", "ts"],
    "express":    ["expressjs", "javascript", "js"],
    "django":     ["python", "py"],
    "flask":      ["python", "py"],
    "fastapi":    ["python", "py"],
    "tensorflow": ["tf", "python", "py"],
    "pytorch":    ["python", "py"],
    "pandas":     ["python", "py"],
    "numpy":      ["python", "py"],
    "scikit-learn": ["sklearn", "python", "py"],
    "jupyter notebook": ["jupyter", "ipython", "python", "py"],
    "spring boot": ["spring", "springboot", "java"],

    # ── Infrastructure / DB synonyms ──────────────────────────────────────────
    "postgresql": ["postgres", "psql"],
    "mongodb":    ["mongo"],
    "kubernetes": ["k8s"],
    "machine learning": ["ml"],
    "artificial intelligence": ["ai"],
    "rest api":   ["restful", "rest apis", "api"],
}

_SENIORITY_SIGNALS = {
    "lead": 2, "principal": 2, "architect": 2, "head of": 2, "vp of": 2,
    "senior": 1, "sr.": 1, "sr ": 1, "staff": 1,
    "junior": -1, "jr.": -1, "jr ": -1, "entry level": -1, "fresher": -1, "intern": -2,
}

_AVAILABILITY_SIGNALS = [
    "open to work", "actively looking", "seeking opportunities",
    "available for", "looking for new", "open for opportunities",
    "#opentowork", "job seeking", "actively seeking",
]


def _split_skills(val) -> list[str]:
    """Normalize skills whether stored as list or comma-separated string."""
    if not val:
        return []
    if isinstance(val, str):
        return [s.strip() for s in val.split(",") if s.strip()]
    result = []
    for item in val:
        result.extend(s.strip() for s in str(item).split(",") if s.strip())
    return result


def score_and_rank(
    candidates: list[Candidate],
    request: RecruitmentRequest,
) -> list[Candidate]:
    all_skills_raw = _split_skills(request.required_skills)
    required_skills = normalize_skills(all_skills_raw)
    critical_skills = normalize_skills(all_skills_raw[:2]) if all_skills_raw else required_skills

    # Pre-expand alias sets once — reused for every candidate instead of recomputing each time
    required_expanded = _expand_aliases(required_skills)
    critical_expanded = _expand_aliases(critical_skills)
    secondary_skills_expanded = required_expanded - critical_expanded

    keywords = [kw.lower().strip() for kw in (request.keywords or [])]
    req_location = normalize_location(request.location or "")
    exp_min = request.experience_min or 0
    exp_max = request.experience_max

    for c in candidates:
        skills_score = _skills_score(c, required_skills, critical_expanded, secondary_skills_expanded)
        experience_score = _experience_score(c, exp_min, exp_max)
        location_score = _location_score(c, req_location)
        context_score = _context_score(c, keywords, exp_min, exp_max)

        total = skills_score + experience_score + location_score + context_score

        c.suitability_score = round(total, 2)
        c.score_breakdown = {
            "skills_score": round(skills_score, 2),
            "experience_score": round(experience_score, 2),
            "location_score": round(location_score, 2),
            "keywords_score": round(context_score, 2),
        }

    candidates.sort(
        key=lambda c: (
            c.suitability_score or 0,
            c.score_breakdown.get("skills_score", 0) if c.score_breakdown else 0,
        ),
        reverse=True,
    )

    for i, c in enumerate(candidates, start=1):
        c.rank = i

    return candidates


# ── Dimension scorers ─────────────────────────────────────────────────────────

def _expand_aliases(skills: set[str]) -> set[str]:
    """Add alias variants so 'node.js' matches 'node', etc."""
    expanded = set(skills)
    for canonical, aliases in _SKILL_ALIASES.items():
        if canonical in skills:
            expanded.update(aliases)
        for alias in aliases:
            if alias in skills:
                expanded.add(canonical)
    return expanded


def _skills_score(
    candidate: Candidate,
    required_skills: set[str],
    critical_expanded: set[str],
    secondary_skills_expanded: set[str],
) -> float:
    if not required_skills:
        return 40.0

    candidate_skills = normalize_skills(candidate.skills or [])

    # Fallback: scan headline + summary when profile skills list is empty
    profile_text = " ".join(filter(None, [candidate.headline, candidate.summary])).lower()
    if not candidate_skills:
        candidate_skills = {s for s in required_skills if s in profile_text}
    else:
        text_skills = {s for s in required_skills if s in profile_text}
        candidate_skills = candidate_skills | text_skills

    # Expand aliases for this candidate only (required sets already pre-expanded)
    candidate_expanded = _expand_aliases(candidate_skills)

    # Critical skills: first 2 — worth 60% of skills score
    critical_total = len(critical_expanded) if critical_expanded else 1
    critical_matched = len(candidate_expanded & critical_expanded)
    critical_pts = (critical_matched / critical_total) * 24.0

    # Secondary skills: remaining — worth 40% of skills score
    if secondary_skills_expanded:
        secondary_matched = len(candidate_expanded & secondary_skills_expanded)
        secondary_pts = (secondary_matched / len(secondary_skills_expanded)) * 16.0
    else:
        # Only critical skills were specified — scale up to full 40
        secondary_pts = 0.0
        critical_pts = (critical_matched / critical_total) * 40.0

    return critical_pts + secondary_pts


def _experience_score(candidate: Candidate, exp_min: int, exp_max: int | None) -> float:
    years = candidate.experience_years
    if years is None:
        return 10.0

    years = float(years)

    if exp_max is not None:
        if exp_min <= years <= exp_max:
            return 25.0
        if years < exp_min:
            gap = exp_min - years
            return max(0.0, 25.0 - gap * 5.0)
        gap = years - exp_max
        return max(0.0, 25.0 - gap * 3.0)
    else:
        if years >= exp_min:
            return 25.0
        gap = exp_min - years
        return max(0.0, 25.0 - gap * 5.0)


def _location_score(candidate: Candidate, req_location: str) -> float:
    if not req_location or req_location == "remote":
        return 20.0

    cand_loc = normalize_location(candidate.location or "")
    if not cand_loc:
        return 5.0

    if "remote" in cand_loc:
        return 15.0

    # LinkedIn returns full strings like "Mumbai, Maharashtra, India"
    # Extract primary city for comparison
    cand_city = cand_loc.split(",")[0].strip()

    if cand_city == req_location or cand_loc == req_location:
        return 20.0

    # Required location appears anywhere in candidate's location string
    if req_location in cand_loc:
        return 20.0

    if same_region(cand_city, req_location):
        return 10.0

    return 0.0


def _context_score(
    candidate: Candidate,
    keywords: list[str],
    exp_min: int,
    exp_max: int | None,
) -> float:
    """
    15-point context score combining:
    - Keyword hits in headline + summary          (up to 7 pts)
    - Availability signals ("open to work", etc.) (up to 4 pts)
    - Seniority alignment from headline           (up to 4 pts)
    """
    text = " ".join(filter(None, [candidate.headline, candidate.summary])).lower()

    # Keyword hits
    if keywords:
        matched = sum(1 for kw in keywords if kw in text)
        keyword_pts = min(7.0, (matched / len(keywords)) * 7.0)
    else:
        keyword_pts = 7.0

    # Availability signals
    availability_pts = 0.0
    for signal in _AVAILABILITY_SIGNALS:
        if signal in text:
            availability_pts = 4.0
            break

    # Seniority alignment
    seniority_pts = _seniority_alignment(text, exp_min, exp_max)

    return keyword_pts + availability_pts + seniority_pts


def _seniority_alignment(text: str, exp_min: int, exp_max: int | None) -> float:
    """
    Award up to 4 pts when the candidate's seniority signals match the experience range.
    Penalize mismatches (senior candidate for junior role, etc.).
    """
    upper = exp_max if exp_max else exp_min + 3
    mid = (exp_min + upper) / 2

    # Expected level: 0-2y=junior, 3-7y=mid/senior, 8+=lead
    if mid <= 2:
        expected = "junior"
    elif mid <= 7:
        expected = "senior"
    else:
        expected = "lead"

    signal_score = 0
    for signal, weight in _SENIORITY_SIGNALS.items():
        if signal in text:
            signal_score += weight

    # Clamp to [-2, 2]
    signal_score = max(-2, min(2, signal_score))

    if expected == "junior":
        if signal_score < 0:   return 4.0   # junior signals for junior role — good
        if signal_score == 0:  return 2.0   # neutral
        return 0.0                           # senior/lead for junior role — mismatch

    if expected == "lead":
        if signal_score > 0:   return 4.0   # senior/lead signals — good
        if signal_score == 0:  return 2.0
        return 0.0

    # Mid/senior role — moderate signals preferred
    if signal_score >= 1:   return 4.0
    if signal_score == 0:   return 2.0
    return 1.0  # slight junior signal — small penalty but not disqualifying
