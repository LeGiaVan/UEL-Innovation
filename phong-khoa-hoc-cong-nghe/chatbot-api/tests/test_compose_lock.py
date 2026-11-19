from pathlib import Path

STARTER = Path(__file__).resolve().parents[2]


def test_compose_locks_bge_m3() -> None:
    compose = (STARTER / "docker-compose.yml").read_text(encoding="utf-8")
    dockerfile = (STARTER / "Dockerfile").read_text(encoding="utf-8")
    env_example = (STARTER / ".env.example").read_text(encoding="utf-8")
    assert "EMBED_BACKEND: bge-m3" in compose
    assert "EMBED_BACKEND=bge-m3" in dockerfile
    assert "EMBED_BACKEND=bge-m3" in env_example
    assert 'pip install --no-cache-dir ".[embed]"' in dockerfile
    assert "BAAI/bge-m3" in dockerfile


def test_compose_prod_does_not_mount_app_or_publish_qdrant() -> None:
    prod = (STARTER / "docker-compose.prod.yml").read_text(encoding="utf-8")
    assert "./chatbot-api/app:/app/app" not in prod
    assert "6335:6333" not in prod
    assert "restart: unless-stopped" in prod
    assert "EMBED_BACKEND: bge-m3" in prod
