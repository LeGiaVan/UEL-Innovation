import pytest

from app.core.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        app_api_key="test-api-key-that-is-long-enough",
        app_env="test",
        minio_access_key="test-access-key",
        minio_secret_key="test-secret-key",
        minio_url="http://minio:9000",
        postgres_db="uel_rag_test",
        postgres_host="postgres",
        postgres_password="test-password",
        postgres_user="uel",
        qdrant_url="http://qdrant:6333",
        qdrant_collection="uel_knowledge_test",
        embedding_model="hash-test",
    )
