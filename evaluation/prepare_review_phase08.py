"""Prepare a non-verdict review queue from authored Phase 8 retrieval cases."""

import json
from pathlib import Path

from app.evaluation.dataset import load_authored_cases


def main():
    cases = load_authored_cases(Path("evaluation/cases-phase08.yaml"))
    queue = [
        {
            "id": case.id,
            "split": case.split,
            "query": case.query,
            "expected_document_codes": case.expected_document_codes,
            "expected_question_codes": case.expected_question_codes,
            "known_answer_fragments": case.must_contain,
            "review_status": "pending",
        }
        for case in cases
        if case.kind == "retrieval"
    ]
    path = Path("reports/phases/phase-08-review-queue.json")
    path.write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Prepared {len(queue)} authored cases for independent review; no scores assigned.")


if __name__ == "__main__":
    main()
