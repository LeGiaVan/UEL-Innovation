from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.workbook import Workbook

from app.ingestion.enums import SKIP_DOCUMENT_SHEETS, WorkbookRole
from app.ingestion.exceptions import SchemaDriftError
from app.ingestion.manifest import ReleaseManifest
from app.ingestion.models import IdentifiedWorkbook
from app.ingestion.normalize import sha256_bytes, sha256_file

DOCUMENT_SHEET_PATTERN = re.compile(r"^Tài liệu \d+$")
MODULE_DATA_SHEET = "1. Phạm vi trả lời"
FAQ_DATA_SHEET = "1. FAQ"
DOCUMENT_SCHEMA_SHEET = "Tài liệu 1"


class SchemaExtractionError(SchemaDriftError):
    """Workbook is missing the sheets required to compute a schema fingerprint."""


def canonical_schema_json(schema: Mapping[str, Any]) -> str:
    return json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def schema_fingerprint(schema: Mapping[str, Any]) -> str:
    return sha256_bytes(canonical_schema_json(schema).encode("utf-8"))


def _sheet(workbook: Workbook, name: str) -> Any:
    if name not in workbook.sheetnames:
        raise SchemaExtractionError(f"Missing sheet required for schema fingerprint: {name}")
    return workbook[name]


def extract_module_schema(workbook: Workbook) -> dict[str, Any]:
    worksheet = _sheet(workbook, MODULE_DATA_SHEET)
    return {
        "type": "module",
        "sheets": list(workbook.sheetnames),
        "metadata_labels": [worksheet.cell(row, 2).value for row in range(4, 7)],
        "headers": [worksheet.cell(9, column).value for column in range(1, 8)],
    }


def extract_faq_schema(workbook: Workbook) -> dict[str, Any]:
    worksheet = _sheet(workbook, FAQ_DATA_SHEET)
    return {
        "type": "faq",
        "sheets": list(workbook.sheetnames),
        "headers": [worksheet.cell(4, column).value for column in range(2, 12)],
    }


def extract_documents_schema(workbook: Workbook) -> dict[str, Any]:
    worksheet = _sheet(workbook, DOCUMENT_SCHEMA_SHEET)
    return {
        "type": "documents",
        "sheets": list(workbook.sheetnames),
        "section_markers": [worksheet.cell(row, 1).value for row in (3, 8, 21, 34, 45, 58)],
        "regulation_headers": [worksheet.cell(9, column).value for column in range(1, 7)],
        "condition_headers": [worksheet.cell(22, column).value for column in range(1, 6)],
        "procedure_labels": [worksheet.cell(row, 2).value for row in range(35, 44)],
        "dossier_headers": [worksheet.cell(46, column).value for column in range(1, 6)],
        "step_headers": [worksheet.cell(59, column).value for column in range(1, 7)],
    }


ROLE_SCHEMA_EXTRACTORS: dict[WorkbookRole, Callable[[Workbook], dict[str, Any]]] = {
    "module_and_routing": extract_module_schema,
    "faq": extract_faq_schema,
    "business_documents": extract_documents_schema,
}


def identify_workbook(path: Path, manifest: ReleaseManifest) -> IdentifiedWorkbook:
    workbook = load_workbook(path, data_only=False, read_only=False)
    expected = manifest.schema_by_digest()
    matches: list[tuple[WorkbookRole, str]] = []
    drift: list[tuple[WorkbookRole, str]] = []

    for role, extractor in ROLE_SCHEMA_EXTRACTORS.items():
        try:
            digest = schema_fingerprint(extractor(workbook))
        except SchemaExtractionError:
            continue
        if expected.get(digest) == role:
            matches.append((role, digest))
        else:
            drift.append((role, digest))

    file_digest = sha256_file(path)
    if len(matches) == 1:
        role, digest = matches[0]
        expected_file = manifest.file_for_role(role)
        return IdentifiedWorkbook(
            path=str(path),
            name=path.name,
            role=role,
            file_sha256=file_digest,
            schema_sha256=digest,
            expected_file_sha256=expected_file.file_sha256,
            expected_schema_sha256=expected_file.schema_sha256,
            checksum_ok=file_digest == expected_file.file_sha256,
            schema_ok=True,
        )

    if drift:
        role, digest = drift[0]
        expected_file = manifest.file_for_role(role)
        return IdentifiedWorkbook(
            path=str(path),
            name=path.name,
            role=role,
            file_sha256=file_digest,
            schema_sha256=digest,
            expected_file_sha256=expected_file.file_sha256,
            expected_schema_sha256=expected_file.schema_sha256,
            checksum_ok=file_digest == expected_file.file_sha256,
            schema_ok=False,
        )

    raise SchemaDriftError(f"Unable to identify workbook by schema fingerprint: {path.name}")


def is_document_data_sheet(name: str) -> bool:
    return bool(DOCUMENT_SHEET_PATTERN.fullmatch(name)) and name not in SKIP_DOCUMENT_SHEETS
