from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from app.core.logging import configure_logging
from app.gold.indexer import GoldIndexer
from app.ingestion.bronze import MinioBronzeStore
from app.ingestion.enums import SourceType
from app.ingestion.exceptions import AdapterNotImplementedError, IngestionError, ManifestError
from app.ingestion.pipeline import SyncRequest, run_sync


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli", description="UEL RAG Chatbot operations"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    sync = subparsers.add_parser("sync", help="Extract, validate and snapshot Bronze source data")
    sync.add_argument("--department", required=True)
    sync.add_argument("--module", required=True)
    sync.add_argument("--source", choices=("xlsx", "google-sheets"), default="xlsx")
    sync.add_argument("--source-path", type=Path)
    sync.add_argument("--config", type=Path, default=Path("configs/departments.yaml"))
    sync.add_argument("--output", type=Path, default=Path("reports/validation"))
    sync.add_argument("--env", default="development")
    sync.add_argument("--dry-run", action="store_true")
    sync.add_argument(
        "--skip-gold",
        action="store_true",
        help="Write Silver only, do not index Qdrant",
    )
    rebuild = subparsers.add_parser(
        "rebuild-gold", help="Rebuild Qdrant Gold index from PostgreSQL Silver"
    )
    rebuild.add_argument("--department", required=True)
    rebuild.add_argument("--module", required=True)
    rebuild.add_argument("--env", default="development")
    rebuild.add_argument("--output", type=Path, default=Path("reports/gold"))
    rebuild.add_argument(
        "--incremental",
        action="store_true",
        help="Skip chunks whose content hash is already in Qdrant",
    )
    verify = subparsers.add_parser(
        "gold-verify", help="Count Gold points, scan PII, incremental sync, smoke search"
    )
    verify.add_argument("--department", required=True)
    verify.add_argument("--module", required=True)
    verify.add_argument("--env", default="development")
    verify.add_argument("--output", type=Path, default=Path("reports/gold"))
    verify.add_argument(
        "--report",
        type=Path,
        default=Path("reports/phases/phase-04-evidence.json"),
    )
    evaluate = subparsers.add_parser("eval-retrieval", help="Phase 5 retrieval baseline")
    evaluate.add_argument("--cases", type=Path, default=Path("evaluation/cases.yaml"))
    evaluate.add_argument("--department", required=True)
    evaluate.add_argument("--module", required=True)
    evaluate.add_argument("--env", default="development")
    evaluate.add_argument("--mode", choices=("hybrid", "dense"), default="hybrid")
    evaluate.add_argument("--top-k", type=int, default=5)
    evaluate.add_argument("--score-threshold", type=float, default=0.0)
    evaluate.add_argument("--skip-dense", action="store_true")
    evaluate.add_argument(
        "--report",
        type=Path,
        default=Path("reports/phases/phase-05-baseline.json"),
    )
    chat = subparsers.add_parser("chat", help="Phase 6 LangGraph RAG chat")
    chat.add_argument("--department", required=True)
    chat.add_argument("--module", required=True)
    chat.add_argument("--env", default="development")
    chat.add_argument("--conversation-id", default=None)
    chat.add_argument("--message", default=None, help="One-shot question; omit for REPL")
    return parser


def _bronze_store_from_settings() -> MinioBronzeStore:
    from app.core.config import get_settings

    settings = get_settings()
    return MinioBronzeStore(
        endpoint_url=settings.minio_url,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        bucket=settings.minio_bucket_bronze,
    )


def _normalize_slugs(args: argparse.Namespace) -> None:
    for attr in ("department", "module"):
        value = getattr(args, attr, None)
        if isinstance(value, str) and "-" in value:
            fixed = value.replace("-", "_")
            print(f"note: --{attr} '{value}' -> '{fixed}' (slug dùng gạch dưới).")
            setattr(args, attr, fixed)


