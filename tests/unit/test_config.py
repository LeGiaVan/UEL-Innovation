import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_use_the_poc_context(settings: Settings) -> None:
    assert settings.app_department_id == "bao_dam_chat_luong"
    assert settings.app_module_code == "khao_khi"
    assert settings.postgres_url.drivername == "postgresql+asyncpg"
    assert settings.qdrant_ready_url == "http://qdrant:6333/readyz"
    assert settings.minio_ready_url == "http://minio:9000/minio/health/ready"


def test_settings_fail_fast_when_secrets_and_dependencies_are_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    required_environment_variables = (
        "APP_API_KEY",
        "MINIO_ACCESS_KEY",
        "MINIO_SECRET_KEY",
        "MINIO_URL",
        "POSTGRES_HOST",
        "POSTGRES_PASSWORD",
        "QDRANT_URL",
    )
    for variable in required_environment_variables:
        monkeypatch.delenv(variable, raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
