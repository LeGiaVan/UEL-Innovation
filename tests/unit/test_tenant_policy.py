from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from app.agent.graph import AgentDeps, AgentRuntime
from app.agent.knowledge import MemoryFaqStore, MemoryRetriever
from app.agent.llm import LlmResponse, LlmTimeoutError
from app.agent.policy import ScopeRule
from app.core.config import ApiClient
from app.factory import create_app


def registry(tmp_path):
    path = tmp_path / "configs" / "departments.yaml"
    path.parent.mkdir()
    departments = [
        {
            "id": tenant,
            "name": tenant.upper(),
            "audience": "students",
            "modules": [
                {
                    "code": module,
                    "name": module.upper(),
                    "source_type": "xlsx",
                    "source_path": f"data/{tenant}/{module}",
                    "enabled": True,
                }
                for module in ("one", "two")
            ],
        }
        for tenant in ("alpha", "beta")
    ]
    path.write_text(yaml.safe_dump({"departments": departments}), encoding="utf-8")
    return path


class Classifier:
    def __init__(self):
        self.choice = "shared"
        self.fail = False

    def complete(self, request):
        assert request.purpose == "routing"
        if self.fail:
            raise LlmTimeoutError("timeout")
        return LlmResponse(text="{}", parsed={"rule_id": self.choice})


class Rules:
    def __init__(self):
        self.scope = "out_of_scope"

    def load(self, department_id, module_code, environment):
        return [
            ScopeRule(
                id="shared",
                version=f"{department_id}/{module_code}/v1",
                scope=self.scope,
                topic="Exam rules",
                support_contact=department_id,
                contact_verified=True,
            )
        ]


def test_template_rule_controls_action_and_contact(tmp_path):
    config = registry(tmp_path)
    rules, llm, retriever = Rules(), Classifier(), MemoryRetriever([])
    runtime = AgentRuntime(
        AgentDeps(llm, MemoryFaqStore([]), retriever, rules=rules, config_path=str(config))
    )

    def ask(tenant):
        return runtime.invoke(
            "phuc khao",
            department_id=tenant,
            module_code="one",
            environment="test",
            conversation_id="same",
        )

    assert ask("alpha").status == "out_of_scope"
    assert ask("alpha").support_contact == "alpha"
    assert ask("beta").support_contact == "beta"
    assert ask("beta").rule_version == "beta/one/v1"
    rules.scope = "human_required"
    assert ask("alpha").status == "human_handoff"
    rules.scope = "answer_allowed"
    assert ask("alpha").status == "insufficient_evidence"
    llm.choice = "invented"
    assert ask("alpha").status == "clarification_required"
    llm.fail = True
    assert ask("alpha").status == "clarification_required"
    # Only the allowed decision may retrieve, not OOS/handoff/unknown/timeout.
    assert len(retriever.calls) == 1


def test_missing_policy_never_defaults_to_permission(tmp_path):
    llm, retriever = Classifier(), MemoryRetriever([])
    runtime = AgentRuntime(
        AgentDeps(llm, MemoryFaqStore([]), retriever, config_path=str(registry(tmp_path)))
    )
    result = runtime.invoke(
        "phuc khao", department_id="alpha", module_code="one", environment="test"
    )
    assert result.status == "human_handoff"
    assert not result.search_called
    assert not result.generate_called


