from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.evaluation.dataset import EvalCase, dataset_fingerprint, load_eval_cases
from app.evaluation.metrics import first_relevant_rank, recall_at_k, reciprocal_rank
from app.gold.models import GoldHit

DEADLINE_CASE_IDS = frozenset(
    {
        "para-phuc-khao-dhcq",
        "para-phuc-khao-sdh",
        "para-diem-i-nop",
        "para-diem-i-hieu-luc",
        "para-tra-diem-i",
        "doc-tl02-thoi-han-dhcq",
        "doc-tl02-thoi-han-sdh",
        "doc-tl03-ba-ngay",
        "doc-tl03-mot-nam",
        "doc-tl04-bay-ngay",
    }
)


class RetrievalSearcher(Protocol):
    faq_boost: float

    def search(
        self,
        query: str,
        *,
        department_id: str,
        module_code: str,
        environment: str,
        limit: int = 8,
        mode: str = "hybrid",
    ) -> list[GoldHit]: ...


class CaseScore(BaseModel):
    case_id: str
    kind: str
    split: str
    rank: int | None = None
    recall_at_1: float = 0.0
    recall_at_5: float = 0.0
    mrr: float = 0.0
    hit_count: int = 0
    top_score: float | None = None
    empty_ok: bool | None = None
    departments: list[str] = Field(default_factory=list)


class SplitMetrics(BaseModel):
    cases: int = 0
    recall_at_1: float = 0.0
    recall_at_5: float = 0.0
    mrr: float = 0.0


class EvalReport(BaseModel):
    dataset_sha256: str
    mode: str
    top_k: int
    score_threshold: float
    faq_boost: float
    retrieval: dict[str, SplitMetrics]
    dense_recall_at_5: dict[str, float] = Field(default_factory=dict)
    tenant_leak_failures: int = 0
    policy_cases: int = 0
    adversarial_cases: int = 0
    recommended_top_k: int
    recommended_threshold: float
    scores: list[CaseScore]


def hit_passes_threshold(hit: GoldHit, threshold: float) -> bool:
    return hit.boosted_score >= threshold


def run_evaluation(
    indexer: RetrievalSearcher,
    session: Session | None,
    *,
    department_id: str,
    module_code: str,
    environment: str,
    top_k: int = 5,
    score_threshold: float = 0.0,
    mode: str = "hybrid",
    compare_dense: bool = True,
    cases: list[EvalCase] | None = None,
) -> EvalReport:
    resolved = (
        cases
        if cases is not None
        else load_eval_cases(
            session,
            department_id=department_id,
            module_code=module_code,
        )
    )
    cases = resolved
    scores = [
        _score_case(
            indexer,
            case,
            department_id=department_id,
            module_code=module_code,
            environment=environment,
            top_k=top_k,
            score_threshold=score_threshold,
            mode=mode,
            progress=(index, len(cases), mode),
        )
        for index, case in enumerate(cases, start=1)
    ]
    retrieval = _aggregate_retrieval(scores)
    dense_recall: dict[str, float] = {}
    if compare_dense:
        dense_cases = [case for case in cases if case.kind == "retrieval"]
        dense_scores = [
            _score_case(
                indexer,
                case,
                department_id=department_id,
                module_code=module_code,
                environment=environment,
                top_k=top_k,
                score_threshold=score_threshold,
                mode="dense",
                progress=(index, len(dense_cases), "dense"),
            )
            for index, case in enumerate(dense_cases, start=1)
        ]
        dense_retrieval = _aggregate_retrieval(dense_scores)
        dense_recall = {split: metrics.recall_at_5 for split, metrics in dense_retrieval.items()}
    leak_fail = sum(
        1 for item in scores if item.kind == "tenant_leak" and item.empty_ok is False
    )
    recommended_k, recommended_threshold = _tune_threshold(indexer, cases, scores)
    return EvalReport(
        dataset_sha256=dataset_fingerprint(cases),
        mode=mode,
        top_k=top_k,
        score_threshold=score_threshold,
        faq_boost=indexer.faq_boost,
        retrieval=retrieval,
        dense_recall_at_5=dense_recall,
        tenant_leak_failures=leak_fail,
        policy_cases=sum(1 for item in scores if item.kind == "policy"),
        adversarial_cases=sum(1 for item in scores if item.kind == "adversarial"),
        recommended_top_k=recommended_k,
        recommended_threshold=recommended_threshold,
        scores=scores,
    )


