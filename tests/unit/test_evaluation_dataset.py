from pathlib import Path

from app.evaluation.dataset import dataset_fingerprint, load_authored_cases, load_eval_cases


def test_authored_cases_cover_required_groups() -> None:
    cases = load_authored_cases(Path("evaluation/cases.yaml"))
    kinds = {item.kind for item in cases}
    by_kind = {kind: [item for item in cases if item.kind == kind] for kind in kinds}
    paraphrases = [item for item in cases if item.id.startswith("para-")]
    documents = [item for item in cases if item.id.startswith("doc-")]
    assert len(cases) >= 40
    assert len(paraphrases) >= 15
    assert len(documents) >= 11
    assert all(item.exact_match_eligible is False for item in paraphrases)
    assert {item.expected_policy for item in by_kind["policy"]} >= {
        "out_of_scope",
        "handoff",
        "insufficient_evidence",
        "answer_allowed",
    }
    assert len(by_kind["adversarial"]) >= 5
    assert all(item.expect_empty for item in by_kind["tenant_leak"])
    splits = {item.split for item in cases}
    assert splits == {"calibration", "test"}


def test_load_eval_cases_without_session_is_authored_only() -> None:
    cases = load_eval_cases(None)
    assert all(not item.id.startswith("faq-verbatim-") for item in cases)
    digest = dataset_fingerprint(cases)
    assert len(digest) == 64
    assert dataset_fingerprint(cases) == digest