def test_invented_gold_citation_falls_back_to_approved_excerpt(tmp_path):
    from app.agent.llm import LlmResponse
    from app.gold.models import GoldHit

    class Dual:
        def complete(self, request):
            if request.purpose == "routing":
                return LlmResponse(text="{}", parsed={"rule_id": "shared"})
            return LlmResponse(text="Nguon: gold:ffffffffffffffffffffffff")

    class CurrentRules:
        def load(self, *args):
            return [
                ScopeRule(
                    id="shared",
                    version="new",
                    release_id="new",
                    scope="answer_allowed",
                    topic="xin diem I",
                )
            ]

    hit = GoldHit(
        chunk_id="gold:aaaaaaaaaaaaaaaaaaaaaaaa",
        entity_type="regulation",
        score=1,
        boosted_score=1,
        stair_markdown="# Xin diem I\n\nNop don trong 3 ngay lam viec.",
        payload={"release_id": "new", "document_code": "TL03"},
    )
    runtime = AgentRuntime(
        AgentDeps(
            Dual(),
            MemoryFaqStore([]),
            MemoryRetriever([hit]),
            rules=CurrentRules(),
            config_path=str(registry(tmp_path)),
        )
    )
    result = runtime.invoke(
        "Toi muon xin diem I, quy trinh nhu the nao",
        department_id="alpha",
        module_code="one",
        environment="test",
    )
    assert result.status == "answered"
    assert result.generate_called is True
    assert "gold:fff" not in result.answer
    assert "3 ngay" in result.answer.casefold() or "3 ngày" in result.answer.casefold()
    assert any(item.value == "TL03" for item in result.citations)


def test_stale_gold_release_is_not_answer_evidence(tmp_path):
    from app.gold.models import GoldHit

    class CurrentRules:
        def load(self, *args):
            return [
                ScopeRule(
                    id="shared",
                    version="new",
                    release_id="new",
                    scope="answer_allowed",
                    topic="policy",
                )
            ]

    hit = GoldHit(
        chunk_id="gold:aaaaaaaaaaaaaaaaaaaaaaaa",
        entity_type="regulation",
        score=1,
        boosted_score=1,
        stair_markdown="old content",
        payload={"release_id": "old"},
    )
    runtime = AgentRuntime(
        AgentDeps(
            Classifier(),
            MemoryFaqStore([]),
            MemoryRetriever([hit]),
            rules=CurrentRules(),
            config_path=str(registry(tmp_path)),
        )
    )
    result = runtime.invoke(
        "policy query", department_id="alpha", module_code="one", environment="test"
    )
    assert result.status == "insufficient_evidence"
    assert not result.generate_called


def test_conversation_clarification_does_not_cross_tenants(tmp_path):
    path = registry(tmp_path)
    data = yaml.safe_load(path.read_text())
    data["departments"][0]["modules"][0]["profile"] = "assessment"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    llm, rules, retriever = Classifier(), Rules(), MemoryRetriever([])
    rules.scope = "answer_allowed"
    runtime = AgentRuntime(
        AgentDeps(llm, MemoryFaqStore([]), retriever, rules=rules, config_path=str(path))
    )
    first = runtime.invoke(
        "Thoi han phuc khao may ngay",
        department_id="alpha",
        module_code="one",
        environment="test",
        conversation_id="shared",
    )
    assert first.status == "clarification_required"
    second = runtime.invoke(
        "test question",
        department_id="beta",
        module_code="one",
        environment="test",
        conversation_id="shared",
    )
    assert second.status == "insufficient_evidence"
    assert retriever.calls == ["test question"]


