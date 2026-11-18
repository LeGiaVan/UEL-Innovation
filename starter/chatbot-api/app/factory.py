import threading
from pathlib import Path

import yaml
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import Settings, settings as default_settings
from app.core.logging import setup_logging
from app.db.mongodb import connect_mongo, get_db
from app.integrations.qdrant import connect_qdrant
from app.services.module_service import load_department_yaml, sync_department_yaml
from app.services.persona_service import runtime_persona


def load_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or default_settings
    setup_logging()
    department = load_yaml(settings.department_yaml)
    department_id = settings.department_id or department.get("id") or "starter"
    mongo_client = connect_mongo(settings)

    app = FastAPI(title=f"UEL chatbot ({department_id})", version="0.1.0")
    app.state.settings = settings
    app.state.db = get_db(mongo_client, settings)
    if app.state.db is not None:
        try:
            sync_department_yaml(settings.department_yaml, department, app.state.db)
            department = load_department_yaml(settings.department_yaml) or department
        except Exception:  # noqa: BLE001
            pass
    app.state.department = department
    app.state.persona = runtime_persona(db=app.state.db, yaml_data=load_yaml(settings.persona_yaml))
    app.state.department_id = department_id
    app.state.mongo_client = mongo_client
    app.state.mongo_ok = mongo_client is not None
    qdrant = connect_qdrant(settings.qdrant_url, dim=settings.embed_dim)
    app.state.qdrant = qdrant
    app.state.qdrant_ok = qdrant is not None

    def _warmup() -> None:
        from app.integrations.embeddings import warmup_embedder

        warmup_embedder(settings.embed_backend, dim=settings.embed_dim)

    threading.Thread(target=_warmup, daemon=True, name="embed-warmup").start()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
        expose_headers=["Retry-After"],
    )
    app.include_router(api_router)

    dist = settings.ui_dist_dir
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="ui")

    return app
