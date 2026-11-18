from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.core.retrieval import DATE_HINTS, PROC_KINDS, PROC_TYPES
from app.integrations.qdrant import COL_DOCS
from app.services import llm as llm_svc


def _expired(point: dict[str, Any], today: date) -> bool:
    raw = (point.get("effective_to") or "").strip()
    if not raw:
        return False
    try:
        return date.fromisoformat(raw[:10]) < today
    except ValueError:
        return False


def retrieve_docs(
    qdrant,
    *,
    vector: list[float],
    module_code: str,
    release_id: str,
    query: str,
    top_k: int,
) -> list[dict[str, Any]]:
    if qdrant is None:
        return []
    today = datetime.now().date()
    hits = qdrant.search(
        COL_DOCS,
        vector,
        limit=max(top_k * 3, 12),
        filt={"module_code": module_code, "release_id": release_id},
    )
    qlow = (query or "").lower()
    date_q = any(h in qlow for h in DATE_HINTS)
    scored = []
    for hit in hits:
        if _expired(hit, today):
            continue
        score = float(hit.get("score") or 0) * float(hit.get("retrieve_boost") or 1.0)
        if date_q and hit.get("source") == "milestone":
            score += 0.15
        scored.append({**hit, "score": score})
    scored.sort(key=lambda p: p["score"], reverse=True)
    top = scored[: max(1, top_k)]
    return _hydrate(qdrant, top, module_code=module_code, release_id=release_id)


def _hydrate(qdrant, hits: list[dict[str, Any]], *, module_code: str, release_id: str) -> list[dict[str, Any]]:
    sheets = set()
    for hit in hits:
        if hit.get("source") != "business":
            continue
        kind = hit.get("kind") or ""
        dtype = hit.get("doc_type_code") or ""
        if kind in PROC_KINDS or dtype in PROC_TYPES:
            if hit.get("sheet"):
                sheets.add(hit["sheet"])
    if not sheets:
        return hits
    extra = qdrant.scroll(
        COL_DOCS,
        filt={
            "module_code": module_code,
            "release_id": release_id,
            "source": "business",
            "sheet": list(sheets),
        },
    )
    seen = {str(h.get("id")) for h in hits}
    out = list(hits)
    for point in extra:
        kind = point.get("kind") or ""
        if kind not in PROC_KINDS:
            continue
        pid = str(point.get("id"))
        if pid in seen:
            continue
        seen.add(pid)
        out.append(point)
    return out


def citations_of(hits: list[dict[str, Any]]) -> list[dict[str, str]]:
    items = []
    for hit in hits:
        label = hit.get("title") or hit.get("question_code") or hit.get("milestone_id") or hit.get("source") or ""
        items.append(
            {
                "source": str(hit.get("source") or ""),
                "document_name": str(label),
                "kind": str(hit.get("kind") or ""),
            }
        )
    return items


def generate_answer(
    *,
    query: str,
    hits: list[dict[str, Any]],
    persona: dict[str, Any],
    llm_opts: dict[str, Any] | None = None,
    api_key: str = "",
    base_url: str = "",
    model: str = "",
) -> tuple[str, int]:
    if not hits:
        return "", 0
    blocks = []
    for i, hit in enumerate(hits, start=1):
        label = hit.get("title") or hit.get("question_code") or hit.get("milestone_id") or hit.get("kind")
        blocks.append(f"[{i}] ({hit.get('source')}/{hit.get('kind')}) {label}\n{hit.get('text') or ''}")
    context = "\n\n".join(blocks)[:12000]
    opts = dict(llm_opts or {})
    if not opts:
        opts = {"api_key": api_key, "base_url": base_url, "model": model, "provider": ""}
    if not opts.get("api_key"):
        first = hits[0]
        return (first.get("text") or "").strip(), 0
    gloss = persona.get("glossary") or {}
    gloss_txt = ""
    if isinstance(gloss, dict) and gloss:
        gloss_txt = "Thuật ngữ:\n" + "\n".join(
            f"- {k}: {v}" for k, v in gloss.items() if str(k).strip()
        )
    system = "\n".join(
        part
        for part in [
            str(persona.get("role") or "Trợ lý quy định"),
            str(persona.get("constraints") or ""),
            str(persona.get("answer_style") or ""),
            gloss_txt,
            "Chỉ dùng nguồn đã cho. Không bịa. Thiếu nguồn thì nói không đủ thông tin. Cuối câu ghi Nguồn.",
        ]
        if part
    )
    text, tokens = llm_svc.chat_complete(
        **opts,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"Câu hỏi: {query}\n\nNguồn:\n{context}"},
        ],
    )
    return text, tokens
