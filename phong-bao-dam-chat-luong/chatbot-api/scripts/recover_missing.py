"""Nạp lại Excel trên đĩa khi Mongo thiếu release đang chạy."""
from __future__ import annotations

import logging

from app.core.config import settings
from app.db.mongodb import connect_mongo, get_db
from app.integrations.qdrant import connect_qdrant
from app.services.ingest_service import recover_missing_releases
from app.services.module_service import live_department, load_department_yaml

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    department = load_department_yaml(settings.department_yaml)
    mongo = connect_mongo(settings)
    db = get_db(mongo, settings)
    qdrant = connect_qdrant(settings.qdrant_url, dim=settings.embed_dim)
    recovered = recover_missing_releases(
        db=db,
        qdrant=qdrant,
        data_dir=settings.chatbot_data_dir,
        department=live_department(department, db),
        embed_dim=settings.embed_dim,
        embed_backend=settings.embed_backend,
    )
    if not recovered:
        print("recover: nothing to load")
        return
    for row in recovered:
        print(
            f"recover: {row.get('module_code')} {row.get('release_id')} "
            f"faqs={row.get('counts', {}).get('faqs')} rules={row.get('counts', {}).get('rules')}",
            flush=True,
        )


if __name__ == "__main__":
    main()
