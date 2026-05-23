from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Index, JSON, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Candidate(Base):
    __tablename__ = "candidates"
    __table_args__ = (
        UniqueConstraint("request_id", "platform", "platform_id", name="idx_candidates_dedup"),
        Index("idx_candidates_request_rank", "request_id", "rank"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("recruitment_requests.id", ondelete="CASCADE"), nullable=False)
    scrape_job_id: Mapped[int] = mapped_column(ForeignKey("scrape_jobs.id", ondelete="CASCADE"), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    platform_id: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    headline: Mapped[str | None] = mapped_column(String(500), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    experience_years: Mapped[float | None] = mapped_column(Numeric(4, 1), nullable=True)
    skills: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    profile_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    suitability_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    score_breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    rank: Mapped[int | None] = mapped_column(nullable=True)
    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email_sent: Mapped[bool | None] = mapped_column(nullable=True)
    resume_received: Mapped[bool | None] = mapped_column(nullable=True)
    resume_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    resume_breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    resume_parsed_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    interview_questions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    request: Mapped["RecruitmentRequest"] = relationship(  # noqa: F821
        "RecruitmentRequest", back_populates="candidates"
    )
    scrape_job: Mapped["ScrapeJob"] = relationship(  # noqa: F821
        "ScrapeJob", back_populates="candidates"
    )
