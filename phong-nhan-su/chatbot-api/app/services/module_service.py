from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from app.ingestion.normalize import nfc, nfc_lower, slug


class ModuleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=2, max_length=120)


def live_department(department: dict[str, Any] | None, db) -> dict[str, Any]:
    dept = dict(department or {})
    yaml_mods = [dict(m) for m in dept.get("modules") or []]
    seen = {str(m.get("code") or "") for m in yaml_mods if m.get("code")}
    if db is not None:
        for row in db["modules"].find({}):
            code = str(row.get("code") or "")
            name = nfc(row.get("name") or "")
            if not code or code in seen:
                continue
            yaml_mods.append(
                {
                    "code": code,
                    "name": name or code,
                    "profile": row.get("profile") or "generic",
                }
            )
            seen.add(code)
    dept["modules"] = yaml_mods
    return dept


def _code_from_name(name: str) -> str:
    return slug(name).replace("-", "_")


def load_department_yaml(path: Path | None) -> dict[str, Any]:
    resolved = resolve_department_yaml(path)
    if resolved is None or not resolved.is_file():
        return {}
    return yaml.safe_load(resolved.read_text(encoding="utf-8")) or {}


def resolve_department_yaml(path: Path | None) -> Path | None:
    if path is None:
        return None
    candidate = Path(path)
    if candidate.is_file():
        return candidate.resolve()
    bundled = Path(__file__).resolve().parents[2] / "configs" / "department.yaml"
    if bundled.is_file():
        return bundled
    return candidate


def _dump_yaml(payload: dict[str, Any]) -> str:
    return yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, default_flow_style=False)


def sync_department_yaml(yaml_path: Path | None, department: dict[str, Any], db) -> None:
    path = resolve_department_yaml(yaml_path)
    if path is None or not path.is_file() or db is None:
        return
    live = live_department(department, db)
    yaml_codes = {str(row.get("code") or "") for row in (department.get("modules") or []) if row.get("code")}
    live_codes = {str(row.get("code") or "") for row in (live.get("modules") or []) if row.get("code")}
    if yaml_codes != live_codes:
        _write_department_modules(path, live.get("modules") or [])


def _write_department_modules(yaml_path: Path, modules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    path = Path(yaml_path)
    if not path.is_file():
        raise ValueError(f"Không tìm thấy {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    slim: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in modules:
        code = str(row.get("code") or "")
        if not code or code in seen:
            continue
        seen.add(code)
        slim.append(
            {
                "code": code,
                "name": row.get("name") or code,
                "profile": row.get("profile") or "generic",
            }
        )
    data["modules"] = slim
    path.write_text(_dump_yaml(data), encoding="utf-8")
    (path.parent / "modules.yaml").write_text(_dump_yaml({"modules": slim}), encoding="utf-8")
    return slim


def _write_module_folder(data_dir: Path, *, code: str, name: str) -> str:
    dest = Path(data_dir) / "modules" / code
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "releases").mkdir(exist_ok=True)
    meta = dest / "module.yaml"
    payload = {"code": code, "name": name, "profile": "generic"}
    meta.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    templates = Path(data_dir) / "templates"
    if templates.is_dir():
        for src in templates.glob("*.xlsx"):
            target = dest / src.name
            if not target.exists():
                shutil.copy2(src, target)
    return str(Path("modules") / code)


def add_module(
    db,
    department: dict[str, Any],
    *,
    name: str,
    email: str,
    data_dir: Path | None = None,
    yaml_path: Path | None = None,
) -> dict[str, str]:
    title = nfc(name)
    if not title:
        raise ValueError("Nhập tên mảng hỗ trợ")
    code = _code_from_name(title)
    live = live_department(department, db)
    for mod in live.get("modules") or []:
        if mod.get("code") == code or nfc_lower(mod.get("name")) == nfc_lower(title):
            raise ValueError(f"Đã có mảng hỗ trợ «{mod.get('name') or code}»")
    if len(live.get("modules") or []) >= 20:
        raise ValueError("Tối đa 20 mảng hỗ trợ")
    if db is None:
        raise ValueError("MongoDB chưa sẵn sàng")
    doc = {
        "code": code,
        "name": title,
        "profile": "generic",
        "created_at": datetime.now(timezone.utc),
        "created_by": email,
    }
    db["modules"].insert_one(doc)
    folder = ""
    if data_dir is not None:
        folder = _write_module_folder(Path(data_dir), code=code, name=title)
    yaml_file = resolve_department_yaml(yaml_path)
    yaml_rel = ""
    if yaml_file is not None:
        _write_department_modules(yaml_file, live_department(department, db).get("modules") or [])
        try:
            yaml_rel = str(yaml_file.relative_to(Path(__file__).resolve().parents[2]))
        except ValueError:
            yaml_rel = str(yaml_file)
    return {"code": code, "name": title, "folder": folder, "yaml": yaml_rel}
