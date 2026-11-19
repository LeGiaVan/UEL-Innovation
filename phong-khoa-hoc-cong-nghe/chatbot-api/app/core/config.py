from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_API_DIR = Path(__file__).resolve().parents[2]
_STARTER_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_STARTER_DIR / ".env", _API_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    department_id: str = "starter"
    jwt_secret: str = "change-me"
    google_client_id: str = ""
    llm_api_key: str = ""
    llm_provider: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 45
    llm_max_retries: int = 1
    embed_backend: str = "hash"
    mongo_uri: str = "mongodb://127.0.0.1:27017"
    mongo_db: str = "uel_chatbot"
    qdrant_url: str = "http://127.0.0.1:6335"
    ui_dist_dir: Path = Path("../chatbot-web/dist")
    chatbot_data_dir: Path = _STARTER_DIR / "chatbot-data"
    department_yaml: Path = _API_DIR / "configs" / "department.yaml"
    persona_yaml: Path = _API_DIR / "configs" / "persona.yaml"
    embed_dim: int = 1024
    jwt_ttl_hours: int = Field(8, ge=1, le=24)
    cookie_secure: bool = False
    cors_origins: str = ""
    docs_enabled: bool = False


settings = Settings()
