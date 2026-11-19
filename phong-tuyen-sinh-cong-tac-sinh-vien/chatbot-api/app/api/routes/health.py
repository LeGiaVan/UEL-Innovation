from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/health/live")
@router.get("/api/health/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
@router.get("/api/health/ready")
def ready(request: Request) -> dict[str, str | bool]:
    mongo_ok = bool(getattr(request.app.state, "mongo_ok", False))
    qdrant_ok = bool(getattr(request.app.state, "qdrant_ok", False))
    ok = mongo_ok and qdrant_ok
    return {"status": "ok" if ok else "degraded", "mongo": mongo_ok, "qdrant": qdrant_ok}
