"""
Rule-based LinkedIn search query builder.

Generates 3 diverse search queries using:
  - Built-in title synonym dictionary (20+ tech roles)
  - Seniority auto-detected from experience range
  - Skill rotation across queries for broader coverage

Zero API calls — runs in microseconds, no added latency.
"""

# ── Title synonym dictionary ──────────────────────────────────────────────────

_SYNONYMS: dict[str, list[str]] = {
    # Python
    "python developer":        ["Python Engineer", "Backend Developer"],
    "python engineer":         ["Python Developer", "Backend Engineer"],
    # Backend
    "backend developer":       ["Backend Engineer", "Server-side Developer"],
    "backend engineer":        ["Backend Developer", "API Developer"],
    "software developer":      ["Software Engineer", "Application Developer"],
    "software engineer":       ["Software Developer", "Application Engineer"],
    # Frontend
    "frontend developer":      ["Frontend Engineer", "UI Developer"],
    "frontend engineer":       ["Frontend Developer", "UI Engineer"],
    "react developer":         ["React Engineer", "Frontend Developer"],
    "angular developer":       ["Angular Engineer", "Frontend Developer"],
    "vue developer":           ["Vue Engineer", "Frontend Developer"],
    # Full stack
    "full stack developer":    ["Full Stack Engineer", "Web Developer"],
    "full stack engineer":     ["Full Stack Developer", "Web Engineer"],
    # Java
    "java developer":          ["Java Engineer", "Backend Developer"],
    "java engineer":           ["Java Developer", "Backend Engineer"],
    # JavaScript / Node
    "javascript developer":    ["JS Developer", "Frontend Engineer"],
    "node.js developer":       ["Node Developer", "Backend JavaScript Developer"],
    "node developer":          ["Node.js Engineer", "JavaScript Backend Developer"],
    # Data / ML
    "data scientist":          ["ML Engineer", "Data Analyst"],
    "machine learning engineer": ["ML Engineer", "AI Engineer"],
    "ml engineer":             ["Machine Learning Engineer", "AI Developer"],
    "data engineer":           ["Data Pipeline Engineer", "ETL Developer"],
    "data analyst":            ["Business Analyst", "BI Analyst"],
    # DevOps / Cloud
    "devops engineer":         ["DevOps Specialist", "Site Reliability Engineer"],
    "cloud engineer":          ["Cloud Architect", "DevOps Engineer"],
    "sre":                     ["Site Reliability Engineer", "DevOps Engineer"],
    # Mobile
    "android developer":       ["Android Engineer", "Mobile Developer"],
    "ios developer":           ["iOS Engineer", "Mobile Developer"],
    "flutter developer":       ["Flutter Engineer", "Mobile Developer"],
    "react native developer":  ["React Native Engineer", "Mobile Developer"],
    # QA
    "qa engineer":             ["Test Engineer", "Quality Assurance Engineer"],
    "test engineer":           ["QA Engineer", "Automation Engineer"],
    # Other
    "ui/ux designer":          ["UX Designer", "Product Designer"],
    "product manager":         ["Product Owner", "Program Manager"],
    "scrum master":            ["Agile Coach", "Scrum Coach"],
    "database administrator":  ["DBA", "Database Engineer"],
}

# Related skills commonly paired with specific technologies
_RELATED_SKILLS: dict[str, list[str]] = {
    "python":    ["Django", "Flask", "FastAPI", "Celery", "SQLAlchemy"],
    "fastapi":   ["Python", "Pydantic", "SQLAlchemy", "REST API"],
    "django":    ["Python", "DRF", "PostgreSQL", "REST API"],
    "react":     ["JavaScript", "TypeScript", "Redux", "Next.js"],
    "angular":   ["TypeScript", "RxJS", "JavaScript"],
    "vue":       ["JavaScript", "Vuex", "Nuxt.js"],
    "java":      ["Spring Boot", "Hibernate", "Maven", "Microservices"],
    "node":      ["Express", "JavaScript", "TypeScript", "REST API"],
    "node.js":   ["Express", "JavaScript", "TypeScript", "REST API"],
    "aws":       ["Cloud", "Terraform", "Docker", "Kubernetes"],
    "docker":    ["Kubernetes", "DevOps", "CI/CD", "Linux"],
    "kubernetes":["Docker", "Helm", "DevOps", "Cloud"],
    "mysql":     ["SQL", "PostgreSQL", "Database", "ORM"],
    "postgresql":["SQL", "MySQL", "Database", "ORM"],
    "mongodb":   ["NoSQL", "Database", "Redis"],
    "flutter":   ["Dart", "Mobile", "iOS", "Android"],
    "machine learning": ["Python", "TensorFlow", "PyTorch", "Scikit-learn"],
    "data science":     ["Python", "Pandas", "NumPy", "SQL"],
}


# ── Seniority ─────────────────────────────────────────────────────────────────

def _seniority(exp_min: int, exp_max: int | None) -> str:
    upper = exp_max if exp_max else exp_min + 3
    mid = (exp_min + upper) / 2
    if mid <= 2:   return "Junior"
    if mid <= 5:   return "Senior" if upper >= 5 else ""
    if mid <= 8:   return "Senior"
    return "Lead"


# ── Public API ────────────────────────────────────────────────────────────────

def generate_search_queries(
    title: str,
    skills: list[str],
    keywords: list[str],
    location: str | None,
    experience_min: int,
    experience_max: int | None,
) -> list[str]:
    """
    Return 3 diverse LinkedIn search queries. Pure rule-based, zero API calls.

    Query 1: original title + top 2 skills
    Query 2: seniority + best synonym + skill 3
    Query 3: second synonym + related skill (or keyword)
    """
    title_clean = title.strip()
    key = title_clean.lower()
    synonyms = _SYNONYMS.get(key, [])

    seniority = _seniority(experience_min, experience_max)

    # Related skills — check each required skill against the lookup
    extra_skills: list[str] = []
    for s in skills:
        related = _RELATED_SKILLS.get(s.lower(), [])
        for r in related:
            if r not in skills and r not in extra_skills:
                extra_skills.append(r)
                break

    queries: list[str] = []

    # Query 1: exact title + top 2 required skills
    parts1 = [title_clean] + skills[:2]
    queries.append(" ".join(parts1))

    # Query 2: seniority + synonym (or title) + skill 3 or extra skill
    syn1 = synonyms[0] if synonyms else title_clean
    skill_q2 = skills[2] if len(skills) > 2 else (extra_skills[0] if extra_skills else (skills[0] if skills else ""))
    parts2 = [p for p in [seniority, syn1, skill_q2] if p]
    if parts2:
        queries.append(" ".join(parts2))

    # Query 3: second synonym (or title) + different skills or keywords
    syn2 = synonyms[1] if len(synonyms) > 1 else (synonyms[0] if synonyms else title_clean)
    skill_q3 = extra_skills[0] if extra_skills else (keywords[0] if keywords else (skills[1] if len(skills) > 1 else ""))
    parts3 = [p for p in [syn2, skill_q3, skills[0] if skills else ""] if p]
    if parts3 and " ".join(parts3) not in queries:
        queries.append(" ".join(parts3))

    # Deduplicate and ensure we always have at least 1
    seen: set[str] = set()
    unique: list[str] = []
    for q in queries:
        q = q.strip()
        if q and q not in seen:
            seen.add(q)
            unique.append(q)

    print(f"[QueryBuilder] Generated {len(unique)} queries: {unique}")
    return unique or [title_clean]
