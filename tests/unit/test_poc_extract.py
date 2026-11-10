from pathlib import Path

from app.ingestion.pipeline import SyncRequest, run_sync

POC_DIR = Path("data/P.BDCL")
CONFIG = Path("configs/departments.yaml")


def test_poc_xlsx_matches_phase0_exit_gate_counts(tmp_path: Path) -> None:
    outcome = run_sync(
        SyncRequest(
            department_id="bao_dam_chat_luong",
            module_code="khao_khi",
            source_type="xlsx",
            source_path=POC_DIR,
            config_path=CONFIG,
            output_dir=tmp_path / "out",
            dry_run=True,
            environment="development",
        )
    )
    report = outcome.report
    assert outcome.status == "validated"
    assert report.counts.routing_rules == 17
    assert report.counts.faqs == 71
    assert report.counts.documents == 4
    assert report.counts.regulation_sections == 15
    assert report.counts.condition_exception_sections == 26
    assert report.counts.dossier_items == 4
    assert report.counts.procedure_steps == 13
    assert report.error_count == 0
    assert report.publish_allowed
    assert {finding.id for finding in report.policy_findings} == {
        f"DATA-{index:02d}" for index in range(1, 11)
    }
    assert all(
        issue.source_file and issue.source_sheet and issue.source_row
        for issue in report.issues
        if issue.code in {"DATA-05", "DATA-07", "ROUTING_INVALID_SCOPE"}
    )
    missing_basis = sum(1 for issue in report.issues if issue.code == "DATA-05")
    assert missing_basis == 59
    unknown_fees = sum(1 for issue in report.issues if issue.code == "DATA-07")
    assert unknown_fees == 3
