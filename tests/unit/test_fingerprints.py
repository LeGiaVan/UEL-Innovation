from pathlib import Path

from openpyxl import load_workbook

from app.ingestion.fingerprints import (
    extract_documents_schema,
    extract_faq_schema,
    extract_module_schema,
    identify_workbook,
    schema_fingerprint,
)
from app.ingestion.manifest import load_release_manifest
from app.ingestion.normalize import sha256_file

POC_DIR = Path("data/P.BDCL")


def test_schema_fingerprints_match_locked_poc_baseline() -> None:
    manifest = load_release_manifest(POC_DIR / "release-manifest.yaml")
    extractors = {
        "module_and_routing": extract_module_schema,
        "faq": extract_faq_schema,
        "business_documents": extract_documents_schema,
    }
    for item in manifest.files:
        path = POC_DIR / item.name
        workbook = load_workbook(path, data_only=False)
        assert sha256_file(path) == item.file_sha256
        assert schema_fingerprint(extractors[item.role](workbook)) == item.schema_sha256


def test_identify_workbook_by_fingerprint_not_filename(tmp_path: Path) -> None:
    source = POC_DIR / "2. FAQ - Câu hỏi thường gặp.xlsx"
    renamed = tmp_path / "renamed-faq.xlsx"
    renamed.write_bytes(source.read_bytes())
    manifest = load_release_manifest(POC_DIR / "release-manifest.yaml")
    identified = identify_workbook(renamed, manifest)
    assert identified.role == "faq"
    assert identified.schema_ok
    assert identified.checksum_ok
    assert identified.name == "renamed-faq.xlsx"
