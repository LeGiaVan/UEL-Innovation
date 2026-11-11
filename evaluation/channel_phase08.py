"""Verify general channel questions against live PoC data."""

import json
from pathlib import Path

from app.agent.graph import AgentRuntime
from app.core.config import Settings
from app.evaluation.dataset import load_authored_cases


def main():
    settings = Settings()
    settings.postgres_host = "127.0.0.1"
    settings.qdrant_url = "http://127.0.0.1:6333"
    cases = load_authored_cases(Path("evaluation/cases-phase08.yaml"))
    runtime = AgentRuntime.from_settings(settings)
    results = []
    for case in cases:
        if case.id not in {"para-xem-diem", "para-nop-tieu-luan-sdh"}:
            continue
        result = runtime.invoke(
            case.query,
            department_id=settings.app_department_id,
            module_code=settings.app_module_code,
            environment=settings.app_env,
            conversation_id="phase8-channel-" + case.id,
        )
        results.append(
            {
                "id": case.id,
                "status": result.status,
                "answer": result.answer,
                "citations": [c.model_dump() for c in result.citations],
            }
        )
    Path("reports/phases/phase-08-channel-regression.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps([{"id": r["id"], "status": r["status"]} for r in results]))
    if len(results) != 2 or any(r["status"] not in {"answered", "faq_answered"} for r in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
