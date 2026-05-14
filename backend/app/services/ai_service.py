"""
Search query builder: tries Gemini first, falls back to rule-based in <2.5 s.

Gemini generates contextually smarter queries (understands tech stacks, domain,
seniority nuances). Rule-based is the safety net — always fast and correct.
"""

import json
import os
import re
import threading

# ── Title synonym dictionary ──────────────────────────────────────────────────

_SYNONYMS: dict[str, list[str]] = {
    "python developer":        ["Python Engineer", "Backend Developer"],
    "python engineer":         ["Python Developer", "Backend Engineer"],
    "backend developer":       ["Backend Engineer", "Server-side Developer"],
    "backend engineer":        ["Backend Developer", "API Developer"],
    "software developer":      ["Software Engineer", "Application Developer"],
    "software engineer":       ["Software Developer", "Application Engineer"],
    "frontend developer":      ["Frontend Engineer", "UI Developer"],
    "frontend engineer":       ["Frontend Developer", "UI Engineer"],
    "react developer":         ["React Engineer", "Frontend Developer"],
    "angular developer":       ["Angular Engineer", "Frontend Developer"],
    "vue developer":           ["Vue Engineer", "Frontend Developer"],
    "full stack developer":    ["Full Stack Engineer", "Web Developer"],
    "full stack engineer":     ["Full Stack Developer", "Web Engineer"],
    "java developer":          ["Java Engineer", "Backend Developer"],
    "java engineer":           ["Java Developer", "Backend Engineer"],
    "javascript developer":    ["JS Developer", "Frontend Engineer"],
    "node.js developer":       ["Node Developer", "Backend JavaScript Developer"],
    "node developer":          ["Node.js Engineer", "JavaScript Backend Developer"],
    "data scientist":          ["ML Engineer", "Data Analyst"],
    "machine learning engineer": ["ML Engineer", "AI Engineer"],
    "ml engineer":             ["Machine Learning Engineer", "AI Developer"],
    "data engineer":           ["Data Pipeline Engineer", "ETL Developer"],
    "data analyst":            ["Business Analyst", "BI Analyst"],
    "devops engineer":         ["DevOps Specialist", "Site Reliability Engineer"],
    "cloud engineer":          ["Cloud Architect", "DevOps Engineer"],
    "sre":                     ["Site Reliability Engineer", "DevOps Engineer"],
    "android developer":       ["Android Engineer", "Mobile Developer"],
    "ios developer":           ["iOS Engineer", "Mobile Developer"],
    "flutter developer":       ["Flutter Engineer", "Mobile Developer"],
    "react native developer":  ["React Native Engineer", "Mobile Developer"],
    "qa engineer":             ["Test Engineer", "Quality Assurance Engineer"],
    "test engineer":           ["QA Engineer", "Automation Engineer"],
    "ui/ux designer":          ["UX Designer", "Product Designer"],
    "product manager":         ["Product Owner", "Program Manager"],
    "scrum master":            ["Agile Coach", "Scrum Coach"],
    "database administrator":  ["DBA", "Database Engineer"],
}

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


# ── Seniority helper ──────────────────────────────────────────────────────────

def _seniority(exp_min: int, exp_max: int | None) -> str:
    upper = exp_max if exp_max else exp_min + 3
    mid = (exp_min + upper) / 2
    if mid <= 2:   return "Junior"
    if mid <= 5:   return "Senior" if upper >= 5 else ""
    if mid <= 8:   return "Senior"
    return "Lead"


# ── Rule-based fallback ───────────────────────────────────────────────────────

