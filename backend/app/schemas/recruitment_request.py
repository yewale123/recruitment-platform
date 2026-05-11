from datetime import datetime
from pydantic import BaseModel, Field


class RecruitmentRequestCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=255, examples=["Senior Python Developer"])
    required_skills: list[str] = Field(..., min_length=1, examples=[["Python", "FastAPI"]])
    experience_min: int = Field(0, ge=0, le=50)
    experience_max: int | None = Field(None, ge=0, le=50)
    location: str | None = Field(None, max_length=255, examples=["Bangalore"])
    keywords: list[str] = Field(default_factory=list)
    platforms: list[str] = Field(default=["linkedin"], min_length=1)


class ScrapeJobSummary(BaseModel):
    id: int
    platform: str
    status: str
    candidates_found: int
    error_message: str | None = None
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class RecruitmentRequestResponse(BaseModel):
    id: int
    title: str
    required_skills: list[str]
    experience_min: int
    experience_max: int | None
    location: str | None
    keywords: list[str]
    platforms: list[str]
    status: str
    candidate_count: int = 0
    scrape_jobs: list[ScrapeJobSummary] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RecruitmentRequestListItem(BaseModel):
    id: int
    title: str
    status: str
    candidate_count: int
    platforms: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class RecruitmentRequestListResponse(BaseModel):
    items: list[RecruitmentRequestListItem]
    total: int
