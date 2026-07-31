"""Application configuration via environment variables (Pydantic Settings)."""

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration loaded from .env / environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "ShopSphere"
    app_env: str = "development"
    debug: bool = True
    secret_key: str = "dev-secret-key-change-in-production-min-32-chars"
    api_v1_prefix: str = "/api/v1"
    host: str = "0.0.0.0"
    port: int = 8908
    base_url: str = "http://localhost:8908"

    # Database
    database_url: str = "sqlite+aiosqlite:///./shopsphere.db"
    database_url_sync: str = "sqlite:///./shopsphere.db"

    # Redis / Cache
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = 300

    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # JWT
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    algorithm: str = "HS256"

    # SMTP
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "noreply@shopsphere.local"
    smtp_from_name: str = "ShopSphere"
    smtp_tls: bool = True

    # Stripe
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""

    # Razorpay
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""

    default_payment_provider: str = "stripe"

    # Uploads
    upload_dir: str = "uploads"
    max_upload_size_mb: int = 5

    # CORS
    cors_origins: List[str] = Field(
        default_factory=lambda: ["http://localhost:8908", "http://127.0.0.1:8908"]
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors(cls, v):
        if isinstance(v, str):
            import json

            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [i.strip() for i in v.split(",") if i.strip()]
        return v

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
