from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)

from app.ingestion.normalize import normalize_question
from app.integrations.embeddings import embed_texts
from app.integrations.qdrant import COL_RULES
from app.repositories import catalog
from app.services import llm as llm_svc
from app.services.rag import citations_of, generate_answer, retrieve_docs


@dataclass
class RouteResult:
    answer: str
    routing_source: str
    status: str
    module_code: str | None = None
    release_id: str | None = None
    rule_id: str | None = None
    citations: list[dict[str, str]] = field(default_factory=list)
    contact_info: dict[str, str] | None = None
    interactive: dict[str, Any] | None = None
    llm_tokens: int = 0


def resolve_module_code(department: dict, *, mode: str | None, module_code: str | None) -> str | None:
    mods = department.get("modules") or []
    if module_code:
        return module_code
    if mode and str(mode).startswith("module_"):
        try:
            idx = int(str(mode).split("_", 1)[1]) - 1
        except ValueError:
            idx = 0
        if 0 <= idx < len(mods):
            return mods[idx].get("code")
    if mods:
        return mods[0].get("code")
    return None


def _form(department: dict) -> dict[str, Any] | None:
    url = (department.get("handoff_form_url") or "").strip()
    if not url:
        return None
    return {"kind": "form", "url": url, "label": "Mở form hỗ trợ"}


def _contact(rule: dict[str, Any], header: dict[str, Any] | None = None) -> dict[str, str] | None:
    name = rule.get("contact_name") or (header or {}).get("default_contact_name") or ""
    info = rule.get("contact_info") or (header or {}).get("default_contact_info") or ""
    channel = rule.get("channel") or ""
    if not (name or info or channel):
        return None
    out: dict[str, str] = {}
    if name:
        out["person"] = str(name)
    if info:
        out["email"] = str(info)
    if channel:
        out["department"] = str(channel)
    return out


def _match_faq(db, *, module_code: str, release_id: str, query: str) -> dict[str, Any] | None:
    norm = normalize_question(query)
    rows = catalog.find_docs(db, "faqs", {"module_code": module_code, "release_id": release_id})
    for row in rows:
        if row.get("is_active") is False:
            continue
        if row.get("question_norm") == norm:
            return row
    return None


def _match_regex(patterns: list[dict[str, Any]], query: str, rules: dict[str, dict]) -> dict[str, Any] | None:
    for item in patterns or []:
        pattern = item.get("pattern") or ""
        rule_id = item.get("rule_id") or ""
        if not pattern or rule_id not in rules:
            continue
        try:
            if re.search(pattern, query):
                return rules[rule_id]
        except re.error:
            continue
    return None


def _cosine_rule(qdrant, *, vector: list[float], module_code: str, release_id: str, threshold: float) -> dict[str, Any] | None:
    if qdrant is None:
        return None
    hits = qdrant.search(
        COL_RULES,
        vector,
        limit=2,
        filt={"module_code": module_code, "release_id": release_id},
    )
    if not hits:
        return None
    top = hits[0]
    if float(top.get("score") or 0) < threshold:
        return None
    if len(hits) > 1 and abs(float(hits[0]["score"]) - float(hits[1]["score"])) < 1e-6:
        return None
    return top


def _llm_rule(*, settings, query: str, rules: list[dict[str, Any]]) -> tuple[str | None, int]:
    opts = llm_svc.options_from_settings(settings)
    allowed = {r["rule_id"] for r in rules if r.get("rule_id")}
    if not opts["api_key"] or not allowed:
        return None, 0
    listing = "\n".join(f"- {r['rule_id']}: {r.get('topic')}" for r in rules)
    text, tokens = llm_svc.chat_complete(
        **opts,
        messages=[
            {
                "role": "system",
                "content": 'Chỉ trả JSON {"rule_id":"..."} với rule_id trong danh sách, hoặc {"rule_id": null}. Không giải thích.',
            },
            {"role": "user", "content": f"Câu hỏi: {query}\n\nDanh sách:\n{listing}"},
        ],
        max_tokens=80,
    )
    return llm_svc.parse_rule_id(text, allowed), tokens


