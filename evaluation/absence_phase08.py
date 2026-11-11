"""Verify routing of the authored general absence question."""

import json
from pathlib import Path

from app.agent.graph import AgentRuntime
from app.core.config import Settings
from app.evaluation.dataset import load_authored_cases


def main():
    settings = Settings()
    settings.postgres_host = "127.0.0.1"
    settings.qdrant_url = "http://127.0.0.1:6333"
    case = next(
        c
        for c in load_authored_cases(Path("evaluation/cases-phase08.yaml"))
        if c.id == "para-vang-thi-diem"
    )
    result = AgentRuntime.from_settings(settings).invoke(
        case.query,
        department_id=settings.app_department_id,
        module_code=settings.app_module_code,
        environment=settings.app_env,
        conversation_id="p8-absence",
    )
    output = {
        "status": result.status,
        "routing_scope": result.routing_scope,
        "routing_source": result.routing_source,
        "answer": result.answer,
        "citations": [c.model_dump() for c in result.citations],
    }
    Path("reports/phases/phase-08-absence-regression.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": result.status,
                "routing_scope": result.routing_scope,
                "citations": len(result.citations),
            }
        )
    )
    if result.status != "answered" or not result.citations:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
