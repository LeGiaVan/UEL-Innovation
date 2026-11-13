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
    assert "Exam rules" not in ask("alpha").answer
    assert "ĐHCQ" not in ask("alpha").answer
    assert "ONE" in ask("alpha").answer
    assert "Chưa xác định chắc chắn phạm vi hỗ trợ" not in ask("alpha").answer


def test_exact_faq_answers_before_policy_classifier(tmp_path):
    from app.agent.models import FaqMatch

    llm = Classifier()
    llm.choice = "invented"
    faqs = MemoryFaqStore(
        [
            FaqMatch(
                question_code="I.1.001",
                question="Quy định khảo thí ở đâu?",
                answer="Theo Quyết định 3388.",
            )
        ]
    )
    runtime = AgentRuntime(
        AgentDeps(
            llm,
            faqs,
            MemoryRetriever([]),
            rules=Rules(),
            config_path=str(registry(tmp_path)),
        )
    )
    result = runtime.invoke(
        "Quy định khảo thí ở đâu?",
        department_id="alpha",
        module_code="one",
        environment="test",
    )
    assert result.status == "faq_answered"
    assert "3388" in result.answer
    assert result.routing_source == "faq_exact"
    assert result.faq_question_code == "I.1.001"


def test_fee_question_abstains_instead_of_scope_menu(tmp_path):
    config = registry(tmp_path)
    data = yaml.safe_load(config.read_text(encoding="utf-8"))
    data["departments"][0]["modules"][0]["profile"] = "assessment"
    config.write_text(yaml.safe_dump(data), encoding="utf-8")
    llm = Classifier()
    llm.choice = "invented"
    runtime = AgentRuntime(
        AgentDeps(
            llm,
            MemoryFaqStore([]),
            MemoryRetriever([]),
            rules=Rules(),
            config_path=str(config),
        )
    )
    result = runtime.invoke(
        "lệ phí phúc khảo",
        department_id="alpha",
        module_code="one",
        environment="test",
    )
    assert result.status == "insufficient_evidence"
    assert result.routing_source == "fee_keyword"
    assert "số tiền" in result.answer
    assert "Nội dung bot có thể trả lời" not in result.answer
    assert "Chưa khớp đúng một phạm vi" not in result.answer


def test_iter_progress_emits_greeting_result(tmp_path):
    runtime = AgentRuntime(
        AgentDeps(
            Classifier(),
            MemoryFaqStore([]),
            MemoryRetriever([]),
            rules=Rules(),
            config_path=str(registry(tmp_path)),
        )
    )
    stages: list[str] = []
    final = None
    for name, item in runtime.iter_progress(
        "xin chào",
        department_id="alpha",
        module_code="one",
        environment="test",
        conversation_id="progress",
    ):
        stages.append(name)
        if item is not None:
            final = item
    assert "routing_check" not in stages
    assert stages[-1] == "__result__"
    assert final is not None
    assert final.status == "greeting"


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
        assert "/v1/admin/releases/upload" in paths
        assert "/v1/admin/packages/inspect" in paths
        assert "/v1/admin/packages/inspect-upload" in paths
        assert "/v1/admin/tenants" in paths
        assert "/v1/admin/modules/{department_id}/{module_code}/bot" in paths
        assert "/v1/admin/chat-preview" in paths
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