def route_message(
    *,
    db,
    qdrant,
    department: dict,
    persona: dict,
    settings,
    message: str,
    module_code: str,
) -> RouteResult:
    release = catalog.get_active_release(db, module_code) if db is not None else None
    release_id = (release or {}).get("release_id")
    header = (release or {}).get("header") or {}
    if not release_id:
        return RouteResult(
            answer=persona.get("clarification") or "Chưa có dữ liệu đã nạp cho mô-đun này.",
            routing_source="llm_clarify",
            status="clarification_required",
            module_code=module_code,
        )
    faq = _match_faq(db, module_code=module_code, release_id=release_id, query=message)
    if faq:
        return RouteResult(
            answer=str(faq.get("answer") or ""),
            routing_source="faq_exact",
            status="faq_exact",
            module_code=module_code,
            release_id=release_id,
            citations=[{"source": "faq", "document_name": str(faq.get("question_code") or ""), "kind": "faq"}],
        )

    rules = catalog.find_docs(db, "routing_rules", {"module_code": module_code, "release_id": release_id})
    by_id = {r.get("rule_id"): r for r in rules if r.get("rule_id")}
    chosen = _match_regex(persona.get("routing_regex") or [], message, by_id)
    source = "regex" if chosen else ""
    tokens = 0
    vector: list[float] | None = None

    def query_vector() -> list[float]:
        nonlocal vector
        if vector is None:
            vector = embed_texts(
                [message],
                dim=getattr(settings, "embed_dim", 1024),
                backend=getattr(settings, "embed_backend", "hash"),
            )[0]
        return vector

    if not chosen:
        threshold = float(persona.get("cosine_threshold") or 0.62)
        try:
            hit = _cosine_rule(
                qdrant,
                vector=query_vector(),
                module_code=module_code,
                release_id=release_id,
                threshold=threshold,
            )
        except Exception:
            log.exception("Cosine File 01 failed")
            hit = None
        if hit and hit.get("rule_id") in by_id:
            chosen = by_id[hit["rule_id"]]
            source = "cosine"
        else:
            rid, tokens = _llm_rule(
                settings=settings,
                query=message,
                rules=rules,
            )
            if rid and rid in by_id:
                chosen = by_id[rid]
                source = "llm"
            else:
                return RouteResult(
                    answer=str(persona.get("clarification") or "Bạn đang hỏi điều gì?"),
                    routing_source="llm_clarify",
                    status="clarification_required",
                    module_code=module_code,
                    release_id=release_id,
                    llm_tokens=tokens,
                )

    scope = chosen.get("scope_code") or ""
    if scope in {"human_handoff", "out_of_scope"}:
        if scope == "out_of_scope":
            answer = str(persona.get("out_of_scope") or chosen.get("bot_behavior") or "")
        else:
            answer = str(chosen.get("bot_behavior") or persona.get("out_of_scope") or "")
        return RouteResult(
            answer=answer.strip(),
            routing_source=source,
            status=scope,
            module_code=module_code,
            release_id=release_id,
            rule_id=chosen.get("rule_id"),
            contact_info=_contact(chosen, header),
            interactive=_form(department),
            llm_tokens=tokens,
        )

    top_k = int(persona.get("top_k") or 6)
    hits = retrieve_docs(
        qdrant,
        vector=query_vector(),
        module_code=module_code,
        release_id=release_id,
        query=message,
        top_k=top_k,
    )
    if not hits:
        return RouteResult(
            answer="Chưa đủ nguồn trong tài liệu đã nạp để trả lời. Không đoán thêm.",
            routing_source=source,
            status="answer_allowed",
            module_code=module_code,
            release_id=release_id,
            rule_id=chosen.get("rule_id"),
            llm_tokens=tokens,
        )
    text, gen_tokens = generate_answer(
        query=message,
        hits=hits,
        persona=persona,
        llm_opts=llm_svc.options_from_settings(settings),
    )
    if not text:
        text = "Chưa đủ nguồn trong tài liệu đã nạp để trả lời. Không đoán thêm."
    return RouteResult(
        answer=text,
        routing_source=source,
        status="answer_allowed",
        module_code=module_code,
        release_id=release_id,
        rule_id=chosen.get("rule_id"),
        citations=citations_of(hits),
        llm_tokens=tokens + gen_tokens,
    )
