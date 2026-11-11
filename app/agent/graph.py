from __future__ import annotations

import hashlib
import json
import time
import uuid
from collections.abc import Callable, Hashable
from dataclasses import dataclass, field
from typing import Any, TypedDict, cast
from uuid import uuid4

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agent.adversarial import is_adversarial
from app.agent.citation import (
    citations_are_valid,
    citations_from_evidence,
    evidence_from_hit,
    extract_citations,
)
from app.agent.knowledge import FaqStore, Retriever
from app.agent.llm import LlmClient, LlmError, LlmMessage, LlmRequest, LlmTimeoutError
from app.agent.metadata import (
    detect_topic,
    detect_training_system,
    is_fee_question,
    needs_training_system_clarification,
)
from app.agent.models import (
    AnswerStatus,
    ChatResult,
    Citation,
    RetrievedEvidence,
    RoutingScope,
    TrainingSystem,
)
from app.agent.policy import (
    RULE_CLASSIFIER_SYSTEM,
    RULE_SCHEMA,
    RuleStore,
    SilverRuleStore,
    module_generate_system,
)
from app.agent.prompts import (
    METADATA_SCHEMA,
    METADATA_SYSTEM,
    ROUTING_SCHEMA,
    ROUTING_SYSTEM,
    SYSTEM_GENERATE,
    extractive_fallback,
    fallback_evidence,
    generate_user_prompt,
)
from app.agent.routing import is_greeting, keyword_scope
from app.agent.templates import (
    ADVERSARIAL_ANSWER,
    CLARIFICATION_ANSWER,
    FEE_UNKNOWN_ANSWER,
    GREETING_ANSWER,
    HANDOFF_NO_FAQ,
    INSUFFICIENT_ANSWER,
    OUT_OF_SCOPE_ANSWER,
    PROVIDER_ERROR_ANSWER,
    TIMEOUT_ANSWER,
    with_contact,
)
from app.ingestion.contact import ResolvedContact
from app.ingestion.normalize import normalize_question


class AgentState(TypedDict, total=False):
    rule_release_id: str
    routing_aliases: dict[str, list[str]]
    module_name: str
    department_name: str
    profile: str
    rule_id: str
    rule_version: str
    rule_contact: dict[str, Any]
    request_id: str
    department_id: str
    module_code: str
    environment: str
    message: str
    normalized_message: str
    effective_query: str
    pending_clarification: bool
    clarification_base_query: str
    routing_scope: str
    routing_source: str
    faq_question_code: str
    faq_answer: str
    training_system: str
    topic: str
    is_fee_question: bool
    retrieved: list[dict[str, Any]]
    answer: str
    status: str
    citations: list[dict[str, str]]
    support_contact: str
    contact_information: str
    online_channel: str
    error_message: str
    node_latency_ms: dict[str, float]
    llm_calls: list[str]
    search_called: bool
    generate_called: bool
    next_node: str


@dataclass
class AgentDeps:
    llm: LlmClient
    faqs: FaqStore
    retriever: Retriever
    top_k: int = 5
    score_threshold: float = 0.4167
    rules: RuleStore | None = None
    config_path: str = "configs/departments.yaml"
    legacy_mode: bool = False