def main(argv: Sequence[str] | None = None) -> int:
    configure_logging("INFO")
    parser = _build_parser()
    args = parser.parse_args(argv)
    _normalize_slugs(args)
    if args.command == "rebuild-gold":
        return _rebuild_gold(args)
    if args.command == "gold-verify":
        return _gold_verify(args)
    if args.command == "eval-retrieval":
        return _eval_retrieval(args)
    if args.command == "chat":
        return _chat(args)
    if args.command != "sync":
        parser.error(f"Unsupported command: {args.command}")

    source_type: SourceType = args.source
    source_path = args.source_path
    if source_path is None:
        from app.ingestion.manifest import load_department_configs, resolve_module
        _, module = resolve_module(load_department_configs(args.config), args.department, args.module)
        source_path = args.config.resolve().parent.parent / module.source_path

    bronze_store = None
    if not args.dry_run:
        bronze_store = _bronze_store_from_settings()

    try:
        outcome = run_sync(
            SyncRequest(
                department_id=args.department,
                module_code=args.module,
                source_type=source_type,
                source_path=source_path,
                config_path=args.config,
                output_dir=args.output,
                dry_run=args.dry_run,
                environment=args.env,
                bronze_store=bronze_store,
                persist_gold=not args.dry_run and not args.skip_gold,
                gold_output_dir=Path("reports/gold"),
            )
        )
    except AdapterNotImplementedError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 4
    except ManifestError as exc:
        print(f"blocked: {exc}", file=sys.stderr)
        return 3
    except IngestionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    report = outcome.report
    print(f"release: {report.release_id}")
    print(f"status: {outcome.status}")
    print(f"dry_run: {report.dry_run}")
    print(f"routing_rules: {report.counts.routing_rules}")
    print(f"faqs: {report.counts.faqs}")
    print(f"documents: {report.counts.documents}")
    print(f"errors: {report.error_count}")
    print(f"warnings: {report.warning_count}")
    print(f"infos: {report.info_count}")
    print(f"publish_allowed: {report.publish_allowed}")
    if outcome.report_json_path:
        print(f"report_json: {outcome.report_json_path}")
    if outcome.report_markdown_path:
        print(f"report_markdown: {outcome.report_markdown_path}")
    if report.bronze_object_keys:
        print(f"bronze_objects: {len(report.bronze_object_keys)}")
    if report.silver:
        print(f"silver_status: {report.silver.status}")
        print(f"silver_inserted: {report.silver.inserted_count}")
        print(f"silver_updated: {report.silver.updated_count}")
        print(f"silver_deactivated: {report.silver.deactivated_count}")
        print(f"silver_unchanged: {report.silver.unchanged_count}")
        print(f"sync_run_id: {report.silver.sync_run_id}")
    if report.gold:
        print(f"gold_status: {report.gold.status}")
        print(f"gold_chunks: {report.gold.chunk_count}")
        print(f"gold_upserted: {report.gold.upserted_count}")
        print(f"gold_unchanged: {report.gold.unchanged_count}")
        print(f"gold_deleted: {report.gold.deleted_count}")
        print(f"gold_collection: {report.gold.collection}")
        print(f"gold_model: {report.gold.model}")
        if report.gold.error_message:
            print(f"gold_error: {report.gold.error_message}")
    if outcome.status == "blocked":
        return 3
    if outcome.status in {"validated", "completed"}:
        return 0
    if outcome.status == "partial_failed":
        return 2
    return 2


def _rebuild_gold(args: argparse.Namespace) -> int:
    indexer = GoldIndexer.from_settings()
    try:
        stats = indexer.sync(
            department_id=args.department,
            module_code=args.module,
            environment=args.env,
            output_dir=args.output,
            full_rebuild=not args.incremental,
        )
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"gold_status: {stats.status}")
    print(f"gold_chunks: {stats.chunk_count}")
    print(f"gold_upserted: {stats.upserted_count}")
    print(f"gold_deleted: {stats.deleted_count}")
    print(f"gold_collection: {stats.collection}")
    print(f"gold_model: {stats.model}")
    return 0 if stats.status == "completed" else 2


def _gold_verify(args: argparse.Namespace) -> int:
    from app.gold.verify import run_gold_verify

    indexer = GoldIndexer.from_settings()
    try:
        report = run_gold_verify(
            indexer,
            department_id=args.department,
            module_code=args.module,
            environment=args.env,
            output_dir=args.output,
        )
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    print(f"collection: {report.collection}")
    print(f"model: {report.model}")
    print(f"dense_dim: {report.dense_dim}")
    print(f"points: {report.point_count}")
    print(f"entity_counts: {report.entity_counts}")
    print(f"release_statuses: {report.release_statuses}")
    print(f"pii_hits: {report.pii_hits}")
    print(f"tenant_leak_hits: {report.tenant_leak_hits}")
    print(f"incremental_unchanged: {report.incremental_unchanged}")
    print(f"incremental_upserted: {report.incremental_upserted}")
    print(f"query_embed_seconds: {report.query_embed_seconds}")
    for item in report.smoke:
        print(
            f"smoke: {item.query} -> hits={item.hit_count} "
            f"top={item.top_entity} matched={item.expect_matched}"
        )
    print(f"report: {args.report}")
    if report.pii_hits or report.tenant_leak_hits:
        return 2
    if report.point_count == 0:
        return 2
    return 0


