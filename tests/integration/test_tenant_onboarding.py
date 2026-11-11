from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.integration
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.agent.policy import SilverRuleStore
from app.gold.builder import build_gold_chunks
from app.ingestion.bronze import NullBronzeStore
from app.ingestion.pipeline import SyncRequest, run_sync
from app.models.tables import Department
from tests.helpers.xlsx_builder import write_mini_release


def test_new_tenant_persists_names_and_isolated_policy(tmp_path: Path, db_session, silver_writer):
    folder = tmp_path / "finance"
    config = write_mini_release(folder, module_name="Student finance")
    manifest_path = folder / "release-manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["department"] = {"id": "finance", "name": "Finance department"}
    manifest["module"] = {"code": "payments", "name": "Student finance"}
    manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
    data = yaml.safe_load(config.read_text(encoding="utf-8"))
    department = data["departments"][0]
    department.update(
        id="finance", name="Finance department", contact={"support_contact": "Finance desk"}
    )
    department["modules"][0].update(code="payments", name="Student finance", contact={})
    config.write_text(yaml.safe_dump(data), encoding="utf-8")
    outcome = run_sync(
        SyncRequest(
            department_id="finance",
            module_code="payments",
            source_type="xlsx",
            source_path=folder,
            config_path=config,
            output_dir=tmp_path / "out",
            environment="test",
            dry_run=False,
            bronze_store=NullBronzeStore(),
            silver_writer=silver_writer,
        )
    )
    assert outcome.status == "completed"
    engine = db_session.get_bind()
    with Session(engine) as session:
        assert (
            session.scalar(select(Department.name).where(Department.code == "finance"))
            == "Finance department"
        )
        chunks = build_gold_chunks(
            session, department_id="finance", module_code="payments", environment="test"
        )
        assert chunks
        assert all("Finance department" in c.stair_markdown for c in chunks)
        assert all("Student finance" in c.stair_markdown for c in chunks)
        assert all(c.payload["release_id"] == manifest["release_id"] for c in chunks)
    store = SilverRuleStore(sessionmaker(engine))
    assert len(store.load("finance", "payments", "test")) == 3
    assert store.load("another", "payments", "test") == []
