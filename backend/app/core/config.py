"""
Central application configuration.

All runtime configuration is sourced from environment variables (see .env.example).
Nothing here should ever contain a real secret - defaults are safe only for local
development against the docker-compose stack.
"""
from functools import lru_cache
from typing import List, Literal

from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- General ---
    PROJECT_NAME: str = "Repurpose AI"
    ENVIRONMENT: Literal["development", "testing", "staging", "production"] = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    APP_VERSION: str = "1.0.0"

    # --- Database ---
    DATABASE_URL: str = "postgresql+psycopg://repurpose:repurpose@localhost:5432/repurpose_ai"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_ECHO: bool = False

    # --- Redis / Celery ---
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    # Dev/test-only: run Celery tasks synchronously in-process when no broker is
    # available. Never set this in a real deployment (docker-compose leaves it unset).
    CELERY_TASK_ALWAYS_EAGER: bool = False

    # --- Auth / JWT ---
    JWT_SECRET: str = "CHANGE_ME_DEV_ONLY_SECRET_KEY_32BYTES_MIN"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_EXPIRE_DAYS: int = 7

    # --- CORS ---
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    @property
    def cors_origins_list(self) -> List[str]:
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    # --- Storage ---
    STORAGE_TYPE: Literal["local", "s3"] = "local"
    LOCAL_STORAGE_PATH: str = "./uploads"
    S3_ENDPOINT: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_BUCKET: str = "repurpose-ai-datasets"
    S3_REGION: str = "us-east-1"
    S3_USE_SSL: bool = True

    # --- Uploads ---
    MAX_UPLOAD_SIZE: int = 52_428_800  # 50 MB
    ALLOWED_UPLOAD_EXTENSIONS: str = "csv,json,xlsx,xls,fasta,fa,fastq,fq,tsv"

    @property
    def allowed_upload_extensions_list(self) -> List[str]:
        return [ext.strip().lower() for ext in self.ALLOWED_UPLOAD_EXTENSIONS.split(",") if ext.strip()]

    # --- Rate limiting ---
    RATE_LIMIT_PER_MINUTE: int = 120

    # --- Caching ---
    CACHE_DEFAULT_TTL_SECONDS: int = 300
    CACHE_DASHBOARD_TTL_SECONDS: int = 60
    CACHE_REFERENCE_DATA_TTL_SECONDS: int = 3600

    # --- Logging ---
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = False

    # --- Pagination ---
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 200

    # --- ML / AI ---
    ML_MODEL_VERSION: str = "1.0.0"
    ML_MODEL_DIR: str = "./models"
    ML_RANDOM_STATE: int = 42

    # --- First superuser (used by scripts/create_admin.py defaults) ---
    FIRST_SUPERUSER_EMAIL: str = "admin@repurpose.ai"
    FIRST_SUPERUSER_PASSWORD: str = "ChangeMe123!"
    FIRST_SUPERUSER_NAME: str = "Platform Admin"

    @field_validator("JWT_SECRET")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        if len(v) < 16:
            raise ValueError("JWT_SECRET must be at least 16 characters long")
        return v

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
