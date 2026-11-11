"""Read-only smoke of production Template 1 routing against the configured tenant."""

import json
from pathlib import Path

from app.agent.graph import AgentRuntime
from app.core.config import Settings


def main():
    settings = Settings(postgres_host="127.0.0.1", qdrant_url="http://127.0.0.1:6333")
    runtime = AgentRuntime.from_settings(settings)
    cases = [
        ("Hoc phi va cong no", "out_of_scope"),
        ("Toi khieu nai ket qua phuc khao cua rieng toi", "human_required"),
        ("Toi muon xin diem I, quy trinh nhu the nao", "answer_allowed"),
    ]
    report = []
    for query, expected in cases:
        result = runtime.invoke(
            query,
            department_id=settings.app_department_id,
            module_code=settings.app_module_code,
            environment=settings.app_env,
        )
        answer = result.answer or ""
        report.append(
            {
                "expected": expected,
                "scope": result.routing_scope,
                "source": result.routing_source,
                "rule_id": result.rule_id,
                "rule_version": result.rule_version,
                "status": result.status,
                "search_called": result.search_called,
                "generate_called": result.generate_called,
                "citation_values": [item.value for item in result.citations],
                "answer_preview": answer[:240],
                "provider_fallback": bool(result.error_message and result.status == "answered"),
            }
        )
    Path("reports/phases/standardization-routing-smoke.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
