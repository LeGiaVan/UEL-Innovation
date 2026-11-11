from app.core.config import Settings
from app.db.database import Database
from app.db.mongodb import MongoDatabase


def create_database(settings: Settings):
    if settings.database_backend == "sqlite":
        return Database(settings.database_path)
    return MongoDatabase(settings.mongodb_uri, settings.mongodb_database)
