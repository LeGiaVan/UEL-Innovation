from pathlib import Path

from app.ingestion.pipeline import SyncRequest, run_sync
from tests.helpers.xlsx_builder import write_mini_release


def test_xlsx_adapter_reads_mini_release_and_skips_empty_or_guidance_rows(
    tmp_path: Path,
) -> None:
    config_path = write_mini_release(tmp_path / "release")
    outcome = run_sync(
        SyncRequest(
            department_id="bao_dam_chat_luong",
            module_code="khao_khi",
            source_type="xlsx",
            source_path=tmp_path / "release",
            config_path=config_path,
            output_dir=tmp_path / "out",
            dry_run=True,
            environment="test",
        )
    )
    assert outcome.status == "validated"
    counts = outcome.report.counts
    assert counts.routing_rules == 3
    assert counts.faqs == 2
    assert counts.documents == 4
    assert counts.regulation_sections == 4
    assert counts.condition_exception_sections == 4
    assert counts.dossier_items == 3
    assert counts.procedure_steps == 3
    located = [issue for issue in outcome.report.issues if issue.code != "DATA-06"]
    assert located
    assert all(issue.source_file and issue.source_row for issue in located)


def test_invalid_routing_enum_is_error(tmp_path: Path) -> None:
    config_path = write_mini_release(tmp_path / "release", invalid_scope=True)
    outcome = run_sync(
        SyncRequest(
            department_id="bao_dam_chat_luong",
            module_code="khao_khi",
            source_type="xlsx",
            source_path=tmp_path / "release",
            config_path=config_path,
            output_dir=tmp_path / "out",
            dry_run=True,
            environment="test",
        )
    )
    assert outcome.status == "validation_failed"
    assert any(issue.code == "ROUTING_INVALID_SCOPE" for issue in outcome.report.issues)
