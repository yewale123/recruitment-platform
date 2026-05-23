from app.connectors.base import BasePlatformConnector, RecruitmentCriteria, RawCandidate
from app.connectors.linkedin import LinkedInConnector
from app.connectors.github import GitHubConnector

CONNECTOR_REGISTRY: dict[str, type[BasePlatformConnector]] = {
    "linkedin": LinkedInConnector,
    "github": GitHubConnector,
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
