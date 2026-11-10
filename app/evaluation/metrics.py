from __future__ import annotations

from collections.abc import Sequence

from app.evaluation.dataset import EvalCase
from app.gold.models import GoldHit


def is_relevant(case: EvalCase, hit: GoldHit) -> bool:
    payload = hit.payload
    question_code = str(payload.get("question_code") or "")
    document_code = str(payload.get("document_code") or "")
    code_ok = False
    if case.expected_question_codes:
        code_ok = question_code in case.expected_question_codes
    if case.expected_document_codes:
        code_ok = code_ok or document_code in case.expected_document_codes
    if not case.expected_question_codes and not case.expected_document_codes:
        return False
    if not code_ok:
        return False
    haystack = hit.stair_markdown.casefold()
    return all(token.casefold() in haystack for token in case.must_contain)


def first_relevant_rank(case: EvalCase, hits: Sequence[GoldHit]) -> int | None:
    for index, hit in enumerate(hits, start=1):
        if is_relevant(case, hit):
            return index
    return None


def recall_at_k(rank: int | None, k: int) -> float:
    return 1.0 if rank is not None and rank <= k else 0.0


def reciprocal_rank(rank: int | None) -> float:
    return 0.0 if rank is None else 1.0 / rank
