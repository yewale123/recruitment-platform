"""
Email enrichment service.

Strategy per platform:
  GitHub   → public email from raw_data (GitHub API, free)
  LinkedIn → email from Contact Info modal (scraped during profile visit, free)

email_status values:
  'found'     — real email from GitHub profile or LinkedIn Contact Info
  'not_found' — no real email found
"""

from app.models.candidate import Candidate


def find_email(candidate: Candidate) -> tuple[str | None, str]:
    """
    Returns (email, status): 'found' | 'not_found'
    Only returns real verified emails — no pattern guessing.
    """
    # GitHub: public email from GitHub API via raw_data
    if candidate.platform == "github":
        raw = candidate.raw_data or {}
        email = raw.get("email") or ""
        if email and "@" in email:
            return email.lower().strip(), "found"
        return None, "not_found"

    # LinkedIn: email scraped from Contact Info modal during enrichment
    raw = candidate.raw_data or {}
    contact_email = raw.get("email", "")
    if contact_email and "@" in contact_email:
        return contact_email.lower().strip(), "found"

    return None, "not_found"
