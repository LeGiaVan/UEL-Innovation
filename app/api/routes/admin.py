"""Administrative configuration and Bronze → Silver → Gold ingestion."""

from __future__ import annotations

import base64
import binascii
import hashlib
import os
import secrets
import tempfile
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

import portalocker
import yaml
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

from app.gold.indexer import GoldIndexer
from app.ingestion.contact import ContactConfig
from app.ingestion.exceptions import IngestionError, SchemaDriftError
from app.ingestion.manifest import (
    DepartmentConfig,
    DepartmentModuleConfig,
    load_department_configs,
    resolve_module,
)
from app.ingestion.models import SyncOutcome
from app.ingestion.package import inspect_directory, write_manifest
from app.ingestion.pipeline import SyncRequest, run_sync

router = APIRouter(prefix="/v1/admin", tags=["administration"])
_ADMIN_KEY = APIKeyHeader(name="X-Admin-Key", auto_error=False)


async def admin_auth(request: Request, x_admin_key: str = Security(_ADMIN_KEY)) -> None:
    expected = request.app.state.settings.app_admin_api_key.get_secret_value()
    provided = x_admin_key or ""
    if len(expected) < 16 or not secrets.compare_digest(provided.encode(), expected.encode()):
        raise HTTPException(401, "Invalid admin credential")


class Registry(BaseModel):
    schema_version: str = "1.0"
    departments: list[DepartmentConfig]


class SyncBody(BaseModel):
    department_id: str = Field(pattern=r"^[a-z0-9_]+$")
    module_code: str = Field(pattern=r"^[a-z0-9_]+$")
    dry_run: bool = True


class SourcePackage(SyncBody):
    files: dict[str, str] = Field(
        description="Filename to base64 bytes; three template XLSX plus optional manifest"
    )


class InspectBody(BaseModel):
    department_id: str = Field(default="preview", pattern=r"^[a-z0-9_]+$")
    department_name: str = "Preview"
    module_code: str = Field(default="preview", pattern=r"^[a-z0-9_]+$")
    module_name: str = "Preview"
    release_id: str = Field(default="preview", pattern=r"^[a-z0-9][a-z0-9._-]{1,127}$")
    files: dict[str, str]


class ReleaseIngest(BaseModel):
    department_id: str = Field(pattern=r"^[a-z0-9_]+$")
    department_name: str
    audience: str = "nguoi_hoc"
    module_code: str = Field(pattern=r"^[a-z0-9_]+$")
    module_name: str
    profile: Literal["generic", "assessment"] = "generic"
    source_path: str | None = None
    release_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{1,127}$")
    contact: ContactConfig = Field(default_factory=ContactConfig)
    files: dict[str, str]
    dry_run: bool = True


class TenantModuleStatus(BaseModel):
    department_id: str
    department_name: str
    module_code: str
    module_name: str
    profile: str
    enabled: bool
    source_path: str
    source_present: bool
    last_release_id: str | None = None
    last_sync_status: str | None = None


def config_path(request: Request) -> Path:
    return Path(request.app.state.settings.departments_config_path).resolve()


def revision(path: Path) -> str:
    return hashlib.sha256(path.read_bytes() if path.exists() else b"").hexdigest()


def source_path(config: Path, source: str) -> Path:
    root = config.parent.parent.resolve()
    target = (root / source).resolve()
    if not target.is_relative_to(root / "data") or target == root / "data":
        raise HTTPException(422, "source_path must be a module directory under data/")
    return target


def _decode_files(files: dict[str, str], *, allow_manifest: bool) -> dict[str, bytes]:
    decoded: dict[str, bytes] = {}
    for name, encoded in files.items():
        allowed = name.endswith(".xlsx") or (allow_manifest and name == "release-manifest.yaml")
        if Path(name).name != name or "\\" in name or ":" in name or not allowed:
            raise HTTPException(422, "Invalid source filename")
        try:
            decoded[name] = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error):
            raise HTTPException(422, "Invalid base64") from None
    return decoded


def _write_package(target: Path, decoded: dict[str, bytes]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + "." + uuid4().hex + ".upload")
    temporary.mkdir()
    try:
        for name, data in decoded.items():
            (temporary / name).write_bytes(data)
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            for item in temporary.iterdir():
                item.unlink()
            temporary.rmdir()


