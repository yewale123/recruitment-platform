"""
Email enrichment service.

Strategy per platform:
  GitHub   → extract public email from raw_data (accurate, free)
  LinkedIn → scan headline+summary for known company, build email pattern

email_status values:
  'found'     — real email confirmed from profile (GitHub public email)
  'guessed'   — pattern-generated from name + company domain (LinkedIn)
  'not_found' — could not determine any email
"""

import re
from app.models.candidate import Candidate

# Company name → email domain (word-boundary matched against headline/summary)
# Sorted longest-first so "tech mahindra" matches before "mahindra"
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
    "mphasis":                   "mphasis.com",
    "sonata software":           "sonata-software.com",
    "sonata":                    "sonata-software.com",
    "sasken":                    "sasken.com",
    "tata elxsi":                "tataelxsi.com",
    "coforge":                   "coforge.com",
    # India product/startups
    "flipkart":    "flipkart.com",
    "swiggy":      "swiggy.in",
    "zomato":      "zomato.com",
    "paytm":       "paytm.com",
    "razorpay":    "razorpay.com",
    "freshworks":  "freshworks.com",
    "zoho":        "zoho.com",
    "phonepe":     "phonepe.com",
    "meesho":      "meesho.com",
    "dream11":     "dream11.com",
    "cred":        "cred.club",
    "zepto":       "zeptonow.com",
    "nykaa":       "nykaa.com",
    "byju":        "byjus.com",
    "byjus":       "byjus.com",
    "ola cabs":    "olacabs.com",
    "olacabs":     "olacabs.com",
    "ola":         "olacabs.com",
    "sharechat":   "sharechat.com",
    "moj":         "sharechat.com",
    "slice":       "sliceit.com",
    "cashfree":    "cashfree.com",
    "groww":       "groww.in",
    "zerodha":     "zerodha.com",
    "upstox":      "upstox.com",
    "lenskart":    "lenskart.com",
    "mamaearth":   "mamaearth.in",
    "delhivery":   "delhivery.com",
    "rivigo":      "rivigo.com",
    "urbanclap":   "urbancompany.com",
    "urban company": "urbancompany.com",
    # Global big tech
    "google":      "google.com",
    "microsoft":   "microsoft.com",
    "amazon":      "amazon.com",
    "meta":        "meta.com",
    "facebook":    "meta.com",
    "apple":       "apple.com",
    "netflix":     "netflix.com",
    "uber":        "uber.com",
    "airbnb":      "airbnb.com",
    "twitter":     "twitter.com",
    "linkedin":    "linkedin.com",
    "ibm":         "ibm.com",
    "oracle":      "oracle.com",
    "salesforce":  "salesforce.com",
    "adobe":       "adobe.com",
    "intuit":      "intuit.com",
    "atlassian":   "atlassian.com",
    "thoughtworks":"thoughtworks.com",
    "deloitte":    "deloitte.com",
    "pwc":         "pwc.com",
    "kpmg":        "kpmg.com",
    "servicenow":  "servicenow.com",
    "vmware":      "vmware.com",
    "sap":         "sap.com",
    "samsung":     "samsung.com",
    "qualcomm":    "qualcomm.com",
    "intel":       "intel.com",
    "amd":         "amd.com",
    "nvidia":      "nvidia.com",
    "paypal":      "paypal.com",
    "stripe":      "stripe.com",
    "shopify":     "shopify.com",
    "twilio":      "twilio.com",
    "datadog":     "datadoghq.com",
    "mongodb":     "mongodb.com",
    "elastic":     "elastic.co",
    "github":      "github.com",
    "gitlab":      "gitlab.com",
}

# Pre-compile regex patterns (word boundary around each company name)
# Sorted longest-first so multi-word names match before single words
_COMPILED = sorted(
    [
        (re.compile(r'\b' + re.escape(name) + r'\b', re.IGNORECASE), domain)
        for name, domain in _COMPANY_DOMAINS.items()
    ],
    key=lambda x: -len(x[0].pattern),
)


def find_email(candidate: Candidate) -> tuple[str | None, str]:
    """
    Returns (email, status): 'found' | 'guessed' | 'not_found'
    """
    if candidate.platform == "github":
        raw = candidate.raw_data or {}
        email = raw.get("email") or ""
        if email and "@" in email:
            return email.lower().strip(), "found"
        return None, "not_found"

    # LinkedIn / others
    if not candidate.full_name:
        return None, "not_found"

    # Scan headline + summary for known company
    text = " ".join(filter(None, [candidate.headline, candidate.summary]))
    domain = _find_domain(text)
    if not domain:
        return None, "not_found"

    email = _build_email(candidate.full_name, domain)
    return (email, "guessed") if email else (None, "not_found")


def _find_domain(text: str) -> str | None:
    """Scan text for any known company using word-boundary regex."""
    if not text:
        return None
    for pattern, domain in _COMPILED:
        if pattern.search(text):
            return domain
    return None


def _build_email(full_name: str, domain: str) -> str | None:
    """Generate firstname.lastname@domain pattern from full name."""
    clean = re.sub(r"[^a-zA-Z\s]", "", full_name).strip().lower()
    parts = clean.split()
    if not parts:
        return None
    first = parts[0]
    last = parts[-1] if len(parts) > 1 else ""
    return f"{first}.{last}@{domain}" if last else f"{first}@{domain}"