def test_admin_multipart_upload_inspect_and_release(settings, tmp_path):
    from pydantic import SecretStr

    from tests.helpers.xlsx_builder import write_mini_release

    config = tmp_path / "configs" / "departments.yaml"
    config.parent.mkdir()
    config.write_text(yaml.safe_dump({"departments": []}), encoding="utf-8")
    settings.departments_config_path = str(config)
    settings.app_admin_api_key = SecretStr("admin-secret-with-enough-length")
    folder = tmp_path / "pkg"
    write_mini_release(folder, module_name="Student finance")
    module_xlsx = next(folder.glob("1*.xlsx"))
    faq_xlsx = next(folder.glob("2*.xlsx"))
    docs_xlsx = next(folder.glob("3*.xlsx"))
    uploads = {
        "workbook_module": (module_xlsx.name, module_xlsx.read_bytes()),
        "workbook_faq": (faq_xlsx.name, faq_xlsx.read_bytes()),
        "workbook_documents": (docs_xlsx.name, docs_xlsx.read_bytes()),
    }
    admin = {"X-Admin-Key": "admin-secret-with-enough-length"}
    with TestClient(create_app(settings)) as client:
        inspected = client.post(
            "/v1/admin/packages/inspect-upload",
            headers=admin,
            data={
                "department_id": "dao_tao",
                "department_name": "Dao tao",
                "module_code": "dkhp",
                "module_name": "Student finance",
                "release_id": "pdt-001",
            },
            files=uploads,
        )
        assert inspected.status_code == 200, inspected.text
        created = client.post(
            "/v1/admin/releases/upload",
            headers=admin,
            data={
                "department_id": "dao_tao",
                "department_name": "Dao tao",
                "module_code": "dkhp",
                "module_name": "Student finance",
                "release_id": "pdt-001",
                "dry_run": "true",
            },
            files=uploads,
        )
        assert created.status_code == 200, created.text
        assert created.json()["status"] == "validated"
        stored = tmp_path / "data" / "dao_tao" / "dkhp" / "pdt-001"
        assert stored.is_dir()
        assert len(list(stored.glob("*.xlsx"))) == 3
        assert (stored / "release-manifest.yaml").is_file()


def test_generic_generate_prompt_omits_assessment_glossary():
    from app.agent.policy import module_generate_system

    generic = module_generate_system("Đăng ký học phần", "Phòng Đào tạo")
    assert "ĐHCQ" not in generic
    assert "sinh viên học kỳ" not in generic
    assert "gold:" in generic
    assert "thân thiện" in generic
    assert "chunk_id" in generic
    packed = module_generate_system(
        "Mô-đun Khảo khí",
        "Phòng Bảo đảm chất lượng",
        glossary={"ĐHCQ": "đại học chính quy"},
        constraints="Không viết ĐHCQ thành sinh viên học kỳ.",
    )
    assert "ĐHCQ: đại học chính quy" in packed
    assert "Không viết ĐHCQ" in packed


def test_generate_user_prompt_uses_pack_not_khao_khi_defaults():
    from app.agent.models import RetrievedEvidence
    from app.agent.prompts import SYSTEM_GENERATE, generate_user_prompt

    evidence = [
        RetrievedEvidence(
            chunk_id="gold:aaaaaaaaaaaaaaaaaaaaaaaa",
            entity_type="regulation",
            boosted_score=0.9,
            stair_markdown="Hạn 2 ngày.",
            document_code="TL02",
        )
    ]
    plain = generate_user_prompt("hỏi quy định", evidence, "unknown")
    assert "ĐHCQ" not in plain
    assert "khảo thí" not in plain.casefold()
    assert "Khảo khí" not in plain
    packed = generate_user_prompt(
        "hỏi quy định",
        evidence,
        "dhcq",
        training_systems=["dhcq", "sdh"],
        writing_notes="PACK_STYLE_MARKER",
        glossary={"ĐHCQ": "đại học chính quy", "SĐH": "sau đại học"},
    )
    assert "PACK_STYLE_MARKER" in packed
    assert "ĐHCQ (đại học chính quy)" in packed
    assert "khảo thí" not in SYSTEM_GENERATE.casefold()
    assert "Khảo khí" not in SYSTEM_GENERATE


def test_pack_answer_style_reaches_generate(tmp_path):
    from app.agent.llm import FakeLlm
    from app.gold.models import GoldHit

    config = registry(tmp_path)
    data = yaml.safe_load(config.read_text(encoding="utf-8"))
    module = data["departments"][0]["modules"][0]
    module["profile"] = "assessment"
    module["routing_aliases"] = {"shared": ["Thời hạn phúc khảo ĐHCQ"]}
    module["prompt_pack"] = {
        "answer_style": "PACK_STYLE_MARKER",
        "metadata_system": "PACK_META_MARKER",
        "glossary": {"ĐHCQ": "đại học chính quy", "SĐH": "sau đại học"},
    }
    config.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    llm = FakeLlm(generate_text="Hạn 02 ngày. Nguồn: TL02.")
    rules = Rules()
    rules.scope = "answer_allowed"
    runtime = AgentRuntime(
        AgentDeps(
            llm,
            MemoryFaqStore([]),
            MemoryRetriever(
                [
                    GoldHit(
                        chunk_id="gold:aaaaaaaaaaaaaaaaaaaaaaaa",
                        entity_type="regulation",
                        score=0.9,
                        boosted_score=0.9,
                        stair_markdown="Hạn phúc khảo ĐHCQ 02 ngày làm việc.",
                        payload={"document_code": "TL02"},
                    )
                ]
            ),
            rules=rules,
            config_path=str(config),
        )
    )
    result = runtime.invoke(
        "Thời hạn phúc khảo ĐHCQ",
        department_id="alpha",
        module_code="one",
        environment="test",
    )
    assert result.status == "answered"
    generate_req = next(item for item in llm.requests if item.purpose == "generate")
    user = generate_req.messages[1].content
    assert "PACK_STYLE_MARKER" in user
    assert "ĐHCQ" in user
    assert "khảo thí" not in generate_req.messages[0].content.casefold()