@dataclass
class AgentRuntime:
    deps: AgentDeps
    checkpointer: MemorySaver = field(default_factory=MemorySaver)

    def __post_init__(self) -> None:
        self._app = build_graph(self.deps).compile(checkpointer=self.checkpointer)

    @classmethod
    def from_settings(
        cls,
        settings: Any | None = None,
        *,
        llm: LlmClient | None = None,
        faqs: FaqStore | None = None,
        retriever: Retriever | None = None,
    ) -> AgentRuntime:
        from sqlalchemy.orm import sessionmaker

        from app.agent.knowledge import SilverFaqStore
        from app.agent.llm import load_llm
        from app.core.config import Settings
        from app.gold.indexer import GoldIndexer
        from app.repositories.silver import create_sync_engine

        resolved = settings or Settings()
        engine = create_sync_engine(resolved)
        factory = sessionmaker(engine, expire_on_commit=False)
        return cls(
            AgentDeps(
                llm=llm or load_llm(resolved),
                faqs=faqs or SilverFaqStore(factory),
                retriever=retriever or GoldIndexer.from_settings(resolved),
                top_k=resolved.rag_top_k,
                score_threshold=resolved.rag_score_threshold,
                rules=SilverRuleStore(factory),
                config_path=resolved.departments_config_path,
            )
        )

    def invoke(
        self,
        message: str,
        *,
        department_id: str,
        module_code: str,
        environment: str,
        conversation_id: str | None = None,
        principal_id: str = "cli",
    ) -> ChatResult:
        thread_id = hashlib.sha256(
            json.dumps(
                [
                    department_id,
                    module_code,
                    environment,
                    principal_id,
                    conversation_id or str(uuid4()),
                ]
            ).encode()
        ).hexdigest()
        context: dict[str, Any] = {}
        if not self.deps.legacy_mode:
            from pathlib import Path

            from app.ingestion.manifest import load_department_configs, resolve_module

            department, module = resolve_module(
                load_department_configs(Path(self.deps.config_path)), department_id, module_code
            )
            context = {
                "department_name": department.name,
                "module_name": module.name,
                "profile": module.profile,
                "routing_aliases": module.routing_aliases,
            }
        state = self._app.invoke(
            {
                "message": message,
                "department_id": department_id,
                "module_code": module_code,
                "environment": environment,
                **context,
            },
            config={"configurable": {"thread_id": thread_id}},
        )
        return _result_from_state(cast(AgentState, state))


def build_graph(deps: AgentDeps) -> StateGraph[AgentState]:
    nodes = _Nodes(deps)
    graph: StateGraph[AgentState] = StateGraph(AgentState)
    for name, fn in nodes.mapping().items():
        graph.add_node(name, fn)  # type: ignore[call-overload]
    graph.add_edge(START, "normalize_input")
    destinations: dict[Hashable, str] = {name: name for name in nodes.mapping()}
    destinations["__end__"] = END
    for name in nodes.mapping():
        if name == "format_response":
            graph.add_edge("format_response", END)
            continue
        graph.add_conditional_edges(name, _dispatch, destinations)
    return graph


def _dispatch(state: AgentState) -> str:
    nxt = state.get("next_node") or "format_response"
    if nxt in {"end", "__end__"}:
        return "__end__"
    return nxt


