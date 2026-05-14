"""
Email enrichment service.

Strategy per platform:
  GitHub   → extract public email from raw_data (free, accurate)
  LinkedIn → find company domain from headline → call Snov.io with name+domain
             Snov.io only called when domain is found (saves credits)

email_status values:
  'found'     — verified email from Snov.io or GitHub public profile
  'guessed'   — pattern-generated fallback (no Snov.io credits used)
  'not_found' — could not determine any email
"""

import json
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from app.config import get_settings
from app.models.candidate import Candidate

settings = get_settings()

# ── Company domain dictionary ─────────────────────────────────────────────────

_COMPANY_DOMAINS: dict[str, str] = {
    # India IT services
    "tata consultancy services": "tcs.com",
    "tata consultancy":          "tcs.com",
    "tcs":                       "tcs.com",
    "infosys bpm":               "infosys.com",
    "infosys":                   "infosys.com",
    "wipro":                     "wipro.com",
    "cognizant":                 "cognizant.com",
    "hcltech":                   "hcltech.com",
    "hcl technologies":          "hcltech.com",
    "hcl":                       "hcltech.com",
    "tech mahindra":             "techmahindra.com",
    "techmahindra":              "techmahindra.com",
    "accenture":                 "accenture.com",
    "capgemini":                 "capgemini.com",
    "ltimindtree":               "ltimindtree.com",
    "lti mindtree":              "ltimindtree.com",
    "lti":                       "ltimindtree.com",
    "mphasis":                   "mphasis.com",
    "hexaware":                  "hexaware.com",
    "mindtree":                  "mindtree.com",
    "persistent systems":        "persistent.com",
    "persistent":                "persistent.com",
    "zensar":                    "zensar.com",
    "kpit":                      "kpit.com",
    "niit technologies":         "niit-tech.com",
    "niit":                      "niit.com",
    "mastech":                   "mastech.com",
    "birlasoft":                 "birlasoft.com",
    "cyient":                    "cyient.com",
    "sonata software":           "sonata-software.com",
    "sonata":                    "sonata-software.com",
    "tata elxsi":                "tataelxsi.com",
    "coforge":                   "coforge.com",
    # India product/startups
    "flipkart":      "flipkart.com",
    "swiggy":        "swiggy.in",
    "zomato":        "zomato.com",
    "paytm":         "paytm.com",
    "razorpay":      "razorpay.com",
    "freshworks":    "freshworks.com",
    "zoho":          "zoho.com",
    "phonepe":       "phonepe.com",
    "meesho":        "meesho.com",
    "dream11":       "dream11.com",
    "cred":          "cred.club",
    "zepto":         "zeptonow.com",
    "nykaa":         "nykaa.com",
    "byju":          "byjus.com",
    "byjus":         "byjus.com",
    "ola cabs":      "olacabs.com",
    "olacabs":       "olacabs.com",
    "ola":           "olacabs.com",
    "sharechat":     "sharechat.com",
    "cashfree":      "cashfree.com",
    "groww":         "groww.in",
    "zerodha":       "zerodha.com",
    "upstox":        "upstox.com",
    "lenskart":      "lenskart.com",
    "delhivery":     "delhivery.com",
    "urban company": "urbancompany.com",
    "urbancompany":  "urbancompany.com",
    # Global big tech
    "google":        "google.com",
    "microsoft":     "microsoft.com",
    "amazon":        "amazon.com",
    "meta":          "meta.com",
    "facebook":      "meta.com",
    "apple":         "apple.com",
    "netflix":       "netflix.com",
    "uber":          "uber.com",
    "airbnb":        "airbnb.com",
    "ibm":           "ibm.com",
    "oracle":        "oracle.com",
    "salesforce":    "salesforce.com",
    "adobe":         "adobe.com",
    "intuit":        "intuit.com",
    "atlassian":     "atlassian.com",
    "thoughtworks":  "thoughtworks.com",
    "deloitte":      "deloitte.com",
    "pwc":           "pwc.com",
    "kpmg":          "kpmg.com",
    "servicenow":    "servicenow.com",
    "vmware":        "vmware.com",
    "sap":           "sap.com",
    "samsung":       "samsung.com",
    "qualcomm":      "qualcomm.com",
    "intel":         "intel.com",
    "nvidia":        "nvidia.com",
    "paypal":        "paypal.com",
    "stripe":        "stripe.com",
    "shopify":       "shopify.com",
    "mongodb":       "mongodb.com",
    "github":        "github.com",
    "gitlab":        "gitlab.com",
}

