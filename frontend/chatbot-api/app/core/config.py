from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="CHATBOT_", extra="ignore"
    )
    environment: Literal["development", "production", "test"] = "development"
    auth_disabled: bool = False
    database_backend: Literal["mongodb", "sqlite"] = "mongodb"
    database_path: Path = Path("data/chatbot.sqlite3")
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = "uel_chatbot"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    allowed_origins: list[str] = [
        f"http://{host}:{port}"
        for host in ("localhost", "127.0.0.1")
        for port in range(5170, 5180)
    ]
    allowed_hosts: list[str] = ["localhost", "127.0.0.1", "testserver", "api"]
    session_ttl_seconds: int = Field(3600, ge=60, le=86400)
    login_limit: int = Field(10, ge=1, le=100)
    chat_limit: int = Field(30, ge=1, le=1000)
    max_body_bytes: int = Field(16384, ge=4096, le=1048576)
    provider: Literal["stub", "rag"] = "stub"
    rag_base_url: str = "http://127.0.0.1:8000"
    rag_api_key: str = ""
    rag_timeout_seconds: float = Field(90, gt=1, le=300)

    @model_validator(mode="after")
    def validate_origins(self):
        if self.environment == "production" and self.auth_disabled:
            raise ValueError(
                "Anonymous development access cannot be enabled in production"
            )
        if "*" in self.allowed_origins or "*" in self.allowed_hosts:
            raise ValueError("Use explicit allowed origins and hosts")
        if self.environment == "production" and any(
            not value.startswith("https://") for value in self.allowed_origins
        ):
            raise ValueError("Production origins must use HTTPS")
        if not self.mongodb_database.strip():
            raise ValueError("MongoDB database name cannot be empty")
        return self
