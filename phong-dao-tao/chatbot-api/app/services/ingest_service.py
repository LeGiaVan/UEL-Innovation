from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.retrieval import FAQ_RETRIEVE_BOOST, FAQ_SOURCE
from app.ingestion.pipeline import parse_and_validate
from app.integrations.embeddings import embed_texts
from app.integrations.qdrant import COL_DOCS, COL_RULES, point_id
from app.repositories import catalog

log = logging.getLogger(__name__)

_EXCEL_SLOT = re.compile(r"(?i)^(?:template|templalet)?[\s_\-]*([1-5])(?:\D|$)")


class IngestError(Exception):
    def __init__(self, status: int, detail: Any) -> None:
        super().__init__(str(detail))
        self.status = status
        self.detail = detail


def _module_name(department: dict, module_code: str) -> str | None:
    for mod in department.get("modules") or []:
        if mod.get("code") == module_code:
            return str(mod.get("name") or "")
    return None


def _checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _bundle_counts(bundle) -> dict[str, int]:
    file03_sheets = {str(d.get("sheet") or "") for d in bundle.business_docs if d.get("sheet")}
    file05_articles = {
        str(c.get("title") or c.get("sheet") or "")
        for c in bundle.intro_chunks
        if c.get("kind") == "intro_summary"
    }
    return {
        "rules": len(bundle.file01.topics),
        "faqs": len(bundle.faqs),
        "milestones": len(bundle.milestones),
        "file03_sheets": len(file03_sheets),
        "file05_articles": len(file05_articles),
    }


def check_module(*, department: dict, module_code: str, files: dict[int, bytes]) -> dict[str, Any]:
    missing = [f"file_0{i}" for i in range(1, 6) if i not in files or not files[i]]
    if missing:
        raise IngestError(422, {"errors": [f"Thiếu {', '.join(missing)} — cần đủ 5 file"], "warnings": [], "issues": []})
    name = _module_name(department, module_code)
    if not name:
        raise IngestError(
            422,
            {
                "errors": [f"Chưa có mảng hỗ trợ «{module_code}». Thêm mảng trên giao diện trước khi cập nhật dữ liệu."],
                "warnings": [],
                "issues": [],
            },
        )
    bundle = parse_and_validate(files, module_code=module_code, module_name=name)
    return {
        "ok": bundle.issues.ok,
        "module_code": module_code,
        "module_name": name,
        **bundle.issues.payload(),
        "counts": _bundle_counts(bundle),
        "choices": {
            key: sorted(bundle.ds.get(key) or [])
            for key in ("audience", "channel", "kind", "scope")
        },
    }


