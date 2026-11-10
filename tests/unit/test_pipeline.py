from pathlib import Path

import yaml

from app.cli import main
from app.ingestion.bronze import NullBronzeStore
from app.ingestion.pipeline import SyncRequest, run_sync
from tests.helpers.xlsx_builder import write_mini_release


def test_dry_run_does_not_upload_bronze(tmp_path: Path) -> None:
    config_path = write_mini_release(tmp_path / "release")
    store = NullBronzeStore()
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
            bronze_store=store,
        )
    )
    assert outcome.status == "validated"
    assert store.uploads == []
    assert outcome.report.bronze_object_keys == []
    assert Path(outcome.report_json_path or "").is_file()
    assert Path(outcome.report_markdown_path or "").is_file()


def test_non_dry_run_uploads_snapshots_without_postgres(tmp_path: Path) -> None:
    config_path = write_mini_release(tmp_path / "release")
    store = NullBronzeStore()
    outcome = run_sync(
        SyncRequest(
            department_id="bao_dam_chat_luong",
            module_code="khao_khi",
            source_type="xlsx",
            source_path=tmp_path / "release",
            config_path=config_path,
            output_dir=tmp_path / "out",
            dry_run=False,
            environment="test",
            bronze_store=store,
            persist_silver=False,
        )
    )
    assert outcome.status == "validated"
    assert any(key.endswith("checksums.json") for key in store.uploads)
    assert any(key.endswith("validation.json") for key in store.uploads)
    assert len(store.uploads) == 5


def test_checksum_mismatch_blocks_parser(tmp_path: Path) -> None:
    config_path = write_mini_release(tmp_path / "release")
    manifest_path = tmp_path / "release" / "release-manifest.yaml"
    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    payload["files"][1]["file_sha256"] = "0" * 64
    manifest_path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
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
    assert outcome.status == "blocked"
    assert outcome.report.blocked_reason == "checksum_mismatch"
    assert outcome.report.counts.faqs == 0


def test_cli_dry_run_writes_reports(tmp_path: Path) -> None:
    config_path = write_mini_release(tmp_path / "release")
    code = main(
        [
            "sync",
            "--department",
            "bao_dam_chat_luong",
            "--module",
            "khao_khi",
            "--source",
            "xlsx",
            "--source-path",
            str(tmp_path / "release"),
            "--config",
            str(config_path),
            "--output",
            str(tmp_path / "out"),
            "--env",
            "test",
            "--dry-run",
        ]
    )
    assert code == 0
    assert (tmp_path / "out" / "mini-khao-khi-test" / "validation.json").is_file()
    assert (tmp_path / "out" / "mini-khao-khi-test" / "validation.md").is_file()


def test_cli_google_sheets_is_not_implemented() -> None:
    assert (
        main(
            [
                "sync",
                "--department",
                "bao_dam_chat_luong",
                "--module",
                "khao_khi",
                "--source",
                "google-sheets",
                "--dry-run",
            ]
        )
        == 4
    )
