from pathlib import Path

from app.cli import _build_parser
from app.evaluation.dataset import EvalCase
from app.evaluation.runner import run_evaluation, write_eval_markdown
from app.gold.models import GoldHit


class FakeIndexer:
    faq_boost = 0.12

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def search(
        self,
        query: str,
        *,
        department_id: str,
        module_code: str,
        environment: str,
        limit: int = 8,
        mode: str = "hybrid",
    ) -> list[GoldHit]:
        del environment, limit, mode
        self.calls.append((query, department_id, module_code))
        if department_id == "other_department":
            return []
        if "học phí" in query:
            return []
        markdown = "Thời hạn 2 ngày làm việc đối với ĐHCQ."
        return [
            GoldHit(
                chunk_id="h1",
                entity_type="regulation",
                score=0.4,
                boosted_score=0.4,
                stair_markdown=markdown,
                payload={"document_code": "TL02", "department_id": department_id},
            )
        ]


def test_run_evaluation_scores_splits_and_tenant_leak(tmp_path: Path) -> None:
    cases = [
        EvalCase(
            id="ret-cal",
            query="Thời hạn phúc khảo ĐHCQ",
            kind="retrieval",
            split="calibration",
            expected_document_codes=["TL02"],
            must_contain=["2 ngày"],
        ),
        EvalCase(
            id="ret-test",
            query="Phúc khảo đại học chính quy mấy ngày",
            kind="retrieval",
            split="test",
            expected_document_codes=["TL02"],
        ),
        EvalCase(
            id="leak-1",
            query="Thời hạn phúc khảo đại học chính quy",
            kind="tenant_leak",
            split="test",
            expect_empty=True,
        ),
        EvalCase(
            id="pol-1",
            query="Tôi muốn hỏi học phí học kỳ này",
            kind="policy",
            split="calibration",
            expected_policy="out_of_scope",
        ),
    ]
    indexer = FakeIndexer()
    report = run_evaluation(
        indexer,
        session=None,
        department_id="bao_dam_chat_luong",
        module_code="khao_khi",
        environment="development",
        compare_dense=True,
        cases=cases,
    )
    assert report.retrieval["test"].recall_at_5 == 1.0
    assert report.retrieval["calibration"].recall_at_1 == 1.0
    assert report.tenant_leak_failures == 0
    assert report.policy_cases == 1
    assert report.dense_recall_at_5["test"] == 1.0
    assert report.recommended_top_k == 5
    assert any(dept == "other_department" for _, dept, _ in indexer.calls)
    path = write_eval_markdown(report, tmp_path / "eval.md")
    text = path.read_text(encoding="utf-8")
    assert "Recall@5" in text
    assert report.dataset_sha256


def test_cli_eval_retrieval_parser() -> None:
    parser = _build_parser()
    args = parser.parse_args(
        ["eval-retrieval", "--department", "bao_dam_chat_luong", "--module", "khao_khi"]
    )
    assert args.command == "eval-retrieval"
    assert args.top_k == 5
    assert args.mode == "hybrid"
    assert args.skip_dense is False
