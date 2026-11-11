from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from app.gold.indexer import GoldIndexer
from app.ingestion.adapter import get_adapter
from app.ingestion.bronze import BronzeStore, NullBronzeStore, upload_bronze_snapshot
from app.ingestion.enums import SourceType
from app.ingestion.exceptions import IngestionError, ManifestError
from app.ingestion.manifest import (
    ReleaseManifest,
    load_department_configs,
    load_release_manifest,
    resolve_module,
)
from app.ingestion.models import (
    CountSummary,
    GoldSummary,
    SilverSummary,
    SyncOutcome,
    ValidationIssue,
    ValidationReport,
)
from app.ingestion.report import write_json_report, write_markdown_report
from app.ingestion.validation import validate_bundle
from app.repositories.silver import SilverWriter


@dataclass(frozen=True)
class SyncRequest:
    department_id: str
    module_code: str
    source_type: SourceType
    source_path: Path
    config_path: Path
    output_dir: Path
    dry_run: bool = True
    environment: str = "development"
    bronze_store: BronzeStore | None = None
    persist_silver: bool = True
    silver_writer: SilverWriter | None = None
    persist_gold: bool = False
    gold_indexer: GoldIndexer | None = None
    gold_output_dir: Path = Path("reports/gold")


def _blocked_report(
    manifest: ReleaseManifest,
    *,
    dry_run: bool,
    reason: str,
    extra_issues: list[ValidationIssue],
) -> ValidationReport:
    return ValidationReport(
        generated_at=datetime.now(UTC),
        release_id=manifest.release_id,
        department_id=manifest.department_id,
        module_code=manifest.module_code,
        dry_run=dry_run,
        publish_allowed=False,
        blocked=True,
        blocked_reason=reason,
        counts=CountSummary(
            routing_rules=0,
            faqs=0,
            documents=0,
            regulation_sections=0,
            condition_exception_sections=0,
            dossier_items=0,
            procedure_steps=0,
        ),
        expected_counts=CountSummary.model_validate(manifest.expected_counts.model_dump()),
        error_count=sum(1 for item in extra_issues if item.severity == "error"),
        warning_count=sum(1 for item in extra_issues if item.severity == "warning"),
        info_count=sum(1 for item in extra_issues if item.severity == "info"),
        issues=extra_issues,
        policy_findings=[],
    )


def _write_reports(report: ValidationReport, output_dir: Path) -> tuple[Path, Path]:
    json_path = write_json_report(report, output_dir / "validation.json")
    markdown_path = write_markdown_report(report, output_dir / "validation.md")
    return json_path, markdown_path


