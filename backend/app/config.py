from functools import lru_cache
from urllib.parse import quote_plus
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "recruitment_platform"

    # Celery (MySQL-based, no Redis needed)
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""

    # Application
    APP_ENV: str = "development"
    SECRET_KEY: str = "change_this_secret"
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # Scraping
    LINKEDIN_SESSION_FILE: str = "linkedin_session.json"
    NAUKRI_SESSION_FILE: str = "naukri_session.json"
    INDEED_SESSION_FILE: str = "indeed_session.json"
    MAX_CANDIDATES_PER_PLATFORM: int = 50
    SCRAPE_ENRICH_LIMIT: int = 5        # profiles to visit for full data (lower = faster)
    SCRAPE_DELAY_MIN: float = 0.5       # seconds between requests
    SCRAPE_DELAY_MAX: float = 1.5

    # AI keyword enhancement (optional — leave blank to disable)
    GEMINI_API_KEY: str = ""

    # GitHub API token (optional but strongly recommended — raises limit from 60/hr to 5000/hr)
    # Generate at: github.com → Settings → Developer settings → Personal access tokens
    GITHUB_TOKEN: str = ""

    # Snov.io email finder (50 free credits/month)
    # Get from: app.snov.io → Profile Settings → API
    SNOV_USER_ID: str = ""
    SNOV_SECRET: str = ""

    # Gmail SMTP — for sending automated outreach emails
    # App Password: myaccount.google.com/apppasswords
    GMAIL_USER: str = ""
    GMAIL_APP_PASSWORD: str = ""
    GMAIL_SENDER_NAME: str = "Recruitment Team"

    @property
    def _encoded_password(self) -> str:
        return quote_plus(self.DB_PASSWORD)

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.DB_USER}:{self._encoded_password}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            f"?charset=utf8mb4"
        )

    @property
    def celery_broker(self) -> str:
        if self.CELERY_BROKER_URL:
            return self.CELERY_BROKER_URL
        return (
            f"sqla+mysql+pymysql://{self.DB_USER}:{self._encoded_password}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def celery_backend(self) -> str:
        if self.CELERY_RESULT_BACKEND:
            return self.CELERY_RESULT_BACKEND
        return (
            f"db+mysql+pymysql://{self.DB_USER}:{self._encoded_password}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
