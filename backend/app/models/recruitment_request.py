from datetime import datetime
from sqlalchemy import JSON, DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class RecruitmentRequest(Base):
    __tablename__ = "recruitment_requests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    required_skills: Mapped[list] = mapped_column(JSON, nullable=False)
    experience_min: Mapped[int] = mapped_column(default=0)
    experience_max: Mapped[int | None] = mapped_column(nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    keywords: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    platforms: Mapped[list] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("pending", "running", "completed", "failed"),
        nullable=False,
        default="pending",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    scrape_jobs: Mapped[list["ScrapeJob"]] = relationship(  # noqa: F821
        "ScrapeJob", back_populates="request", cascade="all, delete-orphan"
    )
    candidates: Mapped[list["Candidate"]] = relationship(  # noqa: F821
        "Candidate", back_populates="request", cascade="all, delete-orphan"
    )
