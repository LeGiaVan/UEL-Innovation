"""Verify VB2/VLVH exceptions against the live Gold dataset."""

import json
from pathlib import Path

from app.agent.graph import AgentRuntime
from app.core.config import Settings
from app.evaluation.dataset import load_authored_cases


def main():
    settings = Settings()
    settings.postgres_host = "127.0.0.1"
    settings.qdrant_url = "http://127.0.0.1:6333"
    runtime = AgentRuntime.from_settings(settings)
    wanted = {"doc-tl02-vb2", "doc-tl03-vb2", "doc-tl04-vb2"}
    cases = [
        c for c in load_authored_cases(Path("evaluation/cases-phase08.yaml")) if c.id in wanted
    ]
    results = []
    for case in cases:
        result = runtime.invoke(
            case.query,
            department_id=settings.app_department_id,
            module_code=settings.app_module_code,
            environment=settings.app_env,
            conversation_id="phase8-vb2-" + case.id,
        )
        results.append(
            {
                "id": case.id,
                "status": result.status,
                "answer": result.answer,
                "citations": [c.model_dump() for c in result.citations],
            }
        )
    Path("reports/phases/phase-08-vb2-regression.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(results, ensure_ascii=True, indent=2))
    outcomes = {r["id"]: r["status"] for r in results}
    if outcomes != {
        "doc-tl02-vb2": "insufficient_evidence",
        "doc-tl03-vb2": "answered",
        "doc-tl04-vb2": "answered",
    }:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
