from pathlib import Path

import yaml
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import Settings, settings as default_settings
from app.core.logging import setup_logging
from app.db.mongodb import ping_mongo


def load_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or default_settings
    setup_logging()
    department = load_yaml(settings.department_yaml)
    department_id = settings.department_id or department.get("id") or "starter"

    app = FastAPI(title=f"UEL chatbot ({department_id})", version="0.1.0")
    app.state.settings = settings
    app.state.department = department
    app.state.department_id = department_id
    app.state.mongo_ok = ping_mongo(settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type"],
    )
    app.include_router(api_router)

    dist = settings.ui_dist_dir
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="ui")

    return app
