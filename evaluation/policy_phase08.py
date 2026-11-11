"""Evaluate policy outcomes on authored cases with the configured agent."""

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
    cases = load_authored_cases(Path("evaluation/cases-phase08.yaml"))
    items = []
    for case in cases:
        if case.kind == "policy" and case.expected_policy in {
            "insufficient_evidence",
            "handoff",
            "out_of_scope",
        }:
            expected = {
                "insufficient_evidence": "insufficient_evidence",
                "handoff": "human_handoff",
                "out_of_scope": "out_of_scope",
            }[case.expected_policy]
        elif case.kind == "adversarial":
            expected = "out_of_scope" if case.id == "adv-other-dept" else "error"
        else:
            continue
        result = runtime.invoke(
            case.query,
            department_id=settings.app_department_id,
            module_code=settings.app_module_code,
            environment=settings.app_env,
            conversation_id="phase8-policy-" + case.id,
        )
        items.append(
            {
                "id": case.id,
                "kind": case.kind,
                "expected": expected,
                "actual": result.status,
                "passed": result.status == expected,
                "search_called": result.search_called,
                "generate_called": result.generate_called,
            }
        )
    report = {"cases": items, "passed": sum(x["passed"] for x in items), "total": len(items)}
    Path("reports/phases/phase-08-policy.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
