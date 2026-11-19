"""Nạp lại 5 Excel seed Khảo thí bằng embed đang khóa (BGE-M3 trên compose)."""

from __future__ import annotations

from pathlib import Path

from app.factory import create_app
from app.services.ingest_service import ingest_module

SEED_DIR = Path("/app/chatbot-data/modules/khao_khi/seed")
SEED_FILES = {
    1: "1. Thong tin Mo-dun - Khao khi.xlsx",
    2: "2. FAQ - Khao khi.xlsx",
    3: "3. Tai lieu nghiep vu - Khao khi.xlsx",
    4: "4. Moc thoi gian.xlsx",
    5: "5. Tai lieu gioi thieu.xlsx",
}


def main() -> None:
    app = create_app()
    settings = app.state.settings
    seed = Path(settings.chatbot_data_dir) / "modules" / "khao_khi" / "seed"
    if not seed.is_dir():
        seed = SEED_DIR
    files = {slot: (seed / name).read_bytes() for slot, name in SEED_FILES.items()}
    body = ingest_module(
        db=app.state.db,
        qdrant=app.state.qdrant,
        data_dir=Path(settings.chatbot_data_dir),
        department=app.state.department,
        module_code="khao_khi",
        files=files,
        filenames=SEED_FILES,
        embed_dim=settings.embed_dim,
        embed_backend=settings.embed_backend,
    )
    print(body)


if __name__ == "__main__":
    main()
