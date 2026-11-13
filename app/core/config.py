from functools import lru_cache
from typing import Literal, Self

from pydantic import AnyHttpUrl, BaseModel, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class ApiClient(BaseModel):
    id: str = Field(min_length=1)
    department_id: str = Field(pattern=r"^[a-z0-9_]+$")
    modules: list[str] = Field(min_length=1)
    api_key: SecretStr = Field(min_length=16)


class Settings(BaseSettings):
    """Validated runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "UEL RAG Chatbot PoC"
    app_env: Literal["development", "test", "uat"] = "development"
    app_api_key: SecretStr = Field(default=SecretStr(""))
    app_department_id: str = Field(
        default="bao_dam_chat_luong",
        pattern=r"^[a-z0-9_]+$",
    )
    app_module_code: str = Field(default="khao_khi", pattern=r"^[a-z0-9_]+$")
    departments_config_path: str = "configs/departments.yaml"
    app_admin_api_key: SecretStr = Field(default=SecretStr(""))
    api_clients: list[ApiClient] = Field(default_factory=list)

    cors_origins: list[str] = []
    chat_timeout_seconds: float = Field(default=90, gt=0, le=300)
    admin_timeout_seconds: float = Field(default=600, gt=0, le=1800)
    request_max_bytes: int = Field(default=16384, ge=1024, le=1048576)
    source_upload_max_bytes: int = Field(default=16777216, ge=1024, le=67108864)

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    request_id_header: str = "X-Request-ID"
    readiness_timeout_seconds: float = Field(default=3.0, gt=0, le=30)

    postgres_host: str = Field(min_length=1)
    postgres_port: int = Field(default=5432, ge=1, le=65535)
    postgres_db: str = Field(default="uel_rag", min_length=1)
    postgres_user: str = Field(default="uel", min_length=1)
    postgres_password: SecretStr = Field(min_length=8)

    qdrant_url: AnyHttpUrl
    qdrant_collection: str = Field(default="uel_knowledge", min_length=3)
    embedding_model: str = Field(default="BAAI/bge-m3")
    embedding_device: Literal["cpu"] = "cpu"
    embedding_batch_size: int = Field(default=2, ge=1, le=32)
    embedding_max_length: int = Field(default=512, ge=32, le=8192)
    gold_faq_score_boost: float = Field(default=0.12, ge=0, le=1)
    rag_top_k: int = Field(default=5, ge=1, le=20)
    rag_score_threshold: float = Field(default=0.4167, ge=0, le=10)
    rag_search_mode: Literal["hybrid", "dense"] = "hybrid"

    llm_provider: Literal["groq", "gemini", "fake"] = "fake"
    llm_model: str = Field(default="openai/gpt-oss-20b", min_length=1)
    llm_api_key: SecretStr = Field(default=SecretStr(""))
    llm_timeout_seconds: float = Field(default=45.0, gt=0, le=120)
    llm_max_retries: int = Field(default=1, ge=0, le=3)

    minio_url: AnyHttpUrl
    minio_access_key: SecretStr = Field(min_length=8)
    minio_secret_key: SecretStr = Field(min_length=8)
    minio_bucket_bronze: str = Field(default="bronze", min_length=3)
    minio_bucket_attachments: str = Field(default="attachments", min_length=3)

    @model_validator(mode="after")
    def validate_credentials(self) -> Self:
        if not self.api_clients and len(self.app_api_key.get_secret_value()) < 16:
            raise ValueError("Configure API_CLIENTS or an APP_API_KEY of at least 16 characters")
        if (
            self.app_env != "development"
            and self.app_admin_api_key.get_secret_value()
            and len(self.app_admin_api_key.get_secret_value()) < 16
        ):
            raise ValueError("Admin key must contain at least 16 characters")
        if len({c.id for c in self.api_clients}) != len(self.api_clients):
            raise ValueError("API client IDs must be unique")
        if len({c.api_key.get_secret_value() for c in self.api_clients}) != len(self.api_clients):
            raise ValueError("API keys must be unique")
        return self

    @property
    def postgres_url(self) -> URL:
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )

    @property
    def postgres_sync_url(self) -> URL:
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )

    @property
    def qdrant_ready_url(self) -> str:
        return f"{str(self.qdrant_url).rstrip('/')}/readyz"

    @property
    def minio_ready_url(self) -> str:
        return f"{str(self.minio_url).rstrip('/')}/minio/health/ready"


@lru_cache
def get_settings() -> Settings:
    return Settings()
