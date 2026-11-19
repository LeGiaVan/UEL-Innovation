from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)

NO_DATA_ANSWER = (
    "Chưa có dữ liệu đã nạp cho mô-đun này. "
    "Cán bộ phòng cần cập nhật đủ 5 file Excel trên trang Quản lý."
)

from app.ingestion.normalize import normalize_question
from app.integrations.embeddings import embed_texts
from app.integrations.qdrant import COL_RULES
from app.repositories import catalog
from app.services import llm as llm_svc
from app.services.rag import generate_answer, retrieve_docs, strip_source_marks


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


_CONTACT_Q = re.compile(
    r"(?i)liên hệ|hotline|số điện thoại|gọi điện|email (phòng|hỗ trợ)|nhờ ai liên hệ"
)


def _handoff_answer(persona: dict, contact: dict[str, str] | None) -> str:
    base = str(persona.get("handoff") or "").strip()
    if not base:
        base = "Việc này cần cán bộ hỗ trợ. Bạn dùng form bên dưới hoặc liên hệ đầu mối của phòng."
    if not contact:
        return base
    bits = [contact[k] for k in ("person", "email") if contact.get(k)]
    if not bits:
        return base
    return f"{base.rstrip('. ')}. {' · '.join(bits)}."


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


def _cosine_rule(
    qdrant,
    *,
    vector: list[float],
    module_code: str,
    release_id: str,
    threshold: float,
    personal: bool = False,
) -> dict[str, Any] | None:
    if qdrant is None:
        return None
    hits = qdrant.search(
        COL_RULES,
        vector,
        limit=5,
        filt={"module_code": module_code, "release_id": release_id},
    )
    ranked = []
    for hit in hits:
        if float(hit.get("score") or 0) < threshold:
            continue
        scope = str(hit.get("scope_code") or "")
        if not personal and scope == "human_handoff":
            continue
        ranked.append(hit)
    if not ranked:
        return None
    if len(ranked) > 1 and abs(float(ranked[0]["score"]) - float(ranked[1]["score"])) < 1e-6:
        return None
    return ranked[0]


def _format_history(history: list[dict[str, Any]] | None) -> str:
    if not history:
        return ""
    lines = []
    for row in history[-8:]:
        role = "Người hỏi" if row.get("role") == "user" else "Bot"
        text = str(row.get("content") or "").strip()
        if text:
            lines.append(f"{role}: {text[:400]}")
    return "\n".join(lines)


_FOLLOWUP = re.compile(
    r"(?is)(thì sao|thì thế nào|còn hệ|hệ sau đại học|sau đại học thì|"
    r"^vậy\b|^thế\b|còn đhcq|còn sđh|còn với hệ|còn đối với)"
)
_PERSONAL = re.compile(
    r"(?is)(của tôi|của em|của mình|hồ sơ của|điểm của tôi|điểm của em|"
    r"kết quả của tôi|kết quả của em|sai sót thông tin|khuyết tật|"
    r"quốc tịch|vướng mắc|khiếu nại|phản ánh|trường hợp của|"
    r"cá nhân tôi|em bị|tôi bị)"
)


def _looks_like_followup(message: str) -> bool:
    text = (message or "").strip()
    if not text or len(text) > 90:
        return False
    return bool(_FOLLOWUP.search(text))


def _is_personal_case(message: str) -> bool:
    return bool(_PERSONAL.search(message or ""))


def compose_search_query(message: str, history: list[dict[str, Any]] | None) -> str:
    current = (message or "").strip()
    if not history or not _looks_like_followup(current):
        return current
    prior = [str(m.get("content") or "").strip() for m in history if m.get("role") == "user"]
    last = prior[-1] if prior else ""
    if not last or last == current:
        return current
    return f"{last}\n{current}"


def _last_allowed_rule(history: list[dict[str, Any]] | None) -> tuple[str | None, str]:
    if not history:
        return None, ""
    for row in reversed(history):
        if row.get("role") != "assistant":
            continue
        if row.get("status") != "answer_allowed":
            return None, ""
        return row.get("rule_id"), str(row.get("routing_source") or "llm")
    return None, ""


