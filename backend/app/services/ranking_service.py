"""
Ranking service — scores and ranks candidates for a recruitment request.

Scoring dimensions (total = 100 pts):
  Skills match    40 pts  — hard requirement matching with alias normalization
  Experience      25 pts  — fit to requested years range
  Location        20 pts  — exact city / same state / remote / mismatch
  Keywords        15 pts  — keyword hits in headline + summary
"""

from app.models.candidate import Candidate
from app.models.recruitment_request import RecruitmentRequest
from app.utils.text_utils import normalize_skills, normalize_location, same_region


def score_and_rank(
    candidates: list[Candidate],
    request: RecruitmentRequest,
) -> list[Candidate]:
    """
    Compute suitability_score + score_breakdown for every candidate,
    then assign rank (1 = best). Modifies candidates in-place and returns them.
    """
    required_skills = normalize_skills(request.required_skills)
    keywords = [kw.lower().strip() for kw in (request.keywords or [])]
    req_location = normalize_location(request.location or "")
    exp_min = request.experience_min or 0
    exp_max = request.experience_max

    for c in candidates:
        skills_score = _skills_score(c, required_skills)
        experience_score = _experience_score(c, exp_min, exp_max)
        location_score = _location_score(c, req_location)
        keywords_score = _keywords_score(c, keywords)

        total = skills_score + experience_score + location_score + keywords_score

        c.suitability_score = round(total, 2)
        c.score_breakdown = {
            "skills_score": round(skills_score, 2),
            "experience_score": round(experience_score, 2),
            "location_score": round(location_score, 2),
            "keywords_score": round(keywords_score, 2),
        }

    # Sort: primary = suitability_score desc, tiebreaker = skills_score desc
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

def _skills_score(candidate: Candidate, required_skills: set[str]) -> float:
    if not required_skills:
        return 40.0

    candidate_skills = normalize_skills(candidate.skills or [])

    # Fallback: extract skills from headline + summary text when profile skills list is empty.
    # Many LinkedIn profiles have skills in their headline (e.g. "Java | Spring Boot | REST APIs").
    if not candidate_skills:
        text = " ".join(filter(None, [candidate.headline, candidate.summary])).lower()
        candidate_skills = {s for s in required_skills if s in text}

    matched = len(candidate_skills & required_skills)
    return (matched / len(required_skills)) * 40.0


def _experience_score(candidate: Candidate, exp_min: int, exp_max: int | None) -> float:
    years = candidate.experience_years
    if years is None:
        return 10.0  # neutral — no data, give partial credit

    years = float(years)

    if exp_max is not None:
        if exp_min <= years <= exp_max:
            return 25.0
        if years < exp_min:
            gap = exp_min - years
            return max(0.0, 25.0 - gap * 5.0)
        # overqualified — less harsh penalty
        gap = years - exp_max
        return max(0.0, 25.0 - gap * 3.0)
    else:
        # No upper bound specified — only penalize being under min
        if years >= exp_min:
            return 25.0
        gap = exp_min - years
        return max(0.0, 25.0 - gap * 5.0)


def _location_score(candidate: Candidate, req_location: str) -> float:
    if not req_location or req_location == "remote":
        return 20.0  # any location qualifies

    cand_loc = normalize_location(candidate.location or "")
    if not cand_loc:
        return 5.0  # no location data — minimal credit

    if "remote" in cand_loc:
        return 15.0  # candidate is remote-willing — likely good

    if cand_loc == req_location:
        return 20.0  # exact match

    if same_region(cand_loc, req_location):
        return 10.0  # same state

    return 0.0


def _keywords_score(candidate: Candidate, keywords: list[str]) -> float:
    if not keywords:
        return 15.0  # no keywords specified — full score
    text = " ".join(filter(None, [candidate.headline, candidate.summary])).lower()
    matched = sum(1 for kw in keywords if kw in text)
    return min(15.0, (matched / len(keywords)) * 15.0)