def write_eval_markdown(report: EvalReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Retrieval baseline",
        "",
        f"- dataset_sha256: `{report.dataset_sha256}`",
        f"- mode: {report.mode}",
        f"- top_k: {report.top_k}",
        f"- score_threshold: {report.score_threshold}",
        f"- recommended_top_k: {report.recommended_top_k}",
        f"- recommended_threshold: {report.recommended_threshold}",
        f"- tenant_leak_failures: {report.tenant_leak_failures}",
        "",
        "| Split | Cases | Recall@1 | Recall@5 | MRR |",
        "|---|---:|---:|---:|---:|",
    ]
    for split, metrics in sorted(report.retrieval.items()):
        lines.append(
            f"| {split} | {metrics.cases} | {metrics.recall_at_1:.3f} | "
            f"{metrics.recall_at_5:.3f} | {metrics.mrr:.3f} |"
        )
    if report.dense_recall_at_5:
        lines.extend(["", "## Dense-only Recall@5", ""])
        for split, value in sorted(report.dense_recall_at_5.items()):
            lines.append(f"- {split}: {value:.3f}")
    lines.extend(
        [
            "",
            "## Tenant leak / policy / adversarial",
            "",
            f"- tenant_leak_failures: {report.tenant_leak_failures}",
            f"- policy_cases: {report.policy_cases}",
            f"- adversarial_cases: {report.adversarial_cases}",
            "",
            "## Deadline cases",
            "",
            "| Case | Split | Rank | R@5 |",
            "|---|---|---:|---:|",
        ]
    )
    by_id = {item.case_id: item for item in report.scores}
    for case_id in sorted(DEADLINE_CASE_IDS):
        item = by_id.get(case_id)
        if item is None:
            continue
        rank = "—" if item.rank is None else str(item.rank)
        lines.append(f"| {case_id} | {item.split} | {rank} | {item.recall_at_5:.0f} |")
    failures = [
        item
        for item in report.scores
        if item.kind == "retrieval" and item.recall_at_5 < 1.0
    ]
    if failures:
        lines.extend(["", "## Retrieval misses (R@5 = 0)", ""])
        for item in failures:
            lines.append(f"- `{item.case_id}` ({item.split}) rank={item.rank}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _score_case(
    indexer: RetrievalSearcher,
    case: EvalCase,
    *,
    department_id: str,
    module_code: str,
    environment: str,
    top_k: int,
    score_threshold: float,
    mode: str,
    progress: tuple[int, int, str] | None = None,
) -> CaseScore:
    if progress is not None:
        index, total, label = progress
        if index == 1 or index == total or index % 10 == 0:
            print(f"eval {label}: {index}/{total} {case.id}", flush=True)
    search_department = "other_department" if case.kind == "tenant_leak" else department_id
    hits = indexer.search(
        case.query,
        department_id=search_department,
        module_code=module_code,
        environment=environment,
        limit=max(top_k, 8),
        mode=mode,
    )
    filtered = [hit for hit in hits if hit_passes_threshold(hit, score_threshold)][:top_k]
    departments = sorted(
        {str(hit.payload.get("department_id") or "") for hit in filtered if hit.payload}
    )
    if case.kind == "tenant_leak" or case.expect_empty:
        return CaseScore(
            case_id=case.id,
            kind=case.kind,
            split=case.split,
            hit_count=len(filtered),
            top_score=filtered[0].boosted_score if filtered else None,
            empty_ok=len(filtered) == 0,
            departments=departments,
        )
    rank = first_relevant_rank(case, filtered) if case.kind == "retrieval" else None
    return CaseScore(
        case_id=case.id,
        kind=case.kind,
        split=case.split,
        rank=rank,
        recall_at_1=recall_at_k(rank, 1) if case.kind == "retrieval" else 0.0,
        recall_at_5=recall_at_k(rank, 5) if case.kind == "retrieval" else 0.0,
        mrr=reciprocal_rank(rank) if case.kind == "retrieval" else 0.0,
        hit_count=len(filtered),
        top_score=filtered[0].boosted_score if filtered else None,
        departments=departments,
    )


def _aggregate_retrieval(scores: Sequence[CaseScore]) -> dict[str, SplitMetrics]:
    grouped: dict[str, list[CaseScore]] = defaultdict(list)
    for item in scores:
        if item.kind != "retrieval":
            continue
        grouped[item.split].append(item)
        grouped["all"].append(item)
    result: dict[str, SplitMetrics] = {}
    for split, items in grouped.items():
        count = len(items) or 1
        result[split] = SplitMetrics(
            cases=len(items),
            recall_at_1=sum(item.recall_at_1 for item in items) / count,
            recall_at_5=sum(item.recall_at_5 for item in items) / count,
            mrr=sum(item.mrr for item in items) / count,
        )
    return result


def _tune_threshold(
    indexer: RetrievalSearcher,
    cases: list[EvalCase],
    scored: list[CaseScore],
) -> tuple[int, float]:
    del indexer, cases
    cal = [item for item in scored if item.kind == "retrieval" and item.split == "calibration"]
    relevant_scores = [
        item.top_score for item in cal if item.rank == 1 and item.top_score is not None
    ]
    if not relevant_scores:
        return 5, 0.0
    floor = min(relevant_scores)
    # Keep a small margin below the weakest calibration R@1 hit; never drop Recall@5 on cal.
    threshold = max(0.0, round(floor * 0.5, 4))
    return 5, threshold