def test_api_identity_and_admin_registry(settings, tmp_path):
    settings.departments_config_path = str(registry(tmp_path))
    settings.api_clients = [
        ApiClient(
            id="alpha-client",
            department_id="alpha",
            modules=["one"],
            api_key="alpha-key-with-enough-length",
        )
    ]

    class Runtime:
        def invoke(self, message, **context):
            from app.agent.models import ChatResult

            assert context["department_id"] == "alpha"
            assert context["module_code"] == "one"
            assert context["principal_id"] == "alpha-client"
            return ChatResult(request_id="r", status="answered", answer="ok")

    # SecretStr assignment must use the validated type even in tests.
    from pydantic import SecretStr

    settings.app_admin_api_key = SecretStr("admin-secret-with-enough-length")
    with TestClient(create_app(settings)) as client:
        client.app.state.agent_runtime = Runtime()
        headers = {"X-API-Key": "alpha-key-with-enough-length"}
        assert (
            client.post(
                "/v1/chat", headers=headers, json={"message": "hi", "module_code": "two"}
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/v1/chat", headers=headers, json={"message": "hi", "department_id": "beta"}
            ).status_code
            == 422
        )
        assert client.post("/v1/chat", headers=headers, json={"message": "hi"}).status_code == 200
        assert client.get("/v1/admin/registry", headers=headers).status_code == 401
        admin = {"X-Admin-Key": settings.app_admin_api_key.get_secret_value()}
        response = client.get("/v1/admin/registry", headers=admin)
        assert response.status_code == 200
        body = response.json()
        import base64

        package = {
            "department_id": "beta",
            "module_code": "one",
            "files": {
                "release-manifest.yaml": base64.b64encode(b"schema_version: '1.0'").decode(),
                "input.xlsx": base64.b64encode(b"example").decode(),
            },
        }
        assert client.post("/v1/admin/sources", headers=headers, json=package).status_code == 401
        unsafe = {**package, "files": {"../escape.xlsx": ""}}
        assert client.post("/v1/admin/sources", headers=admin, json=unsafe).status_code == 422
        assert client.post("/v1/admin/sources", headers=admin, json=package).status_code == 200
        assert client.post("/v1/admin/sources", headers=admin, json=package).status_code == 409
        body["departments"][0]["modules"][0]["enabled"] = False
        result = client.put(
            "/v1/admin/registry", headers={**admin, "If-Match": response.headers["etag"]}, json=body
        )
        assert result.status_code == 200
        assert (
            client.get(
                "/v1/admin/registry/revisions/" + response.headers["etag"], headers=admin
            ).status_code
            == 200
        )
        assert (
            client.put(
                "/v1/admin/registry",
                headers={**admin, "If-Match": response.headers["etag"]},
                json=body,
            ).status_code
            == 409
        )
        assert client.post("/v1/chat", headers=headers, json={"message": "hi"}).status_code == 403


def test_silver_rule_store_filters_tenant_module_release_and_approval():
    from datetime import UTC, datetime
    from uuid import uuid4

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session, sessionmaker

    from app.agent.policy import SilverRuleStore
    from app.db.base import Base
    from app.models.tables import Department, Module, RoutingRule

    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine, tables=[Department.__table__, Module.__table__, RoutingRule.__table__]
    )
    now = datetime.now(UTC)
    common = dict(
        source_file="template.xlsx",
        source_file_sha256="a",
        source_schema_sha256="b",
        source_sheet="scope",
        source_row=10,
        release_id="r1",
        sync_run_id=uuid4(),
        last_seen_sync_run_id=uuid4(),
        ingested_at=now,
        created_at=now,
        updated_at=now,
        release_status="approved_for_dev",
        content_hash="hash",
        is_active=True,
    )
    with Session(engine) as session:
        for tenant in ("alpha", "beta"):
            department = Department(
                code=tenant, name=tenant, audience="students", created_at=now, updated_at=now
            )
            session.add(department)
            session.flush()
            module = Module(department_id=department.id, code="one", name=tenant, **common)
            session.add(module)
            session.flush()
            session.add(
                RoutingRule(
                    department_id=department.id,
                    module_id=module.id,
                    source_key="same-id",
                    topic=tenant,
                    scope_type="answer_allowed",
                    **common,
                )
            )
            session.add(
                RoutingRule(
                    department_id=department.id,
                    module_id=module.id,
                    source_key="stale",
                    topic="stale",
                    scope_type="answer_allowed",
                    **{**common, "release_id": "old"},
                )
            )
        session.commit()
    store = SilverRuleStore(sessionmaker(engine))
    assert [r.topic for r in store.load("alpha", "one", "test")] == ["alpha"]
    assert [r.topic for r in store.load("beta", "one", "test")] == ["beta"]
    assert store.load("alpha", "two", "test") == []
    assert store.load("alpha", "one", "uat") == []
    engine.dispose()


