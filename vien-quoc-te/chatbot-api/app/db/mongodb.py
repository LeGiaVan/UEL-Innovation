from __future__ import annotations

import logging

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.core.config import Settings

log = logging.getLogger(__name__)


def connect_mongo(settings: Settings) -> MongoClient | None:
    uri = (settings.mongo_uri or "").strip()
    if not uri or uri.lower() in {"disabled", "none", "off"}:
        return None
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        db = client[settings.mongo_db]
        db["sessions"].create_index("sid", unique=True)
        db["users"].create_index("sub", unique=True)
        db["rate_windows"].create_index([("sub", 1), ("kind", 1)], unique=True)
        db["token_daily"].create_index([("sub", 1), ("day", 1)], unique=True)
        db["releases"].create_index([("module_code", 1), ("release_id", 1)], unique=True)
        db["routing_rules"].create_index([("module_code", 1), ("release_id", 1), ("rule_id", 1)])
        db["faqs"].create_index([("module_code", 1), ("release_id", 1), ("question_code", 1)])
        db["milestones"].create_index([("module_code", 1), ("release_id", 1), ("milestone_id", 1)])
        db["conversations"].create_index([("sub", 1), ("updated_at", -1)])
        db["conversations"].create_index("id", unique=True)
        db["messages"].create_index([("conversation_id", 1), ("created_at", 1)])
        db["chat_turns"].create_index("id", unique=True)
        db["chat_turns"].create_index([("conversation_id", 1), ("turn_index", 1)])
        db["chat_turns"].create_index([("created_at", -1)])
        db["chat_turns"].create_index([("module_code", 1), ("created_at", -1)])
        db["chat_turns"].create_index([("sub", 1), ("created_at", -1)])
        db["chat_turns"].create_index([("status", 1), ("created_at", -1)])
        return client
    except PyMongoError as exc:
        log.warning("Mongo not ready: %s", exc)
        return None


def ping_mongo(settings: Settings) -> bool:
    return connect_mongo(settings) is not None


def get_db(client: MongoClient | None, settings: Settings) -> Database | None:
    if client is None:
        return None
    return client[settings.mongo_db]
