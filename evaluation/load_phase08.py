"""Run a real HTTP concurrency probe without logging credentials or responses."""

import asyncio
import json
import os
import statistics
import time
from pathlib import Path

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.evaluation.dataset import load_authored_cases
from app.models.tables import Faq


async def main():
    settings = Settings()
    engine = create_engine(settings.postgres_sync_url.set(host="127.0.0.1"))
    with Session(engine) as session:
        query = session.scalar(select(Faq.question).where(Faq.is_active.is_(True)).limit(1))
    engine.dispose()
    if not query:
        raise RuntimeError("No active FAQ available")
    cases = load_authored_cases(Path("evaluation/cases-phase08.yaml"))
    rag = next(case.query for case in cases if case.id == "para-dien-thoai")
    headers = {"X-API-Key": settings.app_api_key.get_secret_value()}
    async with httpx.AsyncClient(
        base_url=os.getenv("PHASE8_BASE_URL", "http://127.0.0.1:8000"), timeout=180
    ) as client:

        async def trial(message):
            start = time.perf_counter()
            try:
                result = await client.post("/v1/chat", headers=headers, json={"message": message})
                payload = result.json()
                return {
                    "http": result.status_code,
                    "status": payload.get("status"),
                    "provider_fallback": payload.get("provider_fallback", False),
                    "fallback": str(payload.get("answer", "")).startswith(
                        "T\u00f4i tr\u00edch \u0111o\u1ea1n d\u1eef li\u1ec7u"
                    ),
                    "seconds": round(time.perf_counter() - start, 3),
                }
            except (httpx.HTTPError, ValueError):
                return {
                    "http": 0,
                    "status": "request_error",
                    "seconds": round(time.perf_counter() - start, 3),
                }

        warmup = {"faq": await trial(query), "rag": await trial(rag)}
        if warmup["faq"]["status"] != "faq_answered" or warmup["rag"]["status"] != "answered":
            raise RuntimeError(f"warmup did not exercise FAQ and RAG: {warmup}")
        report = {"warmup": warmup}
        for kind, message in (("faq", query), ("rag", rag)):
            runs = await asyncio.gather(*(trial(message) for _ in range(10)))
            times = sorted(item["seconds"] for item in runs)
            report[kind] = {
                "requests": len(runs),
                "http_errors": sum(x["http"] != 200 for x in runs),
                "application_errors": sum(x["http"] != 200 or x["status"] == "error" for x in runs),
                "p95_seconds": times[9],
                "median_seconds": statistics.median(times),
                "fallback_responses": sum(x.get("fallback", False) for x in runs),
                "provider_fallbacks": sum(x.get("provider_fallback", False) for x in runs),
                "statuses": [x["status"] for x in runs],
            }
    path = Path("reports/phases/phase-08-load.json")
    await asyncio.to_thread(path.write_text, json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
