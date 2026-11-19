from datetime import datetime, timezone

from pymongo.database import Database


def upsert_google_user(db: Database, *, sub: str, email: str) -> None:
    db["users"].update_one(
        {"sub": sub},
        {
            "$set": {
                "email": email,
                "updated_at": datetime.now(timezone.utc),
            },
            "$setOnInsert": {"created_at": datetime.now(timezone.utc)},
        },
        upsert=True,
    )
