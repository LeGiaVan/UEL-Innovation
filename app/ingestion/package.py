"""Build and inspect a three-workbook Template 1/2/3 release package."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import yaml
from pydantic import BaseModel

from app.ingestion.enums import WorkbookRole
from app.ingestion.exceptions import SchemaDriftError
from app.ingestion.fingerprints import classify_workbook
from app.ingestion.manifest import ManifestCounts, ManifestFile, ReleaseManifest
from app.ingestion.models import CountSummary
from app.ingestion.validation import count_bundle
from app.ingestion.xlsx_adapter import XlsxSourceAdapter


class InspectedFile(BaseModel):
    name: str
    role: WorkbookRole
    file_sha256: str
    schema_sha256: str


class PackageInspect(BaseModel):
    files: list[InspectedFile]
    expected_counts: CountSummary
    manifest: dict[str, object]


def inspect_directory(
    directory: Path,
    *,
    department_id: str,
    department_name: str,
    module_code: str,
    module_name: str,
    release_id: str,
    release_status: str = "approved_for_dev",
) -> PackageInspect:
    xlsx = sorted(path for path in directory.glob("*.xlsx") if not path.name.startswith("~$"))
    if len(xlsx) != 3:
        raise SchemaDriftError("A release package must contain exactly three template workbooks.")
    identified: dict[str, InspectedFile] = {}
    for path in xlsx:
        role, file_digest, schema_digest = classify_workbook(path)
        if role in identified:
            raise SchemaDriftError(f"Duplicate template role {role} in package.")
        identified[role] = InspectedFile(
            name=path.name,
            role=role,
            file_sha256=file_digest,
            schema_sha256=schema_digest,
        )
    required = ("module_and_routing", "faq", "business_documents")
    missing = [role for role in required if role not in identified]
    if missing:
        raise SchemaDriftError(f"Package is missing template roles: {', '.join(missing)}")
    files = [identified[role] for role in required]
    manifest = ReleaseManifest(
        schema_version="1.0",
        release_id=release_id,
        created_at=datetime.now(UTC).date().isoformat(),
        department_id=department_id,
        department_name=department_name,
        module_code=module_code,
        module_name=module_name,
        source_type="xlsx",
        release_status=release_status,
        files=[
            ManifestFile(
                name=item.name,
                role=item.role,
                file_sha256=item.file_sha256,
                schema_sha256=item.schema_sha256,
            )
            for item in files
        ],
        expected_counts=ManifestCounts(
            routing_rules=0,
            faqs=0,
            documents=0,
            regulation_sections=0,
            condition_exception_sections=0,
            dossier_items=0,
            procedure_steps=0,
        ),
        allowed_environments=["development", "test"],
        prohibited_environments=["uat", "production"],
    )
    adapter = XlsxSourceAdapter()
    workbooks = adapter.identify(directory, manifest)
    bundle = adapter.extract(directory, manifest, workbooks)
    counts = count_bundle(bundle)
    payload = {
        "schema_version": manifest.schema_version,
        "release_id": manifest.release_id,
        "created_at": manifest.created_at,
        "department": {"id": department_id, "name": department_name},
        "module": {"code": module_code, "name": module_name},
        "source_type": "xlsx",
        "release_status": release_status,
        "files": [item.model_dump() for item in files],
        "expected_counts": counts.model_dump(),
        "allowed_environments": manifest.allowed_environments,
        "prohibited_environments": manifest.prohibited_environments,
    }
    return PackageInspect(files=files, expected_counts=counts, manifest=payload)


def write_manifest(directory: Path, payload: dict[str, object]) -> None:
    (directory / "release-manifest.yaml").write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