def _gold_indexer(request: Request) -> GoldIndexer:
    cached = getattr(request.app.state, "gold_indexer", None)
    if isinstance(cached, GoldIndexer):
        return cached
    runtime = getattr(request.app.state, "agent_runtime", None)
    retriever = getattr(getattr(runtime, "deps", None), "retriever", None)
    if isinstance(retriever, GoldIndexer):
        request.app.state.gold_indexer = retriever
        return retriever
    indexer = GoldIndexer.from_settings(request.app.state.settings)
    request.app.state.gold_indexer = indexer
    return indexer


def _run_sync(
    request: Request, department_id: str, module_code: str, *, dry_run: bool
) -> SyncOutcome:
    path = config_path(request)
    _, module = resolve_module(load_department_configs(path), department_id, module_code)
    settings = request.app.state.settings
    from app.ingestion.bronze import MinioBronzeStore
    from app.repositories.silver import PostgresSilverWriter

    return run_sync(
        SyncRequest(
            department_id=department_id,
            module_code=module_code,
            source_type=module.source_type,
            source_path=source_path(path, module.source_path),
            config_path=path,
            output_dir=path.parent.parent / "reports" / "validation",
            dry_run=dry_run,
            environment=settings.app_env,
            bronze_store=None
            if dry_run
            else MinioBronzeStore(
                settings.minio_url,
                settings.minio_access_key,
                settings.minio_secret_key,
                settings.minio_bucket_bronze,
            ),
            silver_writer=None if dry_run else PostgresSilverWriter.from_settings(settings),
            gold_indexer=None if dry_run else _gold_indexer(request),
            persist_gold=not dry_run,
            gold_output_dir=path.parent.parent / "reports" / "gold",
        )
    )


