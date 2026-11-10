from app.evaluation.dataset import EvalCase
from app.evaluation.metrics import first_relevant_rank, is_relevant, recall_at_k, reciprocal_rank
from app.gold.models import GoldHit


def _hit(
    *,
    question_code: str = "",
    document_code: str = "",
    markdown: str = "Trong 2 ngày làm việc.",
    score: float = 0.2,
) -> GoldHit:
    return GoldHit(
        chunk_id="c1",
        entity_type="faq" if question_code else "regulation",
        score=score,
        boosted_score=score,
        stair_markdown=markdown,
        payload={"question_code": question_code or None, "document_code": document_code or None},
    )


def test_is_relevant_matches_question_or_document_code() -> None:
    case = EvalCase(
        id="c1",
        query="phúc khảo",
        kind="retrieval",
        split="test",
        expected_question_codes=["II.3.049"],
        expected_document_codes=["TL02"],
        must_contain=["2 ngày"],
    )
    assert is_relevant(case, _hit(question_code="II.3.049", markdown="Trong 2 ngày làm việc."))
    assert is_relevant(case, _hit(document_code="TL02", markdown="Hạn 2 ngày sau khi công bố."))
    assert not is_relevant(case, _hit(document_code="TL02", markdown="Không nêu thời hạn."))
    assert not is_relevant(case, _hit(document_code="TL01", markdown="Trong 2 ngày làm việc."))


def test_must_contain_requires_every_token() -> None:
    case = EvalCase(
        id="c2",
        query="điểm I",
        kind="retrieval",
        split="calibration",
        expected_document_codes=["TL03"],
        must_contain=["1 năm", "hết hạn"],
    )
    hit = _hit(document_code="TL03", markdown="Quá 1 năm điểm I hết hạn.")
    assert is_relevant(case, hit)
    assert not is_relevant(case, _hit(document_code="TL03", markdown="Quá 1 năm chưa thi lại."))


def test_recall_mrr_and_first_rank() -> None:
    case = EvalCase(
        id="c3",
        query="x",
        kind="retrieval",
        split="test",
        expected_document_codes=["TL02"],
    )
    hits = [
        _hit(document_code="TL01"),
        _hit(document_code="TL02"),
        _hit(document_code="TL03"),
    ]
    rank = first_relevant_rank(case, hits)
    assert rank == 2
    assert recall_at_k(rank, 1) == 0.0
    assert recall_at_k(rank, 5) == 1.0
    assert reciprocal_rank(rank) == 0.5
    assert recall_at_k(None, 5) == 0.0
    assert reciprocal_rank(None) == 0.0
