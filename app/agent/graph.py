from __future__ import annotations

import hashlib
import json
import time
import uuid
from collections.abc import Callable, Hashable, Iterator
from dataclasses import dataclass, field
from typing import Any, TypedDict, cast
from uuid import uuid4

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agent.adversarial import is_adversarial
from app.agent.citation import (
    answer_distorts_training_labels,
    answer_overlaps_evidence,
    citations_from_evidence,
    evidence_from_hit,
    extract_citations,
    has_invented_citations,
    student_facing_answer,
    with_human_source_footer,
)
from app.agent.knowledge import FaqStore, Retriever
from app.agent.llm import LlmClient, LlmError, LlmMessage, LlmRequest, LlmTimeoutError
from app.agent.metadata import (
    detect_topic,
    detect_training_system,
    detect_training_systems,
    is_fee_question,
    is_training_system_reply,
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
    ScopeRule,
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
    scope_clarification_answer,
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
    bot_role: str
    bot_constraints: str
    bot_glossary_json: str
    bot_answer_style: str
    bot_metadata_system: str
    bot_greeting: str
    bot_out_of_scope: str
    bot_clarification: str
    rag_top_k: int
    rag_score_threshold: float
    rag_mode: str
    rag_faq_boost: float
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
    training_systems: str
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
    search_mode: str = "hybrid"
    rules: RuleStore | None = None
    config_path: str = "configs/departments.yaml"
    legacy_mode: bool = False


@dataclass
class AgentRuntime:
    deps: AgentDeps
    checkpointer: MemorySaver = field(default_factory=MemorySaver)
    _turns: dict[str, dict[str, Any]] = field(default_factory=dict, repr=False)

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
                search_mode=resolved.rag_search_mode,
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
        initial, thread_id = self._prepare(
            message,
            department_id=department_id,
            module_code=module_code,
            environment=environment,
            conversation_id=conversation_id,
            principal_id=principal_id,
        )
        state = cast(
            AgentState,
            self._app.invoke(initial, config={"configurable": {"thread_id": thread_id}}),
        )
        self._store_turn(thread_id, state)
        return _result_from_state(state)

    def iter_progress(
        self,
        message: str,
        *,
        department_id: str,
        module_code: str,
        environment: str,
        conversation_id: str | None = None,
        principal_id: str = "cli",
    ) -> Iterator[tuple[str, ChatResult | None]]:
        initial, thread_id = self._prepare(
            message,
            department_id=department_id,
            module_code=module_code,
            environment=environment,
            conversation_id=conversation_id,
            principal_id=principal_id,
        )
        last: dict[str, Any] = dict(initial)
        for update in self._app.stream(
            initial,
            config={"configurable": {"thread_id": thread_id}},
            stream_mode="updates",
        ):
            for name, payload in update.items():
                if isinstance(payload, dict):
                    last.update(payload)
                yield name, None
        self._store_turn(thread_id, last)
        yield "__result__", _result_from_state(cast(AgentState, last))

    def _prepare(
        self,
        message: str,
        *,
        department_id: str,
        module_code: str,
        environment: str,
        conversation_id: str | None,
        principal_id: str,
    ) -> tuple[AgentState, str]:
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
                "bot_role": module.prompt_pack.role,
                "bot_constraints": module.prompt_pack.constraints,
                "bot_glossary_json": json.dumps(module.prompt_pack.glossary, ensure_ascii=False),
                "bot_answer_style": module.prompt_pack.answer_style,
                "bot_metadata_system": module.prompt_pack.metadata_system,
                "bot_greeting": module.messages.greeting,
                "bot_out_of_scope": module.messages.out_of_scope,
                "bot_clarification": module.messages.clarification,
            }
            if module.retrieval.top_k is not None:
                context["rag_top_k"] = module.retrieval.top_k
            if module.retrieval.score_threshold is not None:
                context["rag_score_threshold"] = module.retrieval.score_threshold
            if module.retrieval.mode is not None:
                context["rag_mode"] = module.retrieval.mode
            if module.retrieval.faq_boost is not None:
                context["rag_faq_boost"] = module.retrieval.faq_boost
        prior = self._turns.get(thread_id) or {}
        initial = cast(
            AgentState,
            {
                "message": message,
                "department_id": department_id,
                "module_code": module_code,
                "environment": environment,
                "pending_clarification": bool(prior.get("pending_clarification")),
                "clarification_base_query": prior.get("clarification_base_query") or "",
                "effective_query": prior.get("effective_query") or "",
                **context,
            },
        )
        return initial, thread_id

    def _store_turn(self, thread_id: str, state: dict[str, Any]) -> None:
        self._turns[thread_id] = {
            "pending_clarification": bool(state.get("pending_clarification")),
            "clarification_base_query": state.get("clarification_base_query") or "",
            "effective_query": state.get("effective_query") or "",
        }
        if len(self._turns) > 256:
            self._turns.pop(next(iter(self._turns)), None)


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
        base = (state.get("clarification_base_query") or "").strip()
        previous = (base or state.get("effective_query") or "").strip()
        followup = bool(message and previous and message.casefold() != previous.casefold())
        short_reply = len(message.split()) <= 4
        if pending and followup and (is_training_system_reply(message) or short_reply):
            effective = f"{previous} {message}".strip()
        elif (
            followup
            and is_training_system_reply(message)
            and not is_training_system_reply(previous)
        ):
            effective = f"{previous} {message}".strip()
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
            "training_systems": "",
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
                custom = (state.get("bot_greeting") or "").strip()
                state["answer"] = custom or (
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
        faq_hit = self.deps.faqs.match_normalized(
            department_id=state["department_id"],
            module_code=state["module_code"],
            normalized_question=state.get("normalized_message") or "",
            environment=state["environment"],
        )
        if faq_hit is not None:
            state["routing_scope"] = "answer_allowed"
            state["routing_source"] = "faq_exact"
            state["next_node"] = "faq_match"
            return state
        query_text = state.get("effective_query") or ""
        if _uses_assessment(state, legacy_mode=self.deps.legacy_mode) and is_fee_question(
            query_text
        ):
            contact = self._contact(state)
            _apply_contact(state, contact)
            state["status"] = "insufficient_evidence"
            state["answer"] = with_contact(FEE_UNKNOWN_ANSWER, contact)
            state["routing_scope"] = "answer_allowed"
            state["routing_source"] = "fee_keyword"
            state["is_fee_question"] = True
            state["topic"] = "fee"
            state["next_node"] = "format_response"
            return state
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
            selected = _rule_by_topic_overlap(query, rules)
        if selected is None:
            query_text = state.get("effective_query") or ""
            if state.get("profile") == "assessment" and not needs_training_system_clarification(
                query_text
            ):
                state["routing_scope"] = "answer_allowed"
                state["routing_source"] = "policy_fallback_retrieve"
                state["next_node"] = "faq_match"
                return state
            contact = self._contact(state)
            _apply_contact(state, contact)
            state["pending_clarification"] = True
            state["clarification_base_query"] = query_text
            state["status"] = "clarification_required" if rules else "human_handoff"
            state["answer"] = with_contact(_unresolved_guidance(self.deps, state, rules), contact)
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
            custom = (state.get("bot_out_of_scope") or "").strip()
            state["answer"] = with_contact(
                custom
                or (
                    f"Yêu cầu nằm ngoài phạm vi {state.get('module_name')}. "
                    "Vui lòng liên hệ đơn vị phụ trách."
                ),
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
            custom = (state.get("bot_clarification") or "").strip()
            state["answer"] = custom or CLARIFICATION_ANSWER
            state["next_node"] = "format_response"
            return state
        state["pending_clarification"] = False
        state["clarification_base_query"] = ""
        state["next_node"] = "metadata_extract"
        return state

    def metadata_extract(self, state: AgentState) -> AgentState:
        query = state.get("effective_query") or ""
        found_systems = detect_training_systems(query)
        if "vb2_vlvh" in found_systems:
            training = "vb2_vlvh"
        elif len(found_systems) == 1:
            training = found_systems[0]
        else:
            training = detect_training_system(query)
        topic = detect_topic(query)
        fee = is_fee_question(query)
        metadata_system = (state.get("bot_metadata_system") or "").strip()
        if not metadata_system and (
            state.get("profile") == "assessment" or self.deps.legacy_mode
        ):
            metadata_system = METADATA_SYSTEM
        if topic == "other" and metadata_system:
            try:
                response = self.deps.llm.complete(
                    LlmRequest(
                        purpose="metadata",
                        messages=[
                            LlmMessage(role="system", content=metadata_system),
                            LlmMessage(role="user", content=query),
                        ],
                        json_schema=METADATA_SCHEMA,
                    )
                )
                _note_llm(state, "metadata")
                parsed = response.parsed or {}
                llm_training = str(parsed.get("training_system") or training)
                llm_topic = str(parsed.get("topic") or topic)
                if not found_systems and llm_training in {
                    "dhcq",
                    "sdh",
                    "vb2_vlvh",
                    "unknown",
                }:
                    training = llm_training  # type: ignore[assignment]
                    if llm_training in {"dhcq", "sdh", "vb2_vlvh"}:
                        found_systems = [llm_training]
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
        state["training_systems"] = ",".join(found_systems)
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
        limit = int(state["rag_top_k"]) if state.get("rag_top_k") else self.deps.top_k
        threshold = (
            float(state["rag_score_threshold"])
            if "rag_score_threshold" in state
            else self.deps.score_threshold
        )
        hits = self.deps.retriever.search(
            _retrieval_query(state, legacy_mode=self.deps.legacy_mode),
            department_id=state["department_id"],
            module_code=state["module_code"],
            environment=state["environment"],
            limit=limit,
            mode=str(state.get("rag_mode") or self.deps.search_mode or "hybrid"),
            faq_boost=state.get("rag_faq_boost"),
        )
        kept = [
            evidence_from_hit(hit)
            for hit in hits
            if hit.boosted_score >= threshold
            and (
                not state.get("rule_release_id")
                or hit.payload.get("release_id") == state["rule_release_id"]
            )
        ][:limit]
        state["retrieved"] = [item.model_dump() for item in kept]
        state["next_node"] = "evidence_gate"
        return state

    def evidence_gate(self, state: AgentState) -> AgentState:
        evidence = _load_evidence(state)
        if _uses_assessment(state, legacy_mode=self.deps.legacy_mode):
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
                                    state.get("module_name", ""),
                                    state.get("department_name", ""),
                                    role=state.get("bot_role") or "",
                                    constraints=state.get("bot_constraints") or "",
                                    glossary=_glossary_from_state(state),
                                )
                            ),
                        ),
                        LlmMessage(
                            role="user",
                            content=generate_user_prompt(
                                state.get("effective_query") or "",
                                evidence,
                                _as_training(state.get("training_system")),
                                training_systems=_systems_from_state(state),
                                writing_notes=state.get("bot_answer_style") or "",
                                glossary=_glossary_from_state(state),
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
        invented = has_invented_citations(extracted, evidence)
        grounded = (bool(extracted) and not invented) or answer_overlaps_evidence(
            answer, evidence
        )
        labels_ok = True
        if _uses_assessment(state, legacy_mode=self.deps.legacy_mode):
            labels_ok = not answer_distorts_training_labels(
                answer, evidence, training_systems=_systems_from_state(state)
            )
        if labels_ok and not invented and grounded:
            allowed = [
                item
                for item in extracted
                if not has_invented_citations([item], evidence)
            ]
            readable = fallback_evidence(evidence)
            human = [item for item in allowed if item.kind != "chunk_id"]
            state["status"] = "answered"
            state["answer"] = with_human_source_footer(
                student_facing_answer(answer), readable or evidence
            )
            state["citations"] = [
                item.model_dump()
                for item in (
                    human or citations_from_evidence(readable or evidence) or allowed
                )
            ]
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


_OVERLAP_STOP = frozenset(
    {
        "cua",
        "cac",
        "va",
        "voi",
        "cho",
        "trong",
        "theo",
        "mot",
        "nhung",
        "la",
        "duoc",
        "hoac",
        "ve",
        "tai",
        "den",
        "khi",
        "neu",
        "nay",
        "do",
        "to",
        "the",
        "toi",
        "ban",
        "hoi",
        "quy",
        "dinh",
        "quy dinh",
    }
)


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in normalize_question(text).split()
        if len(token) > 2 and token not in _OVERLAP_STOP
    }


def _rule_by_topic_overlap(query: str, rules: list[ScopeRule]) -> ScopeRule | None:
    query_tokens = _tokens(query)
    if not query_tokens or not rules:
        return None
    scored: list[tuple[int, ScopeRule]] = []
    for rule in rules:
        overlap = len(query_tokens & _tokens(rule.topic))
        if overlap:
            scored.append((overlap, rule))
    if not scored:
        return None
    best = max(item[0] for item in scored)
    winners = [rule for overlap, rule in scored if overlap == best]
    if len(winners) != 1:
        return None
    return winners[0]


def _related_faqs(deps: AgentDeps, state: AgentState, query: str) -> list[str]:
    samples = deps.faqs.sample_questions(
        department_id=state["department_id"],
        module_code=state["module_code"],
        environment=state["environment"],
        limit=40,
    )
    query_tokens = _tokens(query)
    ranked: list[tuple[int, str]] = []
    for question in samples:
        overlap = len(query_tokens & _tokens(question))
        if overlap:
            ranked.append((overlap, question))
    ranked.sort(key=lambda item: -item[0])
    return [question for _, question in ranked[:3]]


def _unresolved_guidance(deps: AgentDeps, state: AgentState, rules: list[ScopeRule]) -> str:
    module_name = str(state.get("module_name") or "mô-đun này")
    if not rules:
        return (
            f"Mô-đun **{module_name}** chưa có phạm vi đã duyệt để định tuyến. "
            "Vui lòng liên hệ đơn vị phụ trách."
        )
    query = state.get("effective_query") or ""
    if needs_training_system_clarification(query):
        custom = (state.get("bot_clarification") or "").strip()
        return custom or CLARIFICATION_ANSWER
    return scope_clarification_answer(
        module_name=module_name,
        related_faqs=_related_faqs(deps, state, query),
        assessment=_uses_assessment(state, legacy_mode=deps.legacy_mode),
    )


def _load_evidence(state: AgentState) -> list[RetrievedEvidence]:
    return [RetrievedEvidence.model_validate(item) for item in state.get("retrieved") or []]


def _glossary_from_state(state: AgentState) -> dict[str, str]:
    raw = state.get("bot_glossary_json") or ""
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return {str(key): str(value) for key, value in payload.items()}


def _as_training(value: str | None) -> TrainingSystem:
    if value in {"dhcq", "sdh", "vb2_vlvh", "unknown"}:
        return value  # type: ignore[return-value]
    return "unknown"


def _systems_from_state(state: AgentState) -> list[str]:
    raw = state.get("training_systems") or ""
    found = [item for item in raw.split(",") if item in {"dhcq", "sdh", "vb2_vlvh"}]
    if found:
        return found
    single = state.get("training_system") or ""
    return [single] if single in {"dhcq", "sdh", "vb2_vlvh"} else []


def _uses_assessment(state: AgentState, *, legacy_mode: bool) -> bool:
    """Khảo khí extension. Production: YAML profile=assessment. Tests: legacy_mode."""
    if legacy_mode:
        return True
    return state.get("profile") == "assessment"


def _retrieval_query(state: AgentState, *, legacy_mode: bool = False) -> str:
    query = state.get("effective_query") or ""
    if not _uses_assessment(state, legacy_mode=legacy_mode):
        return query
    topic = state.get("topic") or ""
    folded = query.casefold()
    if topic != "phuc_khao" and "phúc khảo" not in folded and "phuc khao" not in folded:
        return query
    labels = {
        "dhcq": "ĐHCQ đại học chính quy",
        "sdh": "SĐH sau đại học",
        "vb2_vlvh": "VB2 VLVH",
    }
    extras = [labels[item] for item in _systems_from_state(state) if item in labels]
    if not extras:
        extras = ["ĐHCQ SĐH"]
    return f"{query} phúc khảo {' '.join(extras)} Portal UEL"


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