class _Nodes:
    def __init__(self, deps: AgentDeps) -> None:
        self.deps = deps

    def mapping(self) -> dict[str, Callable[[AgentState], AgentState]]:
        return {
            "normalize_input": self._timed("normalize_input", self.normalize_input),
            "adversarial_check": self._timed("adversarial_check", self.adversarial_check),
            "routing_check": self._timed("routing_check", self.routing_check),
            "faq_match": self._timed("faq_match", self.faq_match),
            "human_handoff": self._timed("human_handoff", self.human_handoff),
            "out_of_scope": self._timed("out_of_scope", self.out_of_scope),
            "clarification_check": self._timed("clarification_check", self.clarification_check),
            "metadata_extract": self._timed("metadata_extract", self.metadata_extract),
            "retrieve": self._timed("retrieve", self.retrieve),
            "evidence_gate": self._timed("evidence_gate", self.evidence_gate),
            "generate": self._timed("generate", self.generate),
            "citation_verify": self._timed("citation_verify", self.citation_verify),
            "format_response": self._timed("format_response", self.format_response),
        }

    def _timed(
        self, name: str, fn: Callable[[AgentState], AgentState]
    ) -> Callable[[AgentState], AgentState]:
        def wrapped(state: AgentState) -> AgentState:
            started = time.perf_counter()
            updated = fn(state)
            latency = dict(updated.get("node_latency_ms") or state.get("node_latency_ms") or {})
            latency[name] = round((time.perf_counter() - started) * 1000, 1)
            updated["node_latency_ms"] = latency
            return updated

        return wrapped

    def normalize_input(self, state: AgentState) -> AgentState:
        message = (state.get("message") or "").strip()
        pending = bool(state.get("pending_clarification"))
        base = state.get("clarification_base_query") or ""
        if pending and base and message:
            effective = f"{base} {message}".strip()
        else:
            effective = message
        out: AgentState = {
            **state,
            "request_id": str(uuid.uuid4()),
            "normalized_message": normalize_question(effective) if effective else "",
            "effective_query": effective,
            "routing_scope": "",
            "routing_source": "",
            "rule_id": "",
            "rule_version": "",
            "rule_release_id": "",
            "rule_contact": {},
            "faq_question_code": "",
            "faq_answer": "",
            "training_system": "unknown",
            "topic": "other",
            "is_fee_question": False,
            "retrieved": [],
            "answer": "",
            "status": "error",
            "citations": [],
            "support_contact": "",
            "contact_information": "",
            "online_channel": "",
            "error_message": "",
            "llm_calls": [],
            "search_called": False,
            "generate_called": False,
            "node_latency_ms": {},
        }
        if not effective:
            out["answer"] = "Câu hỏi trống."
            out["next_node"] = "format_response"
            return out
        out["next_node"] = "adversarial_check"
        return out

    def adversarial_check(self, state: AgentState) -> AgentState:
        if is_adversarial(state.get("message") or "") or is_adversarial(
            state.get("effective_query") or ""
        ):
            state["status"] = "error"
            state["answer"] = ADVERSARIAL_ANSWER
            if not self.deps.legacy_mode:
                state["answer"] = (
                    "Yêu cầu này không được hỗ trợ. Vui lòng hỏi thông tin trong phạm vi mô-đun."
                )
            state["error_message"] = "adversarial"
            state["next_node"] = "format_response"
            return state
        query = state.get("effective_query") or ""
        if not state.get("pending_clarification") and is_greeting(query):
            state["status"] = "greeting"
            state["answer"] = GREETING_ANSWER
            if not self.deps.legacy_mode:
                state["answer"] = (
                    f"Xin chào. Tôi là trợ lý {state.get('module_name')} "
                    f"— {state.get('department_name')}. Bạn cần hỗ trợ nội dung nào?"
                )
            state["routing_scope"] = "answer_allowed"
            state["routing_source"] = "greeting"
            state["next_node"] = "format_response"
            return state
        state["next_node"] = "routing_check"
        return state

    def routing_check(self, state: AgentState) -> AgentState:
        if not self.deps.legacy_mode:
            return self._policy_route(state)
        query = state.get("effective_query") or ""
        scope = keyword_scope(query)
        source = "keyword"
        if scope is None:
            scope, source = self._llm_route(state, query)
        state["routing_scope"] = scope
        state["routing_source"] = source
        if scope == "out_of_scope":
            state["next_node"] = "out_of_scope"
            return state
        state["next_node"] = "faq_match"
        return state

    def _policy_route(self, state: AgentState) -> AgentState:
        rules = (
            self.deps.rules.load(state["department_id"], state["module_code"], state["environment"])
            if self.deps.rules is not None
            else []
        )
        aliases = state.get("routing_aliases", {})
        query = normalize_question(state.get("effective_query") or "")
        exact = [
            r
            for r in rules
            if query in {normalize_question(text) for text in [r.topic, *aliases.get(r.id, [])]}
        ]
        selected = exact[0] if len(exact) == 1 else None
        if rules and not exact:
            try:
                response = self.deps.llm.complete(
                    LlmRequest(
                        purpose="routing",
                        json_schema=RULE_SCHEMA,
                        messages=[
                            LlmMessage(role="system", content=RULE_CLASSIFIER_SYSTEM),
                            LlmMessage(
                                role="user",
                                content=json.dumps(
                                    {
                                        "module": state.get("module_name"),
                                        "rules": [
                                            {
                                                "id": r.id,
                                                "scope": r.scope,
                                                "topic": r.topic,
                                                "behavior": r.behavior,
                                            }
                                            for r in rules
                                        ],
                                        "question": state.get("effective_query"),
                                    },
                                    ensure_ascii=False,
                                ),
                            ),
                        ],
                    )
                )
                _note_llm(state, "routing")
                selected = next(
                    (r for r in rules if r.id == (response.parsed or {}).get("rule_id")), None
                )
            except LlmError:
                _note_llm(state, "routing")
        if selected is None:
            state["status"] = "clarification_required" if rules else "human_handoff"
            state["answer"] = (
                "Chưa xác định chắc chắn phạm vi hỗ trợ. "
                "Vui lòng mô tả rõ yêu cầu hoặc liên hệ đơn vị phụ trách."
            )
            state["routing_source"] = "policy_unresolved"
            state["next_node"] = "format_response"
            return state
        state["rule_id"], state["rule_version"] = selected.id, selected.version
        state["rule_release_id"] = selected.release_id
        state["routing_scope"], state["routing_source"] = selected.scope, "template_policy"
        if selected.contact_verified or state["environment"] in {"development", "test"}:
            state["rule_contact"] = selected.model_dump()
        state["next_node"] = "out_of_scope" if selected.scope == "out_of_scope" else "faq_match"
        return state

    def _llm_route(self, state: AgentState, query: str) -> tuple[RoutingScope, str]:
        try:
            response = self.deps.llm.complete(
                LlmRequest(
                    purpose="routing",
                    messages=[
                        LlmMessage(role="system", content=ROUTING_SYSTEM),
                        LlmMessage(role="user", content=query),
                    ],
                    json_schema=ROUTING_SCHEMA,
                )
            )
            _note_llm(state, "routing")
            parsed = response.parsed or {}
            value = str(parsed.get("scope_type") or "")
            if value in {"answer_allowed", "human_required", "out_of_scope"}:
                return value, "llm"  # type: ignore[return-value]
        except LlmError:
            _note_llm(state, "routing")
        return "answer_allowed", "llm_default"

    def faq_match(self, state: AgentState) -> AgentState:
        match = self.deps.faqs.match_normalized(
            department_id=state["department_id"],
            module_code=state["module_code"],
            normalized_question=state.get("normalized_message") or "",
            environment=state["environment"],
        )
        if match is not None:
            state["faq_question_code"] = match.question_code
            state["faq_answer"] = match.answer
            state["citations"] = [
                Citation(kind="question_code", value=match.question_code).model_dump()
            ]
            if state.get("routing_scope") == "human_required":
                state["next_node"] = "human_handoff"
                return state
            state["status"] = "faq_answered"
            state["answer"] = match.answer
            state["next_node"] = "format_response"
            return state
        if state.get("routing_scope") == "human_required":
            state["next_node"] = "human_handoff"
            return state
        state["next_node"] = "clarification_check"
        return state

    def human_handoff(self, state: AgentState) -> AgentState:
        contact = self._contact(state)
        _apply_contact(state, contact)
        faq_answer = state.get("faq_answer") or ""
        if faq_answer:
            body = (
                f"{faq_answer}\n\n{HANDOFF_NO_FAQ} Bot không kết luận dữ liệu cá nhân "
                "kể cả khi có FAQ hướng dẫn chung."
            )
        else:
            body = HANDOFF_NO_FAQ
        state["status"] = "human_handoff"
        state["answer"] = with_contact(body, contact)
        state["next_node"] = "format_response"
        return state

    def out_of_scope(self, state: AgentState) -> AgentState:
        state["status"] = "out_of_scope"
        state["answer"] = OUT_OF_SCOPE_ANSWER
        if not self.deps.legacy_mode:
            contact = self._contact(state)
            _apply_contact(state, contact)
            state["answer"] = with_contact(
                f"Yêu cầu nằm ngoài phạm vi {state.get('module_name')}. "
                "Vui lòng liên hệ đơn vị phụ trách.",
                contact,
            )
        state["next_node"] = "format_response"
        return state

    def clarification_check(self, state: AgentState) -> AgentState:
        if not self.deps.legacy_mode and state.get("profile") != "assessment":
            state["next_node"] = "retrieve"
            return state
        query = state.get("effective_query") or ""
        if needs_training_system_clarification(query):
            state["pending_clarification"] = True
            state["clarification_base_query"] = query
            state["status"] = "clarification_required"
            state["answer"] = CLARIFICATION_ANSWER
            state["next_node"] = "format_response"
            return state
        state["pending_clarification"] = False
        state["clarification_base_query"] = ""
        state["next_node"] = "metadata_extract"
        return state

    def metadata_extract(self, state: AgentState) -> AgentState:
        query = state.get("effective_query") or ""
        training = detect_training_system(query)
        topic = detect_topic(query)
        fee = is_fee_question(query)
        if topic == "other":
            try:
                response = self.deps.llm.complete(
                    LlmRequest(
                        purpose="metadata",
                        messages=[
                            LlmMessage(role="system", content=METADATA_SYSTEM),
                            LlmMessage(role="user", content=query),
                        ],
                        json_schema=METADATA_SCHEMA,
                    )
                )
                _note_llm(state, "metadata")
                parsed = response.parsed or {}
                llm_training = str(parsed.get("training_system") or training)
                llm_topic = str(parsed.get("topic") or topic)
                if llm_training in {"dhcq", "sdh", "vb2_vlvh", "unknown"}:
                    training = llm_training  # type: ignore[assignment]
                if llm_topic in {
                    "phuc_khao",
                    "diem_i_nhan",
                    "diem_i_tra",
                    "seb",
                    "hinh_thuc_thi",
                    "fee",
                    "other",
                }:
                    topic = llm_topic  # type: ignore[assignment]
                if "is_fee_question" in parsed:
                    fee = bool(parsed["is_fee_question"]) or fee
            except LlmError:
                _note_llm(state, "metadata")
        state["training_system"] = training
        state["topic"] = topic
        state["is_fee_question"] = fee
        if fee or topic == "fee":
            state["status"] = "insufficient_evidence"
            state["answer"] = FEE_UNKNOWN_ANSWER
            state["next_node"] = "format_response"
            return state
        state["next_node"] = "retrieve"
        return state

    def retrieve(self, state: AgentState) -> AgentState:
        state["search_called"] = True
        hits = self.deps.retriever.search(
            state.get("effective_query") or "",
            department_id=state["department_id"],
            module_code=state["module_code"],
            environment=state["environment"],
            limit=self.deps.top_k,
            mode="hybrid",
        )
        kept = [
            evidence_from_hit(hit)
            for hit in hits
            if hit.boosted_score >= self.deps.score_threshold
            and (
                not state.get("rule_release_id")
                or hit.payload.get("release_id") == state["rule_release_id"]
            )
        ][: self.deps.top_k]
        state["retrieved"] = [item.model_dump() for item in kept]
        state["next_node"] = "evidence_gate"
        return state

    def evidence_gate(self, state: AgentState) -> AgentState:
        evidence = _load_evidence(state)
        if state.get("profile", "assessment") == "assessment":
            from app.agent.assessment import apply_evidence_policy

            if apply_evidence_policy(state, evidence):
                return state
        if any(item.fee_type == "unknown" for item in evidence) and (
            state.get("is_fee_question") or state.get("topic") == "fee"
        ):
            state["status"] = "insufficient_evidence"
            state["answer"] = FEE_UNKNOWN_ANSWER
            state["next_node"] = "format_response"
            return state
        if not evidence:
            state["status"] = "insufficient_evidence"
            state["answer"] = INSUFFICIENT_ANSWER
            state["next_node"] = "format_response"
            return state
        state["next_node"] = "generate"
        return state

    def generate(self, state: AgentState) -> AgentState:
        evidence = _load_evidence(state)
        try:
            response = self.deps.llm.complete(
                LlmRequest(
                    purpose="generate",
                    messages=[
                        LlmMessage(
                            role="system",
                            content=(
                                SYSTEM_GENERATE
                                if self.deps.legacy_mode
                                else module_generate_system(
                                    state.get("module_name", ""), state.get("department_name", "")
                                )
                            ),
                        ),
                        LlmMessage(
                            role="user",
                            content=generate_user_prompt(
                                state.get("effective_query") or "",
                                evidence,
                                _as_training(state.get("training_system")),
                            ),
                        ),
                    ],
                    timeout_seconds=20,
                )
            )
            _note_llm(state, "generate")
            state["generate_called"] = True
            state["answer"] = response.text.strip()
            state["next_node"] = "citation_verify"
            return state
        except LlmError as exc:
            _note_llm(state, "generate")
            state["generate_called"] = True
            state["error_message"] = str(exc)
            if fallback_evidence(evidence):
                state["answer"] = extractive_fallback(evidence)
                state["citations"] = [
                    item.model_dump()
                    for item in citations_from_evidence(fallback_evidence(evidence))
                ]
                state["status"] = "answered"
                state["next_node"] = "format_response"
                return state
            state["status"] = "error"
            state["answer"] = (
                TIMEOUT_ANSWER if isinstance(exc, LlmTimeoutError) else PROVIDER_ERROR_ANSWER
            )
            state["next_node"] = "format_response"
            return state

    def citation_verify(self, state: AgentState) -> AgentState:
        evidence = _load_evidence(state)
        answer = state.get("answer") or ""
        extracted = extract_citations(answer, evidence)
        if citations_are_valid(answer, evidence):
            state["status"] = "answered"
            state["citations"] = [item.model_dump() for item in extracted]
            state["next_node"] = "format_response"
            return state
        readable = fallback_evidence(evidence)
        if readable:
            state["answer"] = extractive_fallback(evidence)
            state["status"] = "answered"
            state["citations"] = [item.model_dump() for item in citations_from_evidence(readable)]
            state["next_node"] = "format_response"
            return state
        state["status"] = "insufficient_evidence"
        state["answer"] = INSUFFICIENT_ANSWER
        state["citations"] = []
        state["next_node"] = "format_response"
        return state

    def format_response(self, state: AgentState) -> AgentState:
        state["next_node"] = "__end__"
        return state

    def _contact(self, state: AgentState) -> ResolvedContact:
        if state.get("rule_contact"):
            contact = state["rule_contact"]
            if any(
                contact.get(k) for k in ("support_contact", "contact_information", "online_channel")
            ):
                return ResolvedContact(
                    support_contact=contact.get("support_contact"),
                    contact_information=contact.get("contact_information"),
                    online_channel=contact.get("online_channel"),
                    source="record",
                    verified=bool(contact.get("contact_verified")),
                )
        return self.deps.faqs.load_contact(
            department_id=state["department_id"],
            module_code=state["module_code"],
            environment=state["environment"],
        )


