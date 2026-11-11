"""Collect live agent answers for human review; substring checks are only a proxy."""

import json
import os
import unicodedata
from pathlib import Path

from app.agent.graph import AgentRuntime
from app.core.config import Settings
from app.evaluation.dataset import load_authored_cases


def main():
    settings = Settings()
    settings.postgres_host = "127.0.0.1"
    settings.qdrant_url = "http://127.0.0.1:6333"
    runtime = AgentRuntime.from_settings(settings)
    cases = [
        x
        for x in load_authored_cases(Path("evaluation/cases-phase08.yaml"))
        if x.kind == "retrieval" and (x.must_contain or os.getenv("PHASE8_FULL_REVIEW") == "1")
    ]
    if os.getenv("PHASE8_FULL_REVIEW") != "1":
        cases = cases[:10]
    results = []
    for case in cases:
        print("case", case.id, flush=True)
        result = runtime.invoke(
            case.query,
            department_id=settings.app_department_id,
            module_code=settings.app_module_code,
            environment=settings.app_env,
            conversation_id="phase8-" + case.id,
        )
        initial_status = result.status
        if initial_status == "clarification_required":
            result = runtime.invoke(
                "Dai hoc chinh quy",
                department_id=settings.app_department_id,
                module_code=settings.app_module_code,
                environment=settings.app_env,
                conversation_id="phase8-" + case.id,
            )
        text = " ".join(unicodedata.normalize("NFKC", result.answer).casefold().split())
        results.append(
            {
                "id": case.id,
                "query": case.query,
                "expected_substrings": case.must_contain,
                "initial_status": initial_status,
                "llm_calls": result.llm_calls,
                "provider_error": bool(result.error_message),
                "status": result.status,
                "answer": result.answer,
                "citations": [item.model_dump() for item in result.citations],
                "expected_document_codes": case.expected_document_codes,
                "expected_question_codes": case.expected_question_codes,
                "substring_proxy_pass": (
                    all(x.casefold() in text for x in case.must_contain)
                    if case.must_contain
                    else None
                ),
            }
        )
    name = (
        "phase-08-answer-expanded.json"
        if os.getenv("PHASE8_FULL_REVIEW") == "1"
        else "phase-08-answer-sample.json"
    )
    path = Path("reports/phases") / name
    path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        "cases:",
        len(results),
        "substring_proxy_pass:",
        sum(x["substring_proxy_pass"] is True for x in results),
    )


if __name__ == "__main__":
    main()
