from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    department_id: str = "starter"
    jwt_secret: str = "change-me"
    google_client_id: str = ""
    llm_api_key: str = ""
    mongo_uri: str = "mongodb://127.0.0.1:27017"
    mongo_db: str = "uel_chatbot"
    qdrant_url: str = "http://127.0.0.1:6333"
    ui_dist_dir: Path = Path("../chatbot-web/dist")
    department_yaml: Path = Path("./configs/department.yaml")
    persona_yaml: Path = Path("./configs/persona.yaml")
    jwt_ttl_hours: int = Field(8, ge=1, le=24)


settings = Settings()
