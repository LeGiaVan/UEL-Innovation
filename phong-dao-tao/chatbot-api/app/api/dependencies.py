from fastapi import Request

from app.core.config import settings


def department_id(request: Request) -> str:
    """Không lấy mã phòng từ client."""
    return getattr(request.app.state, "department_id", settings.department_id)
