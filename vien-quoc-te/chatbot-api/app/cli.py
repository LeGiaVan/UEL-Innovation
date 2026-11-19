"""Nạp 5 Excel 3.0 từ thư mục (không cần Google admin). UI upload làm ở P5."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

import yaml

from app.core.config import settings
from app.db.mongodb import connect_mongo, get_db
from app.integrations.qdrant import connect_qdrant
from app.services.ingest_service import IngestError, ingest_module


def _slot_files(folder: Path) -> tuple[dict[int, bytes], dict[int, str]]:
    blobs: dict[int, bytes] = {}
    names: dict[int, str] = {}
    for path in folder.glob("*.xlsx"):
        match = re.search(r"(\d+)\.", path.name)
        if not match:
            continue
        slot = int(match.group(1))
        if slot in blobs:
            raise SystemExit(f"Trùng file {slot}: {names[slot]} và {path.name}")
        blobs[slot] = path.read_bytes()
        names[slot] = path.name
    missing = [f"file_0{i}" for i in range(1, 6) if i not in blobs]
    if missing:
        raise SystemExit(f"Thiếu {', '.join(missing)} trong {folder}")
    return blobs, names


RELEASE_COLLECTIONS = ("routing_rules", "faqs", "milestones", "releases")


def cmd_purge(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir or settings.chatbot_data_dir)
    modules_dir = data_dir / "modules"
    removed = []
    if modules_dir.is_dir():
        for rel in modules_dir.glob("*/releases"):
            shutil.rmtree(rel)
            removed.append(str(rel))
    mongo = connect_mongo(settings)
    db = get_db(mongo, settings)
    if db is None:
        print(json.dumps({"errors": ["MongoDB chưa sẵn sàng"]}, ensure_ascii=False, indent=2))
        return 1
    mongo_n = {name: db[name].delete_many({}).deleted_count for name in RELEASE_COLLECTIONS}
    qdrant = connect_qdrant(settings.qdrant_url, dim=settings.embed_dim)
    if qdrant is None:
        print(json.dumps({"errors": ["Qdrant chưa sẵn sàng"]}, ensure_ascii=False, indent=2))
        return 1
    qdrant.wipe()
    print(
        json.dumps(
            {"disk_removed": removed, "mongo_deleted": mongo_n, "qdrant": "wiped rules+docs"},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    folder = Path(args.dir).resolve()
    files, names = _slot_files(folder)
    yaml_path = Path(args.department_yaml or settings.department_yaml)
    department = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    mongo = connect_mongo(settings)
    db = get_db(mongo, settings)
    qdrant = connect_qdrant(settings.qdrant_url, dim=settings.embed_dim)
    try:
        result = ingest_module(
            db=db,
            qdrant=qdrant,
            data_dir=Path(args.data_dir or settings.chatbot_data_dir),
            department=department,
            module_code=args.module,
            files=files,
            filenames=names,
            embed_dim=settings.embed_dim,
            embed_backend=settings.embed_backend,
        )
    except IngestError as exc:
        print(json.dumps(exc.detail if not isinstance(exc.detail, str) else {"errors": [exc.detail]}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="UEL chatbot CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)
    ing = sub.add_parser("ingest", help="Nạp đủ 5 Excel / một module_code")
    ing.add_argument("--module", required=True, help="module_code trong department.yaml")
    ing.add_argument("--dir", required=True, help="Thư mục chứa 5 file .xlsx")
    ing.add_argument("--data-dir", default="")
    ing.add_argument("--department-yaml", default="")
    pur = sub.add_parser("purge-releases", help="Xóa mọi release trên disk + Mongo + Qdrant")
    pur.add_argument("--data-dir", default="")
    args = parser.parse_args(argv)
    if args.cmd == "ingest":
        return cmd_ingest(args)
    if args.cmd == "purge-releases":
        return cmd_purge(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
