import logging

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from app.core.config import Settings

log = logging.getLogger(__name__)


def ping_mongo(settings: Settings) -> bool:
    try:
        client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=1500)
        client.admin.command("ping")
        client.close()
        return True
    except PyMongoError as exc:
        log.warning("Mongo not ready: %s", exc)
        return False