def _rule_based_queries(
    title: str,
    skills: list[str],
    keywords: list[str],
    experience_min: int,
    experience_max: int | None,
) -> list[str]:
    title_clean = title.strip()
    key = title_clean.lower()
    synonyms = _SYNONYMS.get(key, [])
    seniority = _seniority(experience_min, experience_max)

    extra_skills: list[str] = []
    for s in skills:
        related = _RELATED_SKILLS.get(s.lower(), [])
        for r in related:
            if r not in skills and r not in extra_skills:
                extra_skills.append(r)

    queries: list[str] = []

    parts1 = [title_clean] + skills[:2]
    queries.append(" ".join(parts1))

    syn1 = synonyms[0] if synonyms else title_clean
    skill_q2 = skills[2] if len(skills) > 2 else (extra_skills[0] if extra_skills else (skills[0] if skills else ""))
    parts2 = [p for p in [seniority, syn1, skill_q2] if p]
    if parts2:
        queries.append(" ".join(parts2))

    syn2 = synonyms[1] if len(synonyms) > 1 else (synonyms[0] if synonyms else title_clean)
    skill_q3 = extra_skills[0] if extra_skills else (keywords[0] if keywords else (skills[1] if len(skills) > 1 else ""))
    parts3 = [p for p in [syn2, skill_q3, skills[0] if skills else ""] if p]
    if parts3 and " ".join(parts3) not in queries:
        queries.append(" ".join(parts3))

    if len(skills) > 3:
        parts4 = [title_clean] + skills[2:4]
        q4 = " ".join(parts4)
        if q4 not in queries:
            queries.append(q4)

    if keywords:
        parts5 = [title_clean] + keywords[:2]
        q5 = " ".join(parts5)
        if q5 not in queries:
            queries.append(q5)
    elif len(extra_skills) > 1:
        parts5 = [syn1 if synonyms else title_clean] + extra_skills[:2]
        q5 = " ".join(parts5)
        if q5 not in queries:
            queries.append(q5)

    seen: set[str] = set()
    unique: list[str] = []
    for q in queries:
        q = q.strip()
        if q and q not in seen:
            seen.add(q)
            unique.append(q)

    return unique or [title_clean]


# ── Gemini query generator ────────────────────────────────────────────────────

def _gemini_queries(
    title: str,
    skills: list[str],
    keywords: list[str],
    location: str | None,
    experience_min: int,
    experience_max: int | None,
) -> list[str] | None:
    """
    Call Gemini to generate 5 smart LinkedIn search queries.
    Returns list on success, None on any failure.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None

    try:
        from google import genai  # type: ignore
        from google.genai import types as genai_types  # type: ignore

        client = genai.Client(api_key=api_key)

        exp_str = f"{experience_min}+" if not experience_max else f"{experience_min}-{experience_max}"
        skills_str = ", ".join(skills[:5]) if skills else "general"
        kw_str = ", ".join(keywords[:3]) if keywords else ""
        loc_str = location or "any"

        prompt = (
            f"Generate exactly 5 short LinkedIn search queries (3-5 words each) to find: "
            f"Role: {title}, Skills: {skills_str}, Experience: {exp_str} years, Location: {loc_str}"
            + (f", Keywords: {kw_str}" if kw_str else "")
            + ".\n\nRules:\n"
            "- Each query must be 3-5 words only (short = more LinkedIn results)\n"
            "- Use title synonyms, seniority levels, and related tech\n"
            "- Vary queries so each targets a different angle\n"
            "- Output ONLY a JSON array: [\"query1\", \"query2\", \"query3\", \"query4\", \"query5\"]\n"
            "- No explanations, no markdown, just the JSON array"
        )

        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=200,
            ),
        )

        text = response.text.strip()
        # Extract JSON array even if Gemini wraps in markdown
        match = re.search(r'\[.*?\]', text, re.DOTALL)
        if not match:
            return None

        queries = json.loads(match.group())
        if not isinstance(queries, list):
            return None

        # Validate: keep only strings, max 6 words each
        clean = [str(q).strip() for q in queries if q and len(str(q).split()) <= 7]
        return clean[:5] if len(clean) >= 3 else None

    except Exception as e:
        print(f"[QueryBuilder] Gemini failed: {e}")
        return None


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
    Return up to 5 diverse LinkedIn search queries.

    Strategy:
    - Try Gemini with a 2.5-second timeout for smarter queries
    - Merge Gemini results with rule-based (best of both)
    - Fall back to rule-based only if Gemini times out or fails
    """
    # Always compute rule-based (instant, zero cost)
    fallback = _rule_based_queries(title, skills, keywords, experience_min, experience_max)

    # Try Gemini in a thread with timeout so it never blocks the scraper
    result_holder: list[list[str] | None] = [None]

    def _run():
        result_holder[0] = _gemini_queries(title, skills, keywords, location, experience_min, experience_max)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=2.5)

    gemini_result = result_holder[0]

    if gemini_result:
        # Merge: Gemini first (smarter), then rule-based extras for diversity
        merged: list[str] = []
        seen: set[str] = set()
        for q in gemini_result + fallback:
            q = q.strip()
            if q and q.lower() not in seen:
                seen.add(q.lower())
                merged.append(q)
            if len(merged) >= 5:
                break
        print(f"[QueryBuilder] Gemini+rules: {merged}")
        return merged

    print(f"[QueryBuilder] Rule-based fallback: {fallback}")
    return fallback
