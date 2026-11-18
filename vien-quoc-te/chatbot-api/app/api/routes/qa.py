from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["qa"])


@router.get("/qa")
def list_qa() -> list:
    """FAQ gợi ý sidebar. P3 mới lấy từ File 02."""
    return []
