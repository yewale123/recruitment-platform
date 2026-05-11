from datetime import datetime
from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class ScrapeJob(Base):
    __tablename__ = "scrape_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("recruitment_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("pending", "running", "completed", "failed"),
        nullable=False,
        default="pending",
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    candidates_found: Mapped[int] = mapped_column(default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    request: Mapped["RecruitmentRequest"] = relationship(  # noqa: F821
        "RecruitmentRequest", back_populates="scrape_jobs"
    )
    candidates: Mapped[list["Candidate"]] = relationship(  # noqa: F821
        "Candidate", back_populates="scrape_job", cascade="all, delete-orphan"
    )
