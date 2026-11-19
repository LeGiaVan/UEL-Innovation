from datetime import datetime, timezone

from pymongo.database import Database


def create_session(
    db: Database, *, sid: str, sub: str, email: str, expires_at: datetime
) -> None:
    db["sessions"].insert_one(
        {
            "sid": sid,
            "sub": sub,
            "email": email,
            "expires_at": expires_at,
            "revoked": False,
            "created_at": datetime.now(timezone.utc),
        }
    )


def get_active_session(db: Database, sid: str) -> dict | None:
    doc = db["sessions"].find_one({"sid": sid})
    if not doc or doc.get("revoked"):
        return None
    exp = doc.get("expires_at")
    if exp is None:
        return None
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < datetime.now(timezone.utc):
        return None
    return doc


def revoke_session(db: Database, sid: str) -> None:
    db["sessions"].update_one(
        {"sid": sid},
        {"$set": {"revoked": True, "revoked_at": datetime.now(timezone.utc)}},
    )