def test_custom_greeting_comes_from_module_messages(tmp_path):
    config = registry(tmp_path)
    data = yaml.safe_load(config.read_text(encoding="utf-8"))
    data["departments"][0]["modules"][0]["messages"] = {"greeting": "Xin chao tai chinh."}
    config.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    runtime = AgentRuntime(
        AgentDeps(
            Classifier(),
            MemoryFaqStore([]),
            MemoryRetriever([]),
            rules=Rules(),
            config_path=str(config),
        )
    )
    result = runtime.invoke(
        "xin chào", department_id="alpha", module_code="one", environment="test"
    )
    assert result.status == "greeting"
    assert result.answer == "Xin chao tai chinh."


def test_bot_config_put_preview_and_ingest_keeps_pack(settings, tmp_path):
    from pydantic import SecretStr

    from app.api.routes.admin import _upsert_registry
    from app.ingestion.contact import ContactConfig
    from app.ingestion.manifest import DepartmentModuleConfig

    config = registry(tmp_path)
    settings.departments_config_path = str(config)
    settings.app_admin_api_key = SecretStr("admin-secret-with-enough-length")
    admin = {"X-Admin-Key": "admin-secret-with-enough-length"}
    with TestClient(create_app(settings)) as client:

        class Runtime:
            def invoke(self, message, **context):
                from app.agent.models import ChatResult

                assert context["department_id"] == "alpha"
                assert context["principal_id"] == "admin-preview"
                return ChatResult(
                    request_id="r",
                    status="answered",
                    answer="preview-ok",
                    routing_source="template_policy",
                    rule_id="shared",
                )

        client.app.state.agent_runtime = Runtime()
        loaded = client.get("/v1/admin/modules/alpha/one/bot", headers=admin)
        assert loaded.status_code == 200
        assert loaded.json()["retrieval"] == {
            "top_k": 5,
            "score_threshold": 0.4167,
            "mode": "hybrid",
            "faq_boost": 0.12,
        }
        saved = client.put(
            "/v1/admin/modules/alpha/one/bot",
            headers={**admin, "If-Match": loaded.headers["etag"]},
            json={
                "prompt_pack": {
                    "role": "Tro ly tai chinh",
                    "constraints": "Khong bia so tien.",
                    "glossary": {"HP": "hoc phan"},
                    "answer_style": "Tra loi tung he.",
                    "metadata_system": "PACK_META_MARKER",
                },
                "messages": {"greeting": "Xin chao PDT."},
                "retrieval": {"top_k": 3, "score_threshold": 0.4},
                "routing_aliases": {},
                "profile": "generic",
            },
        )
        assert saved.status_code == 200, saved.text
        preview = client.post(
            "/v1/admin/chat-preview",
            headers=admin,
            json={"department_id": "alpha", "module_code": "one", "message": "hello"},
        )
        assert preview.status_code == 200
        assert preview.json()["answer"] == "preview-ok"
        _upsert_registry(
            config,
            department_id="alpha",
            department_name="ALPHA",
            audience="students",
            module=DepartmentModuleConfig(
                code="one",
                name="ONE",
                source_type="xlsx",
                source_path="data/alpha/one",
                profile="generic",
                contact=ContactConfig(),
            ),
            contact=ContactConfig(),
        )
        kept = client.get("/v1/admin/modules/alpha/one/bot", headers=admin)
        assert kept.status_code == 200
        body = kept.json()
        assert body["prompt_pack"]["role"] == "Tro ly tai chinh"
        assert body["prompt_pack"]["glossary"]["HP"] == "hoc phan"
        assert body["prompt_pack"]["answer_style"] == "Tra loi tung he."
        assert body["prompt_pack"]["metadata_system"] == "PACK_META_MARKER"
        assert body["messages"]["greeting"] == "Xin chao PDT."
        assert body["retrieval"] == {
            "top_k": 3,
            "score_threshold": 0.4,
            "mode": "hybrid",
            "faq_boost": 0.12,
        }
        page = client.get("/admin")
        assert page.status_code == 200
        assert "Prompt pack" in page.text
        assert "answerStyle" in page.text
        assert "metadataSystem" in page.text
        assert "Thêm mô-đun" in page.text
        assert "inspectTemplates" in page.text
        assert "ragMode" in page.text
        assert "faqBoost" in page.text