def _eval_retrieval(args: argparse.Namespace) -> int:
    from sqlalchemy.orm import sessionmaker

    from app.core.config import Settings
    from app.evaluation.dataset import load_eval_cases
    from app.evaluation.runner import DEADLINE_CASE_IDS, run_evaluation, write_eval_markdown
    from app.repositories.silver import create_sync_engine

    settings = Settings()
    engine = create_sync_engine(settings)
    indexer = GoldIndexer.from_settings(settings)
    with sessionmaker(engine)() as session:
        report = run_evaluation(
            indexer,
            session,
            department_id=args.department,
            module_code=args.module,
            environment=args.env,
            top_k=args.top_k,
            score_threshold=args.score_threshold,
            mode=args.mode,
            compare_dense=not args.skip_dense,
            cases=load_eval_cases(
                session, args.cases, department_id=args.department, module_code=args.module
            ),
        )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    markdown = write_eval_markdown(report, args.report.with_suffix(".md"))
    print(f"dataset_sha256: {report.dataset_sha256}")
    print(f"mode: {report.mode}")
    print(f"recommended_top_k: {report.recommended_top_k}")
    print(f"recommended_threshold: {report.recommended_threshold}")
    print(f"tenant_leak_failures: {report.tenant_leak_failures}")
    for split, metrics in sorted(report.retrieval.items()):
        print(
            f"retrieval_{split}: n={metrics.cases} "
            f"r1={metrics.recall_at_1:.3f} r5={metrics.recall_at_5:.3f} mrr={metrics.mrr:.3f}"
        )
    for split, value in sorted(report.dense_recall_at_5.items()):
        print(f"dense_r5_{split}: {value:.3f}")
    print(f"report: {args.report}")
    print(f"report_markdown: {markdown}")
    test_metrics = report.retrieval.get("test")
    all_metrics = report.retrieval.get("all")
    deadline_misses = [
        item.case_id
        for item in report.scores
        if item.case_id in DEADLINE_CASE_IDS and item.recall_at_5 < 1.0
    ]
    if report.tenant_leak_failures:
        return 2
    if all_metrics is None or all_metrics.cases < 80:
        return 2
    if test_metrics is None or test_metrics.recall_at_5 < 0.85:
        return 2
    if deadline_misses:
        print(f"deadline_misses: {deadline_misses}")
        return 2
    return 0


def _chat(args: argparse.Namespace) -> int:
    from uuid import uuid4

    from app.agent.graph import AgentRuntime
    from app.core.config import Settings

    settings = Settings()
    if settings.llm_provider != "fake" and not settings.llm_api_key.get_secret_value():
        print(
            "Thiếu LLM_API_KEY. Tạo key Groq tại https://console.groq.com/keys "
            "rồi gán LLM_API_KEY (và LLM_PROVIDER=groq) trong .env."
        )
        return 2
    runtime = AgentRuntime.from_settings(settings)
    conversation_id = args.conversation_id or str(uuid4())
    print(f"llm: {settings.llm_provider} / {settings.llm_model}")
    if args.message:
        _print_chat_result(
            runtime.invoke(
                args.message,
                department_id=args.department,
                module_code=args.module,
                environment=args.env,
                conversation_id=conversation_id,
            )
        )
        return 0
    print(f"conversation_id={conversation_id}")
    print("Nhập câu hỏi (dòng trống hoặc 'quit' để thoát).")
    while True:
        try:
            line = input("> ").strip()
        except EOFError:
            return 0
        if not line or line.casefold() in {"quit", "exit"}:
            return 0
        _print_chat_result(
            runtime.invoke(
                line,
                department_id=args.department,
                module_code=args.module,
                environment=args.env,
                conversation_id=conversation_id,
            )
        )


def _print_chat_result(result: object) -> None:
    from app.agent.models import ChatResult

    chat = result if isinstance(result, ChatResult) else ChatResult.model_validate(result)
    print(f"status: {chat.status}")
    print(f"routing: {chat.routing_scope} ({chat.routing_source})")
    if chat.citations:
        visible = [
            f"{item.kind}:{item.value}" for item in chat.citations if item.kind != "chunk_id"
        ]
        if visible:
            print(f"citations: {', '.join(visible)}")
    if chat.llm_calls:
        print(f"llm_calls: {', '.join(chat.llm_calls)}")
    if chat.error_message and chat.status == "error":
        print(f"error: {chat.error_message}")
    elif chat.error_message and chat.status == "answered":
        detail = chat.error_message
        if "không tồn tại" in detail.casefold() or "404" in detail:
            print(f"note: {detail}")
        else:
            print("note: mô hình quá tải/timeout — câu trả lời đang trích từ nguồn đã retrieve.")
    if chat.node_latency_ms:
        parts = [f"{name}={ms:.0f}ms" for name, ms in chat.node_latency_ms.items()]
        print(f"latency: {', '.join(parts)}")
    print(chat.answer)
    print()


if __name__ == "__main__":
    raise SystemExit(main())
