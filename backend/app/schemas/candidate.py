import re
from datetime import datetime
from pydantic import BaseModel, model_validator


class ScoreBreakdown(BaseModel):
    skills_score: float
    experience_score: float
    location_score: float
    keywords_score: float


class CandidateResponse(BaseModel):
    id: int
    rank: int | None
    platform: str
    full_name: str | None
    headline: str | None
    location: str | None
    experience_years: float | None
    skills: list[str]
    profile_url: str | None
    summary: str | None
    suitability_score: float | None
    score_breakdown: ScoreBreakdown | None
    created_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def fill_skills_from_headline(self) -> "CandidateResponse":
        """When profile skills list is empty, extract tokens from headline as fallback.

        Many LinkedIn profiles list skills pipe-separated in their headline,
        e.g. "Java Developer | Spring Boot | MySQL | REST APIs".
        """
        if not self.skills and self.headline:
            parts = re.split(r"[|,]", self.headline)
            extracted: list[str] = []
            for part in parts:
                part = part.strip()
                # Keep short tokens (likely skill names, not job titles or sentences)
                if 1 < len(part) <= 35 and " " not in part or (
                    1 < len(part) <= 35 and len(part.split()) <= 3
                ):
                    extracted.append(part)
            if extracted:
                self.skills = extracted[:12]
        return self


class CandidateListResponse(BaseModel):
    items: list[CandidateResponse]
    total: int
    request_status: str