def ingest_module(
    *,
    db,
    qdrant,
    data_dir: Path,
    department: dict,
    module_code: str,
    files: dict[int, bytes],
    filenames: dict[int, str],
    embed_dim: int = 1024,
    embed_backend: str = "hash",
    on_progress=None,
) -> dict[str, Any]:
    if db is None:
        raise IngestError(503, "MongoDB chưa sẵn sàng")
    if qdrant is None:
        raise IngestError(503, "Qdrant chưa sẵn sàng")
    missing = [f"file_0{i}" for i in range(1, 6) if i not in files or not files[i]]
    if missing:
        raise IngestError(422, {"errors": [f"Thiếu {', '.join(missing)} — cần đủ 5 file"], "warnings": []})

    name = _module_name(department, module_code)
    if not name:
        raise IngestError(422, {"errors": [f"Chưa có mảng hỗ trợ «{module_code}». Thêm mảng trên giao diện trước khi cập nhật dữ liệu."], "warnings": []})

    def note(step: str, pct: int, message: str, **extra: Any) -> None:
        if on_progress:
            on_progress({"type": "progress", "step": step, "pct": min(100, max(0, pct)), "message": message, **extra})

    previous = catalog.get_active_release(db, module_code)
    note("parse", 8, "Đang đọc và đối chiếu 5 file Excel…")
    bundle = parse_and_validate(files, module_code=module_code, module_name=name)
    if not bundle.issues.ok:
        raise IngestError(
            422,
            {
                **bundle.issues.payload(),
                "module_code": module_code,
                "ok": False,
                "choices": {
                    key: sorted(bundle.ds.get(key) or [])
                    for key in ("audience", "channel", "kind", "scope")
                },
            },
        )

    note("store", 18, "File hợp lệ. Đang lưu vào kho dữ liệu…")
    release_id = datetime.now(timezone.utc).strftime("r%Y%m%dT%H%M%S") + "-" + uuid4().hex[:6]
    dest = Path(data_dir) / "modules" / module_code / "releases" / release_id / "source"
    dest.mkdir(parents=True, exist_ok=True)
    checksums = {}
    for idx, blob in files.items():
        fname = filenames.get(idx) or f"{idx}.xlsx"
        (dest / fname).write_bytes(blob)
        checksums[str(idx)] = _checksum(blob)

    now = datetime.now(timezone.utc)
    catalog.save_release_meta(
        db,
        {
            "module_code": module_code,
            "release_id": release_id,
            "active": False,
            "checksums": checksums,
            "warnings": bundle.issues.warnings,
            "created_at": now,
            "header": {
                "module_name": bundle.file01.module_name,
                "department_name": bundle.file01.department_name,
                "module_description": bundle.file01.module_description,
                "default_contact_name": bundle.file01.default_contact_name,
                "default_contact_info": bundle.file01.default_contact_info,
            },
        },
    )
    rules = []
    for row in bundle.file01.topics:
        rules.append(
            {
                **row,
                "module_code": module_code,
                "release_id": release_id,
            }
        )
    faqs = [{**row, "module_code": module_code, "release_id": release_id} for row in bundle.faqs]
    milestones = [{**row, "module_code": module_code, "release_id": release_id} for row in bundle.milestones]
    catalog.insert_many(db, "routing_rules", rules)
    catalog.insert_many(db, "faqs", faqs)
    catalog.insert_many(db, "milestones", milestones)

    qdrant.ensure_collections(embed_dim)
    note("embed_rules", 28, f"Đang gắn {len(rules)} chủ đề vào bot…")
    rule_points = []
    rule_texts = []
    for row in rules:
        text = "\n".join([row["topic"], row["bot_behavior"], row["scope"], row["audience"]])
        rule_texts.append(text)
        rule_points.append(
            {
                "id": point_id(release_id, row["rule_id"]),
                "module_code": module_code,
                "release_id": release_id,
                "rule_id": row["rule_id"],
                "source": "rules",
                "topic": row.get("topic") or "",
                "scope": row.get("scope") or "",
                "scope_code": row.get("scope_code") or "",
                "bot_behavior": row.get("bot_behavior") or "",
                "audience": row.get("audience") or "",
                "contact_name": row.get("contact_name") or "",
                "contact_info": row.get("contact_info") or "",
                "channel": row.get("channel") or "",
                "text": text,
            }
        )
    def on_rules(done: int, total: int) -> None:
        span = 22
        pct = 28 + int(span * done / max(total, 1))
        note("embed_rules", pct, f"Gắn chủ đề {done}/{total}", done=done, total=total)

    for point, vector in zip(
        rule_points,
        embed_texts(rule_texts, dim=embed_dim, backend=embed_backend, on_batch=on_rules),
        strict=True,
    ):
        point["vector"] = vector
    qdrant.upsert(COL_RULES, rule_points)

    doc_points = []
    doc_texts = []
    for chunk in bundle.business_chunks:
        text = chunk["text"]
        doc_texts.append(text)
        doc_points.append(
            {
                "id": point_id(release_id, "business", chunk.get("sheet", ""), chunk.get("kind", ""), text),
                "module_code": module_code,
                "release_id": release_id,
                "source": "business",
                **{k: v for k, v in chunk.items() if k != "text"},
                "text": text,
            }
        )
    for ms in milestones:
        text = f"{ms['name']}\n{ms['group']}\n{ms['full_text']}\n{ms['academic_term']}"
        doc_texts.append(text)
        doc_points.append(
            {
                "id": point_id(release_id, "milestone", ms["milestone_id"]),
                "module_code": module_code,
                "release_id": release_id,
                "source": "milestone",
                "milestone_id": ms["milestone_id"],
                "text": text,
            }
        )
    for chunk in bundle.intro_chunks:
        text = chunk["text"]
        doc_texts.append(text)
        doc_points.append(
            {
                "id": point_id(release_id, "intro", chunk.get("sheet", ""), chunk.get("kind", ""), text),
                "module_code": module_code,
                "release_id": release_id,
                "source": "intro",
                **{k: v for k, v in chunk.items() if k != "text"},
                "text": text,
            }
        )
    for faq in faqs:
        text = f"{faq['question']}\n{faq['answer']}"
        doc_texts.append(text)
        doc_points.append(
            {
                "id": point_id(release_id, FAQ_SOURCE, faq["question_code"]),
                "module_code": module_code,
                "release_id": release_id,
                "source": FAQ_SOURCE,
                "retrieve_boost": FAQ_RETRIEVE_BOOST,
                "question_code": faq["question_code"],
                "section": faq.get("section") or "",
                "question": faq["question"],
                "answer": faq["answer"],
                "text": text,
            }
        )
    note("embed_docs", 52, f"Đang gắn {len(doc_points)} đoạn FAQ / tài liệu / mốc thời gian…")

    def on_docs(done: int, total: int) -> None:
        span = 40
        pct = 52 + int(span * done / max(total, 1))
        note("embed_docs", pct, f"Gắn tri thức {done}/{total}", done=done, total=total)

    for point, vector in zip(
        doc_points,
        embed_texts(doc_texts, dim=embed_dim, backend=embed_backend, on_batch=on_docs),
        strict=True,
    ):
        point["vector"] = vector
    qdrant.upsert(COL_DOCS, doc_points)

    note("activate", 96, "Đang đưa bản mới vào sử dụng…")
    catalog.activate_release(db, module_code=module_code, release_id=release_id)
    if previous:
        old = previous.get("release_id")
        if old and old != release_id:
            qdrant.delete_release(COL_RULES, module_code=module_code, release_id=old)
            qdrant.delete_release(COL_DOCS, module_code=module_code, release_id=old)

    file03_sheets = sorted({str(d.get("sheet") or "") for d in bundle.business_docs if d.get("sheet")})
    file05_articles = sorted(
        {
            str(c.get("title") or c.get("sheet") or "")
            for c in bundle.intro_chunks
            if c.get("kind") == "intro_summary"
        }
    )
    files_out = [
        {"index": idx, "filename": filenames.get(idx) or f"{idx}.xlsx", "checksum": checksums.get(str(idx), "")}
        for idx in range(1, 6)
        if idx in files
    ]
    return {
        "module_code": module_code,
        "release_id": release_id,
        "warnings": bundle.issues.warnings,
        "issues": bundle.issues.as_dicts(),
        "checksums": checksums,
        "files": files_out,
        "counts": {
            "rules": len(rules),
            "faqs": len(faqs),
            "milestones": len(milestones),
            "docs": len(doc_points),
            "file03_sheets": len(file03_sheets),
            "file05_articles": len(file05_articles),
        },
    }


