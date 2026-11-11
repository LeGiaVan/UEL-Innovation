"""Measure normalized exact FAQ lookup against active rows in the PoC tenant."""

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.agent.knowledge import SilverFaqStore
from app.core.config import Settings
from app.ingestion.normalize import normalize_question
from app.models.tables import Department, Faq, Module
from app.repositories.silver import create_sync_engine


def main():
    settings = Settings()
    settings.postgres_host = "127.0.0.1"
    engine = create_sync_engine(settings)
    factory = sessionmaker(engine, expire_on_commit=False)
    with Session(engine) as session:
        rows = session.execute(
            select(Faq.question_code, Faq.question)
            .join(Department, Faq.department_id == Department.id)
            .join(Module, Faq.module_id == Module.id)
            .where(
                Department.code == settings.app_department_id,
                Module.code == settings.app_module_code,
                Faq.is_active.is_(True),
                Faq.release_status.in_(["approved_for_dev", "approved_for_uat"]),
            )
        ).all()
    store = SilverFaqStore(factory)
    misses = []
    for code, question in rows:
        hit = store.match_normalized(
            department_id=settings.app_department_id,
            module_code=settings.app_module_code,
            normalized_question=normalize_question(question),
            environment="development",
        )
        if not hit or hit.question_code != code:
            misses.append(code)
    result = {
        "total": len(rows),
        "misses": misses,
        "rate": (len(rows) - len(misses)) / len(rows) if rows else None,
    }
    Path("reports/phases/phase-08-faq-match.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result))
    engine.dispose()


if __name__ == "__main__":
    main()
