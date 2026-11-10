from pathlib import Path

from app.ingestion.pipeline import SyncRequest, run_sync
from tests.helpers.xlsx_builder import write_mini_release


def test_duplicate_faq_code_is_error(tmp_path: Path) -> None:
    config_path = write_mini_release(tmp_path / "release", duplicate_faq=True)
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
    assert any(issue.code == "FAQ_DUPLICATE_CODE" for issue in outcome.report.issues)


def test_unknown_fee_and_missing_legal_basis_are_warnings(tmp_path: Path) -> None:
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
    codes = {issue.code for issue in outcome.report.issues}
    finding_ids = {item.id for item in outcome.report.policy_findings}
    assert "DATA-05" in codes
    assert "DATA-07" in codes
    assert finding_ids == {f"DATA-{index:02d}" for index in range(1, 11)}
    assert outcome.report.warning_count >= 1