def _llm_rule(
    *,
    settings,
    query: str,
    rules: list[dict[str, Any]],
    history: list[dict[str, Any]] | None = None,
    personal: bool = False,
) -> tuple[str | None, int]:
    opts = llm_svc.options_from_settings(settings)
    pool = rules
    if not personal:
        slim = [r for r in rules if r.get("scope_code") != "human_handoff"]
        if slim:
            pool = slim
    allowed = {r["rule_id"] for r in pool if r.get("rule_id")}
    if not opts["api_key"] or not allowed:
        return None, 0
    listing = "\n".join(
        f"- {r['rule_id']} [{r.get('scope_code') or 'answer_allowed'}]: {r.get('topic')}"
        for r in pool
    )
    hist = _format_history(history)
    user = f"Câu hiện tại: {query}\n\nDanh sách:\n{listing}"
    if hist:
        user = f"Lịch sử:\n{hist}\n\n{user}\n\nCâu ngắn là hỏi tiếp chủ đề lượt trước."
    text, tokens = llm_svc.chat_complete(
        **opts,
        messages=[
            {
                "role": "system",
                "content": (
                    'Chỉ trả JSON {"rule_id":"..."} với rule_id trong danh sách, hoặc {"rule_id": null}. '
                    "Câu hỏi quy định chung (mức, điều kiện, hạn, bao nhiêu, gồm những gì) thì chọn "
                    "answer_allowed khớp chủ đề. human_handoff chỉ khi hỏi hồ sơ/kết quả/vướng mắc "
                    "của một người cụ thể. Không chọn chủ đề 'ngoại ngữ khác' nếu câu hỏi nói tiếng Anh. "
                    "Không giải thích."
                ),
            },
            {"role": "user", "content": user},
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
    history: list[dict[str, Any]] | None = None,
) -> RouteResult:
    release = catalog.get_active_release(db, module_code) if db is not None else None
    release_id = (release or {}).get("release_id")
    header = (release or {}).get("header") or {}
    if not release_id:
        return RouteResult(
            answer=NO_DATA_ANSWER,
            routing_source="no_data",
            status="clarification_required",
            module_code=module_code,
        )
    if _CONTACT_Q.search(message or ""):
        contact = _contact({}, header)
        return RouteResult(
            answer=_handoff_answer(persona, contact),
            routing_source="regex",
            status="human_handoff",
            module_code=module_code,
            release_id=release_id,
            contact_info=contact,
            interactive=_form(department),
        )
    faq = _match_faq(db, module_code=module_code, release_id=release_id, query=message)
    if faq:
        return RouteResult(
            answer=str(faq.get("answer") or ""),
            routing_source="faq_exact",
            status="faq_exact",
            module_code=module_code,
            release_id=release_id,
            citations=[],
        )

    rules = catalog.find_docs(db, "routing_rules", {"module_code": module_code, "release_id": release_id})
    by_id = {r.get("rule_id"): r for r in rules if r.get("rule_id")}
    search_query = compose_search_query(message, history)
    personal = _is_personal_case(message)
    chosen = _match_regex(persona.get("routing_regex") or [], message, by_id)
    source = "regex" if chosen else ""
    tokens = 0
    vector: list[float] | None = None

    def query_vector() -> list[float]:
        nonlocal vector
        if vector is None:
            vector = embed_texts(
                [search_query],
                dim=getattr(settings, "embed_dim", 1024),
                backend=getattr(settings, "embed_backend", "hash"),
            )[0]
        return vector

    if not chosen:
        last_rid, last_src = _last_allowed_rule(history)
        if last_rid and last_rid in by_id and _looks_like_followup(message):
            chosen = by_id[last_rid]
            source = last_src or "regex"
        else:
            threshold = float(persona.get("cosine_threshold") or 0.62)
            try:
                hit = _cosine_rule(
                    qdrant,
                    vector=query_vector(),
                    module_code=module_code,
                    release_id=release_id,
                    threshold=threshold,
                    personal=personal,
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
                    query=search_query,
                    rules=rules,
                    history=history,
                    personal=personal,
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
        contact = _contact(chosen, header)
        if scope == "out_of_scope":
            answer = str(persona.get("out_of_scope") or "Câu này ngoài phạm vi của phòng.").strip()
        else:
            answer = _handoff_answer(persona, contact)
        return RouteResult(
            answer=answer,
            routing_source=source,
            status=scope,
            module_code=module_code,
            release_id=release_id,
            rule_id=chosen.get("rule_id"),
            contact_info=contact,
            interactive=_form(department),
            llm_tokens=tokens,
        )

    top_k = int(persona.get("top_k") or 6)
    hits = retrieve_docs(
        qdrant,
        vector=query_vector(),
        module_code=module_code,
        release_id=release_id,
        query=search_query,
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
        history=history,
    )
    if not text:
        text = "Chưa đủ nguồn trong tài liệu đã nạp để trả lời. Không đoán thêm."
    return RouteResult(
        answer=strip_source_marks(text),
        routing_source=source,
        status="answer_allowed",
        module_code=module_code,
        release_id=release_id,
        rule_id=chosen.get("rule_id"),
        citations=[],
        llm_tokens=tokens + gen_tokens,
    )
