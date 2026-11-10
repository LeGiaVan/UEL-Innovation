from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from app.core.config import Settings
from app.db.base import Base
from app.repositories.silver import PostgresSilverWriter


def _host_settings(database: str) -> Settings:
    return Settings(_env_file=".env", postgres_host="localhost", postgres_db=database)


@pytest.fixture(scope="session")
def silver_engine() -> Iterator[Engine]:
    try:
        admin_settings = _host_settings("uel_rag")
        admin = create_engine(admin_settings.postgres_sync_url, isolation_level="AUTOCOMMIT")
        with admin.connect() as connection:
            exists = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = 'uel_rag_test'")
            ).scalar()
            if not exists:
                connection.execute(text("CREATE DATABASE uel_rag_test"))
        admin.dispose()
    except OperationalError as exc:
        pytest.skip(f"PostgreSQL is not available on localhost: {exc}")

    test_settings = _host_settings("uel_rag_test")
    engine = create_engine(test_settings.postgres_sync_url, pool_pre_ping=True)
    config = Config(str(Path("alembic.ini")))
    config.set_main_option(
        "sqlalchemy.url",
        test_settings.postgres_sync_url.render_as_string(hide_password=False),
    )
    command.upgrade(config, "head")
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(silver_engine: Engine) -> Iterator[Session]:
    factory = sessionmaker(silver_engine)
    with factory() as session:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
        yield session
        session.rollback()


@pytest.fixture
def silver_writer(silver_engine: Engine) -> PostgresSilverWriter:
    return PostgresSilverWriter(silver_engine)
