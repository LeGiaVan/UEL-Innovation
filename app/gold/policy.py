from __future__ import annotations

from datetime import date
from typing import Any

DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"
BGE_M3_DENSE_DIM = 1024
DEFAULT_FAQ_SCORE_BOOST = 0.12

INDEXABLE_RELEASE_STATUSES: dict[str, frozenset[str]] = {
    "development": frozenset({"approved_for_dev", "approved_for_uat"}),
    "test": frozenset({"approved_for_dev", "approved_for_uat"}),
    "uat": frozenset({"approved_for_uat"}),
}


def allowed_release_statuses(environment: str) -> frozenset[str]:
    return INDEXABLE_RELEASE_STATUSES.get(environment, INDEXABLE_RELEASE_STATUSES["development"])


def is_indexable(*, is_active: bool, release_status: str, environment: str) -> bool:
    return is_active and release_status in allowed_release_statuses(environment)


def boosted_score(entity_type: str, score: float, faq_boost: float) -> float:
    if entity_type == "faq":
        return score + faq_boost
    return score


def is_effective(payload: dict[str, Any], today: date | None = None) -> bool:
    current = today or date.today()
    start = _parse_optional_date(payload.get("effective_from"))
    end = _parse_optional_date(payload.get("effective_to"))
    if (payload.get("effective_from") not in (None, "") and start is None) or (
        payload.get("effective_to") not in (None, "") and end is None
    ):
        return False
    if start is not None and start > current:
        return False
    return not (end is not None and end < current)


def _parse_optional_date(value: object) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    text = str(value)
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None
