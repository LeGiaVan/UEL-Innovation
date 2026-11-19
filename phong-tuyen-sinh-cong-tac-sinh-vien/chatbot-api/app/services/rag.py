from __future__ import annotations

import re
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


def _history_block(history: list[dict[str, Any]] | None) -> str:
    if not history:
        return ""
    lines = []
    for row in history[-8:]:
        role = "Người hỏi" if row.get("role") == "user" else "Bot"
        text = str(row.get("content") or "").strip()
        if text:
            lines.append(f"{role}: {strip_source_marks(text)[:600]}")
    if not lines:
        return ""
    return "Lịch sử hội thoại:\n" + "\n".join(lines)


ANSWER_MAX_TOKENS = 3072
_CUT_OFF = re.compile(
    r"(?i)[,:;–—\-]\s*$|\b(và|hoặc|gồm|như|theo|là|hơn|của|các|những)\s*$"
)


def looks_cut_off(text: str) -> bool:
    t = (text or "").rstrip()
    if len(t) < 24:
        return False
    if t.endswith("|") and not t.endswith("|\n"):
        return True
    return bool(_CUT_OFF.search(t))


def strip_source_marks(text: str) -> str:
    t = (text or "").strip()
    t = re.sub(r"\n+Nguồn\s*:[\s\S]*$", "", t, flags=re.IGNORECASE)
    t = re.sub(r"(?m)^Nguồn\s*:.*$", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*Nguồn\s*:\s*(?:\[[0-9]+\]\s*,?\s*)+\s*$", "", t, flags=re.IGNORECASE)
    return t.strip()


def generate_answer(
    *,
    query: str,
    hits: list[dict[str, Any]],
    persona: dict[str, Any],
    llm_opts: dict[str, Any] | None = None,
    api_key: str = "",
    base_url: str = "",
    model: str = "",
    history: list[dict[str, Any]] | None = None,
) -> tuple[str, int]:
    if not hits:
        return "", 0
    blocks = []
    for hit in hits:
        text = str(hit.get("text") or "").strip()
        if text:
            blocks.append(text)
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
            "Chỉ dùng tài liệu đã cho. Không bịa. Thiếu thông tin thì nói không đủ thông tin.",
            "Trả lời câu hiện tại, hiểu theo lịch sử (câu ngắn như «hệ chính quy thì sao» là hỏi tiếp chủ đề lượt trước).",
            "Văn tự nhiên như nhân viên phòng đang giải thích, đủ ý, không đọc máy.",
            "Trình bày Markdown cho giao diện chat: in đậm (**…**) mốc thời hạn, số ngày, tên hệ, điều kiện bắt buộc.",
            "Quy trình/các bước: danh sách đánh số, mỗi bước một mục, tiêu đề bước in đậm.",
            "So sánh nhiều hệ/khóa/mức: bảng Markdown (hàng là hệ hoặc khóa, cột là mức/thời hạn).",
            "Ghi chú dùng blockquote (> **Lưu ý:** …). Tiêu đề nhỏ nhất ### . Không dùng heading lớn.",
            "Khóa/hệ cùng mức thì một bảng, ghi rõ áp dụng khóa nào — không lặp bảng giống nhau.",
            "Viết đủ đến hết ý. Không cắt giữa câu, giữa bảng hay sau «Yêu cầu thấp hơn,».",
            "Không ghi [1], [2], «Nguồn:» hay nhãn tài liệu trong câu trả lời.",
        ]
        if part
    )
    hist = _history_block(history)
    user = "\n\n".join(p for p in [hist, f"Câu hỏi hiện tại: {query}", f"Tài liệu:\n{context}"] if p)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    text, tokens = llm_svc.chat_complete(
        **opts,
        messages=messages,
        max_tokens=ANSWER_MAX_TOKENS,
        continue_on_limit=True,
    )
    if looks_cut_off(text):
        more, extra = llm_svc.chat_complete(
            **opts,
            messages=[
                *messages,
                {"role": "assistant", "content": text},
                {
                    "role": "user",
                    "content": "Tiếp tục đúng chỗ vừa dừng. Không lặp đoạn trước. Kết thúc đủ câu và đủ bảng.",
                },
            ],
            max_tokens=2048,
            continue_on_limit=True,
        )
        if more:
            joiner = "" if text.endswith(("\n", " ")) or more.startswith(("\n", " ")) else "\n"
            text = f"{text}{joiner}{more}".strip()
            tokens += extra
    return strip_source_marks(text), tokens
