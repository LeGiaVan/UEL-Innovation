from fastapi import APIRouter

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("")
def list_conversations() -> dict:
    return {"conversations": []}
