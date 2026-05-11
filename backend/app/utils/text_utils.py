"""
Text utilities for skill normalization and candidate text processing.
"""

# Maps common aliases/abbreviations → canonical skill name
SKILL_ALIASES: dict[str, str] = {
    "js": "javascript",
    "ts": "typescript",
    "py": "python",
    "ml": "machine learning",
    "ai": "artificial intelligence",
    "dl": "deep learning",
    "nlp": "natural language processing",
    "cv": "computer vision",
    "k8s": "kubernetes",
    "k8": "kubernetes",
    "pg": "postgresql",
    "postgres": "postgresql",
    "mysql": "mysql",
    "mongo": "mongodb",
    "aws": "aws",
    "gcp": "google cloud",
    "azure": "microsoft azure",
    "react.js": "react",
    "reactjs": "react",
    "vue.js": "vue",
    "vuejs": "vue",
    "node.js": "node",
    "nodejs": "node",
    "next.js": "next",
    "nextjs": "next",
    "express.js": "express",
    "expressjs": "express",
    "fast api": "fastapi",
    "flask": "flask",
    "django": "django",
    "spring boot": "spring boot",
    "springboot": "spring boot",
    "rest": "rest api",
    "restful": "rest api",
    "graphql": "graphql",
    "sql": "sql",
    "nosql": "nosql",
    "ci/cd": "ci cd",
    "cicd": "ci cd",
    "git": "git",
    "github": "github",
    "gitlab": "gitlab",
    "docker": "docker",
    "linux": "linux",
    "c++": "cpp",
    "c#": "csharp",
    ".net": "dotnet",
    "asp.net": "asp.net",
}

# Indian state/city lookup for location scoring partial match
CITY_TO_STATE: dict[str, str] = {
    "bangalore": "karnataka",
    "bengaluru": "karnataka",
    "mysore": "karnataka",
    "mysuru": "karnataka",
    "mumbai": "maharashtra",
    "pune": "maharashtra",
    "nagpur": "maharashtra",
    "hyderabad": "telangana",
    "secunderabad": "telangana",
    "chennai": "tamil nadu",
    "coimbatore": "tamil nadu",
    "delhi": "delhi",
    "new delhi": "delhi",
    "gurgaon": "haryana",
    "gurugram": "haryana",
    "noida": "uttar pradesh",
    "kolkata": "west bengal",
    "ahmedabad": "gujarat",
    "surat": "gujarat",
    "jaipur": "rajasthan",
    "chandigarh": "punjab",
    "lucknow": "uttar pradesh",
    "indore": "madhya pradesh",
    "bhopal": "madhya pradesh",
    "kochi": "kerala",
    "thiruvananthapuram": "kerala",
}


def normalize_skill(skill: str) -> str:
    """Lowercase, strip, resolve alias."""
    s = skill.lower().strip()
    return SKILL_ALIASES.get(s, s)


def normalize_skills(skills: list[str]) -> set[str]:
    return {normalize_skill(s) for s in skills if s}


def normalize_location(location: str) -> str:
    return location.lower().strip()


def same_region(loc_a: str, loc_b: str) -> bool:
    """Return True if both cities are in the same Indian state."""
    state_a = CITY_TO_STATE.get(normalize_location(loc_a))
    state_b = CITY_TO_STATE.get(normalize_location(loc_b))
    if state_a and state_b:
        return state_a == state_b
    return False


def parse_experience_years(text: str) -> float | None:
    """
    Extract a float number of years from strings like:
      "5 years", "3+ years", "2-4 years", "8 yrs", "10+ yrs experience"
    Returns the lower bound for ranges.
    """
    import re
    text = text.lower().strip()
    # Match patterns like "3+", "2-4", "5"
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:\+|-\s*\d+)?\s*(?:years?|yrs?)", text)
    if match:
        return float(match.group(1))
    return None
