from fastapi import APIRouter

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/me")
def me() -> dict:
    """P1 sẽ trả JWT session. P0: chưa đăng nhập."""
    return {"authenticated": False}


@router.post("/google")
def google_login() -> dict:
    return {"detail": "Google ID token verification is scheduled for P1"}


@router.post("/logout")
def logout() -> dict:
    return {"ok": True}
