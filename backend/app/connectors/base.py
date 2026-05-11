"""
Abstract base class for all platform connectors.

To add a new platform:
  1. Create app/connectors/<platform>.py
  2. Subclass BasePlatformConnector and set PLATFORM_NAME
  3. Implement search() and get_profile()
  4. Register it in app/connectors/__init__.py → CONNECTOR_REGISTRY
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class RecruitmentCriteria:
    title: str
    required_skills: list[str]
    experience_min: int
    experience_max: int | None
    location: str | None
    keywords: list[str]
    max_results: int = 50
    search_queries: list[str] = field(default_factory=list)


@dataclass
class RawCandidate:
    platform: str
    platform_id: str
    full_name: str | None
    headline: str | None
    location: str | None
    experience_years: float | None
    skills: list[str]
    profile_url: str | None
    summary: str | None
    raw_data: dict = field(default_factory=dict)


class BasePlatformConnector(ABC):
    PLATFORM_NAME: str = ""

    @abstractmethod
    async def search(
        self,
        criteria: RecruitmentCriteria,
    ) -> list[RawCandidate]:
        """
        Search the platform for candidates matching the given criteria.
        Must manage its own browser/session lifecycle.
        """
        ...

    @abstractmethod
    async def get_profile(self, profile_url: str) -> RawCandidate | None:
        """
        Fetch detailed profile data for a single candidate URL.
        Return None if the profile cannot be fetched.
        """
        ...

    def build_search_query(self, criteria: RecruitmentCriteria) -> str:
        """
        Build a plain-text search query from criteria.
        Uses AI-enhanced keywords when available, otherwise title + top skills.
        """
        parts = [criteria.title]
        if criteria.keywords:
            parts.extend(criteria.keywords[:4])
        else:
            parts.extend(criteria.required_skills[:3])
        return " ".join(parts)
