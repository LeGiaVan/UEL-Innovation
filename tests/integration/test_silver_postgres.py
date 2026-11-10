from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ingestion.models import SyncOutcome
from app.ingestion.pipeline import SyncRequest, run_sync
from app.models.tables import (
    Department,
    Document,
    DocumentSection,
    Faq,
    Module,
    RoutingRule,
    SyncRun,
)
from app.repositories.silver import PostgresSilverWriter
from tests.helpers.xlsx_builder import update_faq_answer, write_mini_release

pytestmark = pytest.mark.integration


def _sync(
    tmp_path: Path,
    writer: PostgresSilverWriter,
    source: Path,
    config: Path,
) -> SyncOutcome:
    return run_sync(
        SyncRequest(
            department_id="bao_dam_chat_luong",
            module_code="khao_khi",
            source_type="xlsx",
            source_path=source,
            config_path=config,
            output_dir=tmp_path / "out",
            dry_run=False,
            environment="test",
            persist_silver=True,
            silver_writer=writer,
        )
    )


def test_mini_release_is_idempotent(
    tmp_path: Path,
    db_session: Session,
    silver_writer: PostgresSilverWriter,
) -> None:
    config_path = write_mini_release(tmp_path / "release")
    first = _sync(tmp_path, silver_writer, tmp_path / "release", config_path)
    second = _sync(tmp_path, silver_writer, tmp_path / "release", config_path)
    assert first.status == "completed"
    assert second.status == "completed"
    assert db_session.scalar(select(func.count()).select_from(Department)) == 1
    assert db_session.scalar(select(func.count()).select_from(Module)) == 1
    assert (
        db_session.scalar(
            select(func.count()).select_from(RoutingRule).where(RoutingRule.is_active.is_(True))
        )
        == 3
    )
    assert (
        db_session.scalar(select(func.count()).select_from(Faq).where(Faq.is_active.is_(True))) == 2
    )
    assert (
        db_session.scalar(
            select(func.count()).select_from(Document).where(Document.is_active.is_(True))
        )
        == 4
    )
    assert second.report.silver is not None
    assert second.report.silver.inserted_count == 0
    faq_ids = list(db_session.scalars(select(Faq.id)).all())
    assert len(faq_ids) == len(set(faq_ids))
    inherited = db_session.scalars(select(Faq)).all()
    assert all(item.contact_source == "module" for item in inherited)
    assert all(item.contact_verified is False for item in inherited)


def test_one_cell_change_updates_only_that_faq(
    tmp_path: Path,
    db_session: Session,
    silver_writer: PostgresSilverWriter,
) -> None:
    config_path = write_mini_release(tmp_path / "release")
    _sync(tmp_path, silver_writer, tmp_path / "release", config_path)
    before = {
        row.question_code: (row.id, row.content_hash, row.answer)
        for row in db_session.scalars(select(Faq))
    }
    db_session.expire_all()
    update_faq_answer(tmp_path / "release", "I.1.001", "Câu trả lời đã sửa.")
    outcome = _sync(tmp_path, silver_writer, tmp_path / "release", config_path)
    assert outcome.status == "completed"
    after = {
        row.question_code: (row.id, row.content_hash, row.answer)
        for row in db_session.scalars(select(Faq))
    }
    assert after["I.1.001"][0] == before["I.1.001"][0]
    assert after["I.1.001"][2] == "Câu trả lời đã sửa."
    assert after["I.1.001"][1] != before["I.1.001"][1]
    assert after["I.1.002"] == before["I.1.002"]
    assert outcome.report.silver is not None
    assert outcome.report.silver.updated_count >= 1


def test_failed_sync_is_recorded_and_leaves_no_partial_silver(
    tmp_path: Path,
    db_session: Session,
    silver_writer: PostgresSilverWriter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = write_mini_release(tmp_path / "release")

    def boom(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise RuntimeError("injected silver failure")

    monkeypatch.setattr(silver_writer, "_apply", boom)
    with pytest.raises(Exception, match="injected silver failure"):
        _sync(tmp_path, silver_writer, tmp_path / "release", config_path)
    db_session.expire_all()
    assert db_session.scalar(select(func.count()).select_from(Faq)) == 0
    run = db_session.scalar(select(SyncRun).order_by(SyncRun.started_at.desc()))
    assert run is not None
    assert run.status == "failed"


def test_poc_counts_match_exit_gate(
    tmp_path: Path,
    db_session: Session,
    silver_writer: PostgresSilverWriter,
) -> None:
    outcome = run_sync(
        SyncRequest(
            department_id="bao_dam_chat_luong",
            module_code="khao_khi",
            source_type="xlsx",
            source_path=Path("data/P.BDCL"),
            config_path=Path("configs/departments.yaml"),
            output_dir=tmp_path / "out",
            dry_run=False,
            environment="development",
            persist_silver=True,
            silver_writer=silver_writer,
        )
    )
    assert outcome.status == "completed"
    assert db_session.scalar(select(func.count()).select_from(Department)) == 1
    assert db_session.scalar(select(func.count()).select_from(Module)) == 1
    assert (
        db_session.scalar(
            select(func.count()).select_from(RoutingRule).where(RoutingRule.is_active.is_(True))
        )
        == 17
    )
    assert (
        db_session.scalar(select(func.count()).select_from(Faq).where(Faq.is_active.is_(True)))
        == 71
    )
    assert (
        db_session.scalar(
            select(func.count()).select_from(Document).where(Document.is_active.is_(True))
        )
        == 4
    )
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(DocumentSection)
            .where(
                DocumentSection.is_active.is_(True),
                DocumentSection.section_type == "regulation",
            )
        )
        == 15
    )
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(DocumentSection)
            .where(
                DocumentSection.is_active.is_(True),
                DocumentSection.section_type != "regulation",
            )
        )
        == 26
    )
