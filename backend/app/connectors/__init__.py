from app.connectors.base import BasePlatformConnector, RecruitmentCriteria, RawCandidate
from app.connectors.linkedin import LinkedInConnector
from app.connectors.naukri import NaukriConnector
from app.connectors.indeed import IndeedConnector

CONNECTOR_REGISTRY: dict[str, type[BasePlatformConnector]] = {
    "linkedin": LinkedInConnector,
    "naukri": NaukriConnector,
    "indeed": IndeedConnector,
}


def get_connector(platform: str) -> BasePlatformConnector:
    cls = CONNECTOR_REGISTRY.get(platform.lower())
    if not cls:
        raise ValueError(f"Unknown platform: '{platform}'. Available: {list(CONNECTOR_REGISTRY)}")
    return cls()


__all__ = [
    "BasePlatformConnector",
    "RecruitmentCriteria",
    "RawCandidate",
    "get_connector",
    "CONNECTOR_REGISTRY",
]