def _note_llm(state: AgentState, purpose: str) -> None:
    calls = list(state.get("llm_calls") or [])
    calls.append(purpose)
    state["llm_calls"] = calls


def _apply_contact(state: AgentState, contact: ResolvedContact) -> None:
    state["support_contact"] = contact.support_contact or ""
    state["contact_information"] = contact.contact_information or ""
    state["online_channel"] = contact.online_channel or ""


def _load_evidence(state: AgentState) -> list[RetrievedEvidence]:
    return [RetrievedEvidence.model_validate(item) for item in state.get("retrieved") or []]


def _as_training(value: str | None) -> TrainingSystem:
    if value in {"dhcq", "sdh", "vb2_vlvh", "unknown"}:
        return value  # type: ignore[return-value]
    return "unknown"


def _result_from_state(state: AgentState) -> ChatResult:
    citations = [Citation.model_validate(item) for item in state.get("citations") or []]
    status = state.get("status") or "error"
    valid_status: AnswerStatus
    if status in {
        "faq_answered",
        "answered",
        "greeting",
        "human_handoff",
        "out_of_scope",
        "insufficient_evidence",
        "clarification_required",
        "error",
    }:
        valid_status = status  # type: ignore[assignment]
    else:
        valid_status = "error"
    return ChatResult(
        request_id=state.get("request_id") or "",
        status=valid_status,
        answer=state.get("answer") or "",
        citations=citations,
        routing_scope=state.get("routing_scope") or None,
        routing_source=state.get("routing_source") or None,
        rule_id=state.get("rule_id") or None,
        rule_version=state.get("rule_version") or None,
        support_contact=state.get("support_contact") or None,
        contact_information=state.get("contact_information") or None,
        online_channel=state.get("online_channel") or None,
        node_latency_ms=dict(state.get("node_latency_ms") or {}),
        llm_calls=list(state.get("llm_calls") or []),
        search_called=bool(state.get("search_called")),
        generate_called=bool(state.get("generate_called")),
        faq_question_code=state.get("faq_question_code") or None,
        error_message=state.get("error_message") or None,
    )
