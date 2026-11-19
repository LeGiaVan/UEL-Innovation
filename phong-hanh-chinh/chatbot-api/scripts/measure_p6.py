"""Đo p95 embed + chat sau warmup. Chạy trong container app khi đã nạp seed."""

from __future__ import annotations

import statistics
import time

from app.factory import create_app
from app.integrations.embeddings import embed_texts
from app.services.routing import route_message


def p95(samples: list[float]) -> float:
    if len(samples) == 1:
        return samples[0]
    return float(statistics.quantiles(samples, n=20)[18])


def main() -> None:
    app = create_app()
    settings = app.state.settings
    backend = settings.embed_backend
    embed_texts(["warmup"], dim=settings.embed_dim, backend=backend)
    embed_ms: list[float] = []
    for _ in range(21):
        start = time.perf_counter()
        embed_texts(["Một câu hỏi khảo thí để đo embed."], dim=settings.embed_dim, backend=backend)
        embed_ms.append((time.perf_counter() - start) * 1000)

    def chat(message: str) -> tuple[object, float]:
        start = time.perf_counter()
        result = route_message(
            db=app.state.db,
            qdrant=app.state.qdrant,
            department=app.state.department,
            persona=app.state.persona,
            settings=settings,
            message=message,
            module_code="khao_khi",
        )
        return result, (time.perf_counter() - start) * 1000

    faq_q = "Người học xem điểm học phần ở đâu?"
    handoff_q = "Kết quả phúc khảo của tôi tuần này ra sao?"
    rag_q = "thời hạn phúc khảo ĐHCQ"
    chat(faq_q)
    chat(handoff_q)
    chat(rag_q)
    faq_ms, no_rag_ms, rag_ms = [], [], []
    for _ in range(12):
        _, ms = chat(faq_q)
        faq_ms.append(ms)
        _, ms = chat(handoff_q)
        no_rag_ms.append(ms)
        _, ms = chat(rag_q)
        rag_ms.append(ms)
    print(
        {
            "backend": backend,
            "embed_p95_ms": round(p95(embed_ms), 1),
            "faq_p95_ms": round(p95(faq_ms), 1),
            "no_rag_p95_ms": round(p95(no_rag_ms), 1),
            "rag_p95_ms": round(p95(rag_ms), 1),
        }
    )


if __name__ == "__main__":
    main()
