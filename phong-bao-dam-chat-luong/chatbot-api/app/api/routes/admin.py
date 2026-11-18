from fastapi import APIRouter

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/status")
def admin_status() -> dict:
    return {"ingest": "P3/P5", "persona": "P5"}
