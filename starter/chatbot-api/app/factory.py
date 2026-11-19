import logging
import threading
from pathlib import Path

import yaml
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import Settings, settings as default_settings
from app.core.logging import setup_logging
from app.core.middleware import OriginGuardMiddleware
from app.core.origins import allowed_origins
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

    docs_enabled = bool(settings.docs_enabled)
    app = FastAPI(
        title=f"UEL chatbot ({department_id})",
        version="0.1.0",
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )
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

    def _warmup_and_recover() -> None:
        from app.integrations.embeddings import warmup_embedder
        from app.services.ingest_service import recover_missing_releases
        from app.services.module_service import live_department

        warmup_embedder(settings.embed_backend, dim=settings.embed_dim)
        try:
            recovered = recover_missing_releases(
                db=app.state.db,
                qdrant=getattr(app.state, "qdrant", None),
                data_dir=settings.chatbot_data_dir,
                department=live_department(app.state.department, app.state.db),
                embed_dim=settings.embed_dim,
                embed_backend=settings.embed_backend,
            )
            if recovered:
                codes = ", ".join(row.get("module_code") or "?" for row in recovered)
                print(f"recover: loaded {codes}", flush=True)
        except Exception:  # noqa: BLE001
            logging.getLogger(__name__).exception("recover missing releases failed")

    threading.Thread(target=_warmup_and_recover, daemon=True, name="embed-warmup").start()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins(settings, department),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
        expose_headers=["Retry-After"],
    )
    app.add_middleware(OriginGuardMiddleware, fastapi_app=app)
    app.include_router(api_router)

    if not docs_enabled:
        async def docs_off() -> JSONResponse:
            return JSONResponse({"detail": "Not Found"}, status_code=404)

        for path in ("/docs", "/redoc", "/openapi.json"):
            app.add_api_route(path, docs_off, methods=["GET", "HEAD"], include_in_schema=False)

    dist = settings.ui_dist_dir
    if dist.is_dir():
        assets = dist / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")
        index_file = dist / "index.html"

        @app.get("/{full_path:path}")
        async def spa_fallback(full_path: str):
            root = dist.resolve()
            target = (dist / full_path).resolve()
            try:
                target.relative_to(root)
            except ValueError:
                return FileResponse(index_file) if index_file.is_file() else {"detail": "not found"}
            if target.is_file():
                return FileResponse(target)
            if index_file.is_file():
                return FileResponse(index_file)
            return {"detail": "UI chưa build"}

    return app
