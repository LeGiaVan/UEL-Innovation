"""Classify provider errors from concurrent real RAG requests without logging their content."""

import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.agent.graph import AgentRuntime
from app.core.config import Settings
from app.evaluation.dataset import load_authored_cases


def main():
    settings = Settings()
    settings.postgres_host = "127.0.0.1"
    settings.qdrant_url = "http://127.0.0.1:6333"
    runtime = AgentRuntime.from_settings(settings)
    case = next(
        x
        for x in load_authored_cases(Path("evaluation/cases-phase08.yaml"))
        if x.id == "para-dien-thoai"
    )

    def ask(index):
        result = runtime.invoke(
            case.query,
            department_id=settings.app_department_id,
            module_code=settings.app_module_code,
            environment=settings.app_env,
            conversation_id=f"phase8-provider-{index}",
        )
        error = (result.error_message or "").casefold()
        return next(
            (
                key
                for key in ("429", "401", "403", "404", "503", "timeout", "connect")
                if key in error
            ),
            "other" if error else "no_reported_error",
        )

    ask("warmup")
    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(ask, range(10)))
    report = {"attempts": len(results), "categories": dict(Counter(results))}
    Path("reports/phases/phase-08-provider-load.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report))


if __name__ == "__main__":
    main()