# Pre-compile regex for word-boundary matching (longest first)
_COMPILED = sorted(
    [
        (re.compile(r'\b' + re.escape(name) + r'\b', re.IGNORECASE), domain)
        for name, domain in _COMPANY_DOMAINS.items()
    ],
    key=lambda x: -len(x[0].pattern),
)


# ── Public API ────────────────────────────────────────────────────────────────

def find_email(candidate: Candidate) -> tuple[str | None, str]:
    """
    Returns (email, status): 'found' | 'guessed' | 'not_found'
    """
    # GitHub: use public email from raw_data
    if candidate.platform == "github":
        raw = candidate.raw_data or {}
        email = raw.get("email") or ""
        if email and "@" in email:
            return email.lower().strip(), "found"
        return None, "not_found"

    # LinkedIn: find domain → call Snov.io → fallback to pattern
    if not candidate.full_name:
        return None, "not_found"

    text = " ".join(filter(None, [candidate.headline, candidate.summary]))
    domain = _find_domain(text)
    if not domain:
        return None, "not_found"

    name_parts = _split_name(candidate.full_name)
    if not name_parts:
        return None, "not_found"

    first, last = name_parts

    # Try Snov.io first (verified email)
    snov_email = _snov_find_email(first, last, domain)
    if snov_email:
        return snov_email, "found"

    # Fallback: pattern guess (no credits used)
    email = f"{first}.{last}@{domain}" if last else f"{first}@{domain}"
    return email, "guessed"


# ── Snov.io ───────────────────────────────────────────────────────────────────

def _snov_get_token() -> str | None:
    """Get Snov.io OAuth access token."""
    user_id = settings.SNOV_USER_ID.strip()
    secret = settings.SNOV_SECRET.strip()
    if not user_id or not secret:
        return None
    try:
        body = urlencode({
            "grant_type": "client_credentials",
            "client_id": user_id,
            "client_secret": secret,
        }).encode()
        req = Request(
            "https://api.snov.io/v1/oauth/access_token",
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
            return data.get("access_token")
    except Exception as e:
        print(f"[Snov] Token error: {e}")
        return None


def _snov_find_email(first: str, last: str, domain: str) -> str | None:
    """
    Call Snov.io email finder API.
    Only called when we already have a domain — avoids wasting credits.
    Returns verified email string or None.
    """
    token = _snov_get_token()
    if not token:
        return None

    try:
        body = urlencode({
            "access_token": token,
            "first_name": first,
            "last_name": last,
            "domain": domain,
        }).encode()
        req = Request(
            "https://api.snov.io/v1/get-emails-from-name",
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())

        if not data.get("success"):
            return None

        emails = data.get("data", [])
        # Return first valid/verified email
        for entry in emails:
            email = entry.get("email", "")
            status = entry.get("emailStatus", "")
            if email and status in ("valid", "all"):
                return email.lower()
        # Return first email regardless of status if no verified one
        if emails and emails[0].get("email"):
            return emails[0]["email"].lower()

        return None

    except Exception as e:
        print(f"[Snov] Email finder error: {e}")
        return None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _find_domain(text: str) -> str | None:
    """Scan text for known company using word-boundary regex."""
    if not text:
        return None
    for pattern, domain in _COMPILED:
        if pattern.search(text):
            return domain
    return None


def _split_name(full_name: str) -> tuple[str, str] | None:
    """Split full name into (first, last). Returns None if name is unusable."""
    clean = re.sub(r"[^a-zA-Z\s]", "", full_name).strip().lower()
    parts = clean.split()
    if not parts:
        return None
    first = parts[0]
    last = parts[-1] if len(parts) > 1 else ""
    return first, last