def run_sync(request: SyncRequest) -> SyncOutcome:
    configs = load_department_configs(request.config_path)
    department, module = resolve_module(configs, request.department_id, request.module_code)
    source_path = request.source_path.resolve()
    if not source_path.exists():
        raise ManifestError(f"Source path not found: {source_path}")
    manifest = load_release_manifest(source_path / "release-manifest.yaml")

    if (
        manifest.department_id != request.department_id
        or manifest.module_code != request.module_code
    ):
        raise ManifestError("Release manifest department/module does not match CLI arguments.")
    if department.name != manifest.department_name or department.id != manifest.department_id:
        raise ManifestError("Department config does not match release manifest.")
    if module.name != manifest.module_name:
        raise ManifestError("Module config does not match release manifest.")
    if request.environment in manifest.prohibited_environments:
        raise ManifestError(
            f"Release {manifest.release_id} is not allowed in environment {request.environment}."
        )
    if manifest.allowed_environments and request.environment not in manifest.allowed_environments:
        raise ManifestError(
            f"Release {manifest.release_id} is not allowed in environment {request.environment}."
        )
    adapter = get_adapter(request.source_type)
    workbooks = adapter.identify(source_path, manifest)
    output_dir = request.output_dir / department.id / module.code / manifest.release_id
    found_roles = {item.role for item in workbooks}
    missing_roles = [
        role
        for role in ("module_and_routing", "faq", "business_documents")
        if role not in found_roles
    ]
    if missing_roles:
        issues = [
            ValidationIssue(
                severity="error",
                code="MISSING_WORKBOOK",
                message=f"Không nhận diện được workbook cho role {role} bằng schema fingerprint.",
            )
            for role in missing_roles
        ]
        report = _blocked_report(
            manifest,
            dry_run=request.dry_run,
            reason="missing_workbook",
            extra_issues=issues,
        )
        json_path, markdown_path = _write_reports(report, output_dir)
        return SyncOutcome(
            status="blocked",
            report=report,
            report_json_path=str(json_path),
            report_markdown_path=str(markdown_path),
        )

    schema_failures = [item for item in workbooks if not item.schema_ok]
    checksum_failures = [item for item in workbooks if not item.checksum_ok]
    if schema_failures:
        issues = [
            ValidationIssue(
                severity="error",
                code="SCHEMA_DRIFT",
                message=(
                    f"Schema fingerprint mismatch for {item.name}: "
                    f"{item.schema_sha256} != {item.expected_schema_sha256}"
                ),
                source_file=item.name,
            )
            for item in schema_failures
        ]
        report = _blocked_report(
            manifest,
            dry_run=request.dry_run,
            reason="schema_drift",
            extra_issues=issues,
        )
        json_path, markdown_path = _write_reports(report, output_dir)
        return SyncOutcome(
            status="blocked",
            report=report,
            report_json_path=str(json_path),
            report_markdown_path=str(markdown_path),
        )

    if checksum_failures:
        issues = [
            ValidationIssue(
                severity="error",
                code="CHECKSUM_MISMATCH",
                message=(
                    f"File checksum mismatch for {item.name}: "
                    f"{item.file_sha256} != {item.expected_file_sha256}"
                ),
                source_file=item.name,
            )
            for item in checksum_failures
        ]
        report = _blocked_report(
            manifest,
            dry_run=request.dry_run,
            reason="checksum_mismatch",
            extra_issues=issues,
        )
        json_path, markdown_path = _write_reports(report, output_dir)
        return SyncOutcome(
            status="blocked",
            report=report,
            report_json_path=str(json_path),
            report_markdown_path=str(markdown_path),
        )

    bundle = adapter.extract(source_path, manifest, workbooks)
    report = validate_bundle(bundle, manifest, dry_run=request.dry_run)

    bronze_keys: list[str] = []
    if not request.dry_run:
        store = request.bronze_store or NullBronzeStore()
        files = {item.name: Path(item.path) for item in workbooks}
        checksums = {
            item.name: {
                "role": item.role,
                "file_sha256": item.file_sha256,
                "schema_sha256": item.schema_sha256,
            }
            for item in workbooks
        }
        bronze_keys = upload_bronze_snapshot(
            store,
            department_id=bundle.department_id,
            module_code=bundle.module_code,
            release_id=bundle.release_id,
            files=files,
            checksums=checksums,
            report_json=report.model_dump_json(indent=2).encode("utf-8"),
        )
        report.bronze_object_keys = bronze_keys

    status: Literal[
        "validated", "blocked", "validation_failed", "completed", "failed", "partial_failed"
    ]
    if report.blocked:
        status = "blocked"
    elif report.error_count:
        status = "validation_failed"
    elif request.dry_run or not request.persist_silver:
        status = "validated"
    else:
        writer = request.silver_writer
        if writer is None:
            from app.repositories.silver import PostgresSilverWriter

            writer = PostgresSilverWriter.from_settings()
        try:
            stats = writer.persist(
                bundle,
                manifest,
                department,
                module,
                request.environment,
            )
        except Exception as exc:
            report.silver = SilverSummary(
                sync_run_id="",
                status="failed",
            )
            json_path, markdown_path = _write_reports(report, output_dir)
            raise IngestionError(f"Silver load failed: {exc}") from exc
        report.silver = SilverSummary(
            sync_run_id=str(stats.sync_run_id),
            status=stats.status,
            inserted_count=stats.inserted_count,
            updated_count=stats.updated_count,
            deactivated_count=stats.deactivated_count,
            unchanged_count=stats.unchanged_count,
        )
        status = "completed" if stats.status == "completed" else "failed"
        if status == "completed" and request.persist_gold:
            indexer = request.gold_indexer or GoldIndexer.from_settings()
            try:
                gold_stats = indexer.sync(
                    department_id=request.department_id,
                    module_code=request.module_code,
                    environment=request.environment,
                    output_dir=request.gold_output_dir,
                    full_rebuild=False,
                )
                report.gold = GoldSummary(
                    status=gold_stats.status,
                    collection=gold_stats.collection,
                    model=gold_stats.model,
                    chunk_count=gold_stats.chunk_count,
                    upserted_count=gold_stats.upserted_count,
                    unchanged_count=gold_stats.unchanged_count,
                    deleted_count=gold_stats.deleted_count,
                )
            except Exception as exc:
                marker = getattr(writer, "mark_status", None)
                if marker is not None:
                    marker(stats.sync_run_id, "partial_failed", str(exc))
                report.gold = GoldSummary(status="failed", error_message=str(exc)[:2000])
                status = "partial_failed"

    json_path, markdown_path = _write_reports(report, output_dir)
    return SyncOutcome(
        status=status,
        report=report,
        report_json_path=str(json_path),
        report_markdown_path=str(markdown_path),
    )