def _upsert_registry(
    path: Path,
    *,
    department_id: str,
    department_name: str,
    audience: str,
    module: DepartmentModuleConfig,
    contact: ContactConfig,
) -> None:
    departments = load_department_configs(path) if path.exists() else []
    current = next((item for item in departments if item.id == department_id), None)
    if current is None:
        departments.append(
            DepartmentConfig(
                id=department_id,
                name=department_name,
                audience=audience,
                contact=contact,
                modules=[module],
            )
        )
    else:
        current.name = department_name
        current.audience = audience
        current.contact = contact
        existing = next((item for item in current.modules if item.code == module.code), None)
        if existing is None:
            current.modules.append(module)
        else:
            existing.name = module.name
            existing.source_type = module.source_type
            existing.source_path = module.source_path
            existing.profile = module.profile
            existing.contact = module.contact
            existing.enabled = True
    if path.exists():
        history = path.parent / ".registry-history"
        history.mkdir(exist_ok=True)
        (history / (revision(path) + ".yaml")).write_bytes(path.read_bytes())
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    try:
        temporary.write_text(
            yaml.safe_dump(
                {
                    "schema_version": "1.0",
                    "departments": [item.model_dump() for item in departments],
                },
                allow_unicode=True,
            ),
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _report_status(report: dict[str, Any] | None) -> str | None:
    if not report:
        return None
    gold = report.get("gold")
    if isinstance(gold, dict) and gold.get("status"):
        return str(gold["status"])
    silver = report.get("silver")
    if isinstance(silver, dict) and silver.get("status"):
        return str(silver["status"])
    if report.get("blocked"):
        return "blocked"
    if report.get("dry_run"):
        return "validated"
    return None


def _latest_report(root: Path, department_id: str, module_code: str) -> dict[str, Any] | None:
    folder = root / department_id / module_code
    if not folder.is_dir():
        return None
    reports = sorted(folder.glob("*/validation.json"), key=lambda item: item.stat().st_mtime)
    if not reports:
        return None
    payload = yaml.safe_load(reports[-1].read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    return payload


@router.get("/registry", dependencies=[Depends(admin_auth)])
def registry(request: Request, response: Response) -> Registry:
    path = config_path(request)
    with portalocker.Lock(str(path) + ".lock", timeout=10):
        departments = load_department_configs(path)
        response.headers["ETag"] = revision(path)
    return Registry(departments=departments)


@router.put("/registry", dependencies=[Depends(admin_auth)])
def replace_registry(
    body: Registry, request: Request, response: Response, if_match: str = Header()
) -> Registry:
    path = config_path(request)
    if body.schema_version != "1.0":
        raise HTTPException(422, "Unsupported registry schema")
    ids = [d.id for d in body.departments]
    sources = []
    if len(set(ids)) != len(ids):
        raise HTTPException(422, "Duplicate tenant IDs")
    for department in body.departments:
        codes = [m.code for m in department.modules]
        if len(set(codes)) != len(codes):
            raise HTTPException(422, "Duplicate module codes")
        for module in department.modules:
            sources.append(source_path(path, module.source_path))
    if len(set(sources)) != len(sources):
        raise HTTPException(422, "Each module must have its own source directory")
    path.parent.mkdir(parents=True, exist_ok=True)
    with portalocker.Lock(str(path) + ".lock", timeout=10):
        if if_match != revision(path):
            raise HTTPException(409, "Configuration changed; reload before updating")
        if path.exists():
            history = path.parent / ".registry-history"
            history.mkdir(exist_ok=True)
            (history / (revision(path) + ".yaml")).write_bytes(path.read_bytes())
        temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
        try:
            temporary.write_text(
                yaml.safe_dump(body.model_dump(), allow_unicode=True), encoding="utf-8"
            )
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        response.headers["ETag"] = revision(path)
    return body


@router.get("/registry/revisions/{version}", dependencies=[Depends(admin_auth)])
def registry_revision(version: str, request: Request) -> Registry:
    if len(version) != 64 or any(c not in "0123456789abcdef" for c in version):
        raise HTTPException(422, "Invalid revision")
    path = config_path(request).parent / ".registry-history" / (version + ".yaml")
    if not path.is_file():
        raise HTTPException(404, "Unknown revision")
    return Registry.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


@router.get("/tenants", dependencies=[Depends(admin_auth)])
def tenants(request: Request) -> list[TenantModuleStatus]:
    path = config_path(request)
    reports_root = path.parent.parent / "reports" / "validation"
    with portalocker.Lock(str(path) + ".lock", timeout=10):
        departments = load_department_configs(path)
    rows: list[TenantModuleStatus] = []
    for department in departments:
        for module in department.modules:
            report = _latest_report(reports_root, department.id, module.code)
            try:
                present = source_path(path, module.source_path).exists()
            except HTTPException:
                present = False
            rows.append(
                TenantModuleStatus(
                    department_id=department.id,
                    department_name=department.name,
                    module_code=module.code,
                    module_name=module.name,
                    profile=module.profile,
                    enabled=module.enabled,
                    source_path=module.source_path,
                    source_present=present,
                    last_release_id=(
                        None if report is None else (str(report.get("release_id") or "") or None)
                    ),
                    last_sync_status=_report_status(report),
                )
            )
    return rows


@router.get(
    "/reports/{department_id}/{module_code}",
    dependencies=[Depends(admin_auth)],
)
def latest_report(department_id: str, module_code: str, request: Request) -> dict[str, Any]:
    path = config_path(request)
    report = _latest_report(
        path.parent.parent / "reports" / "validation", department_id, module_code
    )
    if report is None:
        raise HTTPException(404, "No validation report for this module")
    return report


@router.post("/packages/inspect", dependencies=[Depends(admin_auth)])
def inspect_package(body: InspectBody) -> dict[str, Any]:
    decoded = _decode_files(body.files, allow_manifest=False)
    if len(decoded) != 3:
        raise HTTPException(422, "Send exactly three template XLSX files")
    with tempfile.TemporaryDirectory() as folder:
        directory = Path(folder)
        for name, data in decoded.items():
            (directory / name).write_bytes(data)
        try:
            result = inspect_directory(
                directory,
                department_id=body.department_id,
                department_name=body.department_name,
                module_code=body.module_code,
                module_name=body.module_name,
                release_id=body.release_id,
            )
        except (IngestionError, SchemaDriftError) as exc:
            raise HTTPException(422, str(exc)) from None
    return result.model_dump(mode="json")


@router.post("/sources", dependencies=[Depends(admin_auth)])
def upload_source(body: SourcePackage, request: Request) -> dict[str, str | int]:
    path = config_path(request)
    with portalocker.Lock(str(path) + ".lock", timeout=10):
        try:
            _, module = resolve_module(
                load_department_configs(path), body.department_id, body.module_code
            )
        except IngestionError:
            raise HTTPException(422, "Unknown module") from None
        target = source_path(path, module.source_path)
        if target.exists():
            raise HTTPException(
                409, "Release directory already exists; configure a new release directory"
            )
        decoded = _decode_files(body.files, allow_manifest=True)
        if "release-manifest.yaml" not in decoded:
            raise HTTPException(422, "Release manifest required")
        _write_package(target, decoded)
    return {
        "status": "uploaded",
        "files": len(decoded),
        "next": "POST /v1/admin/sync (dry_run=true) then dry_run=false",
    }


@router.post("/sync", dependencies=[Depends(admin_auth)], response_model=SyncOutcome)
def sync(body: SyncBody, request: Request) -> SyncOutcome:
    path = config_path(request)
    with portalocker.Lock(str(path) + ".lock", timeout=10):
        try:
            resolve_module(load_department_configs(path), body.department_id, body.module_code)
        except IngestionError:
            raise HTTPException(422, "Unknown module") from None
    try:
        return _run_sync(request, body.department_id, body.module_code, dry_run=body.dry_run)
    except IngestionError:
        raise HTTPException(
            422, "Source/configuration validation failed; check release package"
        ) from None


@router.post("/releases", dependencies=[Depends(admin_auth)])
def ingest_release(body: ReleaseIngest, request: Request) -> dict[str, Any]:
    """Register a tenant/module if needed, store the three templates, then ETL to Qdrant.

    dry_run=true validates only. dry_run=false writes Bronze, Silver and Gold.
    """
    path = config_path(request)
    relative = body.source_path or (
        f"data/{body.department_id}/{body.module_code}/{body.release_id}"
    )
    decoded = _decode_files(body.files, allow_manifest=True)
    xlsx = {name: data for name, data in decoded.items() if name.endswith(".xlsx")}
    if len(xlsx) != 3:
        raise HTTPException(422, "Send exactly three template XLSX files")
    with tempfile.TemporaryDirectory() as folder:
        directory = Path(folder)
        for name, data in xlsx.items():
            (directory / name).write_bytes(data)
        try:
            inspected = inspect_directory(
                directory,
                department_id=body.department_id,
                department_name=body.department_name,
                module_code=body.module_code,
                module_name=body.module_name,
                release_id=body.release_id,
            )
        except (IngestionError, SchemaDriftError) as exc:
            raise HTTPException(422, str(exc)) from None
        manifest_bytes = decoded.get("release-manifest.yaml")
        if manifest_bytes is None:
            write_manifest(directory, inspected.manifest)
            manifest_bytes = (directory / "release-manifest.yaml").read_bytes()
        package = {**xlsx, "release-manifest.yaml": manifest_bytes}
    module = DepartmentModuleConfig(
        code=body.module_code,
        name=body.module_name,
        source_type="xlsx",
        source_path=relative,
        profile=body.profile,
        contact=body.contact,
    )
    with portalocker.Lock(str(path) + ".lock", timeout=10):
        target = source_path(path, relative)
        if target.exists():
            raise HTTPException(
                409, "Release directory already exists; use a new source_path/release_id"
            )
        _upsert_registry(
            path,
            department_id=body.department_id,
            department_name=body.department_name,
            audience=body.audience,
            module=module,
            contact=body.contact,
        )
        _write_package(target, package)
    if body.dry_run:
        try:
            outcome = _run_sync(request, body.department_id, body.module_code, dry_run=True)
        except IngestionError:
            raise HTTPException(422, "Package stored but validation failed") from None
        return {
            "status": outcome.status,
            "source_path": relative,
            "manifest": inspected.manifest,
            "sync": outcome.model_dump(mode="json"),
            "next": "POST /v1/admin/sync with dry_run=false to write Bronze/Silver/Qdrant",
        }
    try:
        outcome = _run_sync(request, body.department_id, body.module_code, dry_run=False)
    except IngestionError:
        raise HTTPException(422, "Package stored but ETL failed") from None
    return {
        "status": outcome.status,
        "source_path": relative,
        "manifest": inspected.manifest,
        "sync": outcome.model_dump(mode="json"),
    }