def excel_slot(filename: str) -> int | None:
    match = _EXCEL_SLOT.match(Path(filename).name.strip())
    return int(match.group(1)) if match else None


def _complete_pack(files: dict[int, bytes]) -> bool:
    return all(bool(files.get(i)) for i in range(1, 6))


def load_release_files(source_dir: Path) -> tuple[dict[int, bytes], dict[int, str]]:
    files: dict[int, bytes] = {}
    names: dict[int, str] = {}
    if not source_dir.is_dir():
        return files, names
    for path in source_dir.iterdir():
        if path.suffix.lower() not in {".xlsx", ".xlsm"}:
            continue
        if path.stat().st_size <= 0:
            continue
        idx = excel_slot(path.name)
        if not idx:
            continue
        blob = path.read_bytes()
        if not blob:
            continue
        files[idx] = blob
        names[idx] = path.name
    return files, names


def _latest_source_dir(module_dir: Path) -> Path | None:
    releases = module_dir / "releases"
    found: list[Path] = []
    if releases.is_dir():
        for path in releases.iterdir():
            source = path / "source"
            files, _ = load_release_files(source)
            if _complete_pack(files):
                found.append(source)
    if found:
        return max(found, key=lambda path: path.parent.name)
    seed = module_dir / "seed"
    files, _ = load_release_files(seed)
    if _complete_pack(files):
        return seed
    return None


def recover_missing_releases(
    *,
    db,
    qdrant,
    data_dir: Path,
    department: dict,
    embed_dim: int = 1024,
    embed_backend: str = "hash",
) -> list[dict[str, Any]]:
    """Nạp lại Excel đã lưu trên đĩa nếu Mongo không còn release đang chạy."""
    root = Path(data_dir) / "modules"
    if db is None or qdrant is None or not root.is_dir():
        return []
    known = {str(mod.get("code") or "") for mod in (department.get("modules") or []) if mod.get("code")}
    recovered: list[dict[str, Any]] = []
    for module_dir in sorted(root.iterdir()):
        if not module_dir.is_dir() or module_dir.name.startswith("."):
            continue
        code = module_dir.name
        if known and code not in known:
            continue
        if catalog.get_active_release(db, code):
            continue
        source = _latest_source_dir(module_dir)
        if source is None:
            continue
        files, names = load_release_files(source)
        if not _complete_pack(files):
            log.warning("recover skip %s: found slots %s in %s", code, sorted(files), source)
            continue
        log.info("recover ingest %s from %s", code, source)
        try:
            recovered.append(
                ingest_module(
                    db=db,
                    qdrant=qdrant,
                    data_dir=Path(data_dir),
                    department=department,
                    module_code=code,
                    files=files,
                    filenames=names,
                    embed_dim=embed_dim,
                    embed_backend=embed_backend,
                )
            )
        except Exception:
            log.exception("recover ingest failed for %s", code)
    return recovered