def test_generic_module_does_not_rewrite_phuc_khao_or_say_khao_khi(tmp_path):
    from app.agent.llm import LlmResponse
    from app.gold.models import GoldHit

    class Dual:
        def complete(self, request):
            if request.purpose == "routing":
                return LlmResponse(text="{}", parsed={"rule_id": "shared"})
            return LlmResponse(text="Han 5 ngay. Nguồn: QT01.")

    config = registry(tmp_path)
    retriever = MemoryRetriever(
        [
            GoldHit(
                chunk_id="gold:aaaaaaaaaaaaaaaaaaaaaaaa",
                entity_type="regulation",
                score=1,
                boosted_score=1,
                stair_markdown="Han nop don 5 ngay lam viec.",
                payload={"document_code": "QT01"},
            )
        ]
    )
    rules = Rules()
    rules.scope = "answer_allowed"
    runtime = AgentRuntime(
        AgentDeps(Dual(), MemoryFaqStore([]), retriever, rules=rules, config_path=str(config))
    )
    greeting = runtime.invoke(
        "xin chào", department_id="alpha", module_code="one", environment="test"
    )
    assert greeting.status == "greeting"
    assert "Khảo khí" not in greeting.answer
    assert "ONE" in greeting.answer
    result = runtime.invoke(
        "Thời hạn phúc khảo ĐHCQ",
        department_id="alpha",
        module_code="one",
        environment="test",
        conversation_id="generic-retrieve",
    )
    assert retriever.calls
    assert retriever.calls[-1] == "Thời hạn phúc khảo ĐHCQ"
    assert "Portal UEL" not in retriever.calls[-1]
    assert result.status in {"answered", "insufficient_evidence"}


def test_assessment_module_rewrites_phuc_khao_query(tmp_path):
    from app.agent.llm import LlmResponse
    from app.gold.models import GoldHit

    class Dual:
        def complete(self, request):
            if request.purpose == "routing":
                return LlmResponse(text="{}", parsed={"rule_id": "shared"})
            if request.purpose == "metadata":
                return LlmResponse(
                    text="{}",
                    parsed={
                        "training_system": "dhcq",
                        "topic": "phuc_khao",
                        "is_fee_question": False,
                    },
                )
            return LlmResponse(text="2 ngay. Nguồn: TL02.")

    config = registry(tmp_path)
    data = yaml.safe_load(config.read_text(encoding="utf-8"))
    data["departments"][0]["modules"][0]["profile"] = "assessment"
    config.write_text(yaml.safe_dump(data), encoding="utf-8")
    retriever = MemoryRetriever(
        [
            GoldHit(
                chunk_id="gold:aaaaaaaaaaaaaaaaaaaaaaaa",
                entity_type="regulation",
                score=1,
                boosted_score=1,
                stair_markdown="Phuc khao DHCQ 2 ngay tren Portal UEL.",
                payload={"document_code": "TL02"},
            )
        ]
    )
    rules = Rules()
    rules.scope = "answer_allowed"
    runtime = AgentRuntime(
        AgentDeps(Dual(), MemoryFaqStore([]), retriever, rules=rules, config_path=str(config))
    )
    runtime.invoke(
        "Thời hạn phúc khảo ĐHCQ",
        department_id="alpha",
        module_code="one",
        environment="test",
        conversation_id="assess-retrieve",
    )
    assert retriever.calls
    assert "Portal UEL" in retriever.calls[-1]