def test_explicit_template_rule_id_survives_topic_changes():
    from openpyxl import Workbook

    from app.ingestion.xlsx_adapter import parse_routing_rules

    book = Workbook()
    sheet = book.active
    sheet.title = "1. Phạm vi trả lời"
    sheet["H9"] = "rule_id"
    sheet["B10"] = "Trong phạm vi trả lời"
    sheet["C10"] = "First description"
    sheet["H10"] = "scope-001"
    first = parse_routing_rules(book, "template.xlsx", "alpha", "one")
    sheet["C10"] = "Updated description"
    second = parse_routing_rules(book, "template.xlsx", "alpha", "one")
    assert first[0].source_key == second[0].source_key == "scope-001"
    assert first[0].content_hash != second[0].content_hash


def test_second_tenant_ingestion_uses_config_names(tmp_path):
    from app.ingestion.pipeline import SyncRequest, run_sync
    from tests.helpers.xlsx_builder import write_mini_release

    folder = tmp_path / "source"
    config = write_mini_release(folder, module_name="Student finance")
    manifest_path = folder / "release-manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["department"] = {"id": "finance", "name": "Finance department"}
    manifest["module"] = {"code": "payments", "name": "Student finance"}
    manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
    data = yaml.safe_load(config.read_text(encoding="utf-8"))
    department = data["departments"][0]
    department.update(id="finance", name="Finance department")
    department["modules"][0].update(code="payments", name="Student finance")
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
        )
    )
    assert outcome.status == "validated"
    assert outcome.report.error_count == 0
    assert "/finance/payments/" in Path(outcome.report_json_path).as_posix()


def test_openapi_lists_admin_etl_and_inspect_release(settings, tmp_path):
    import base64

    from pydantic import SecretStr

    from tests.helpers.xlsx_builder import write_mini_release

    config = tmp_path / "configs" / "departments.yaml"
    config.parent.mkdir()
    config.write_text(yaml.safe_dump({"departments": []}), encoding="utf-8")
    settings.departments_config_path = str(config)
    settings.app_admin_api_key = SecretStr("admin-secret-with-enough-length")
    folder = tmp_path / "pkg"
    write_mini_release(folder, module_name="Student finance")
    files = {
        path.name: base64.b64encode(path.read_bytes()).decode() for path in folder.glob("*.xlsx")
    }
    with TestClient(create_app(settings)) as client:
        schema = client.get("/openapi.json").json()
        paths = schema["paths"]
        assert "/v1/admin/releases" in paths
        assert "/v1/admin/packages/inspect" in paths
        assert "/v1/admin/tenants" in paths
        assert any(tag["name"] == "administration" for tag in schema["tags"])
        admin = {"X-Admin-Key": "admin-secret-with-enough-length"}
        inspected = client.post(
            "/v1/admin/packages/inspect",
            headers=admin,
            json={
                "department_id": "finance",
                "department_name": "Finance department",
                "module_code": "payments",
                "module_name": "Student finance",
                "release_id": "fin-pay-001",
                "files": files,
            },
        )
        assert inspected.status_code == 200
        body = inspected.json()
        assert {item["role"] for item in body["files"]} == {
            "module_and_routing",
            "faq",
            "business_documents",
        }
        assert body["expected_counts"]["routing_rules"] == 3
        created = client.post(
            "/v1/admin/releases",
            headers=admin,
            json={
                "department_id": "finance",
                "department_name": "Finance department",
                "module_code": "payments",
                "module_name": "Student finance",
                "release_id": "fin-pay-001",
                "files": files,
                "dry_run": True,
            },
        )
        assert created.status_code == 200
        payload = created.json()
        assert payload["status"] == "validated"
        assert payload["sync"]["report"]["error_count"] == 0
        listed = client.get("/v1/admin/tenants", headers=admin)
        assert listed.status_code == 200
        assert listed.json()[0]["department_id"] == "finance"
        assert listed.json()[0]["source_present"] is True
