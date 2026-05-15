"""
Email enrichment service.

Strategy per platform:
  GitHub   → public email from raw_data (GitHub API, free)
  LinkedIn → email from Contact Info modal (scraped during enrichment, free)
             fallback: pattern-generate from company domain (unverified, marked ~)

email_status values:
  'found'     — real email from GitHub profile or LinkedIn Contact Info
  'guessed'   — pattern-generated fallback (firstname.lastname@company.com)
  'not_found' — could not determine any email
"""

import re

from app.models.candidate import Candidate

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
    # GitHub: public email from GitHub API via raw_data
    if candidate.platform == "github":
        raw = candidate.raw_data or {}
        email = raw.get("email") or ""
        if email and "@" in email:
            return email.lower().strip(), "found"
        return None, "not_found"

    # LinkedIn: check email scraped from Contact Info modal during enrichment
    raw = candidate.raw_data or {}
    contact_email = raw.get("email", "")
    if contact_email and "@" in contact_email:
        return contact_email.lower().strip(), "found"

    # Fallback: pattern-generate from company domain (unverified)
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
    email = f"{first}.{last}@{domain}" if last else f"{first}@{domain}"
    return email, "guessed"


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
