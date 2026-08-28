from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .ai_employee_workspace import run_ai_employee_workspace
from .autonomous_loop import run_autonomous_loop
from .autonomous_runner import run_autonomous_director
from .autonomous_v2 import run_autonomous_v2_mvp
from .api_connectors import run_api_sources
from .amazon_training import run_amazon_training_bootstrap
from .ai_worker_training import run_ai_worker_onboarding_meeting
from .bulk_import import export_table, import_table
from .chat_extractor import ExtractionError, extract_chat_text
from .course_mindmap import run_course_mindmap
from .course_corpus_import import run_course_corpus_import
from .daily_runner import run_daily_director
from .data_lake_cleanup import run_data_lake_cleanup
from .ecommerce_director_agent import run_ecommerce_director_analysis
from .feishu_learning_import import register_feishu_learning_sources
from .high_frequency_training import run_high_frequency_training
from .idle_learning import run_idle_learning
from .intake import intake_text
from .knowledge_distillation import run_knowledge_distillation
from .market_coverage import run_market_coverage_intelligence
from .parser import RECORD_TYPES, RECORD_TYPE_ALIASES
from .patent_search import run_patent_search_agent
from .platform_autopilot import run_platform_autopilot
from .reporting import generate_daily_report
from .server import DEFAULT_PORT, run_server
from .store_operations_autopilot import run_store_operations_autopilot
from .storage import read_records
from .tk_evidence_recovery import run_tk_evidence_recovery
from .tiktok_knowledge_lake import run_tiktok_knowledge_lake_pilot
from .tk_overnight import run_tk_overnight_review, run_tk_overnight_round
from .tk_supervision_health import run_tk_supervision_health


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-director", description="AI Ecommerce Director v0.1")
    parser.add_argument("--root", default=".", help="Project root. Defaults to current directory.")
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    intake = subparsers.add_parser("intake", help="Record real-world operating data.")
    intake.add_argument("--type", default="auto", choices=["auto", *sorted(RECORD_TYPES)])
    intake.add_argument("--text", help="Raw text to intake.")
    intake.add_argument("--file", help="Text file to intake.")
    intake.add_argument("--source", default="manual")

    import_cmd = subparsers.add_parser("import", help="Import CSV or Excel rows into the real-data database.")
    import_cmd.add_argument("--type", required=True, choices=supported_record_type_choices())
    import_cmd.add_argument("--file", required=True, help="CSV, XLSX, or XLS file to import.")
    import_cmd.add_argument("--worksheet", help="Excel worksheet name.")
    import_cmd.add_argument("--mapping", help='Optional JSON column mapping, for example {"达人":"influencer_handle"}.')
    import_cmd.add_argument("--confidence-threshold", type=float, default=0.7)
    import_cmd.add_argument("--update-on-duplicate", action="store_true")

    export_cmd = subparsers.add_parser("export", help="Export stored records to CSV.")
    export_cmd.add_argument("--type", required=True, choices=supported_record_type_choices())
    export_cmd.add_argument("--file", required=True, help="Output CSV file.")

    extract = subparsers.add_parser("extract", help="Extract structured records from unstructured chat text.")
    extract.add_argument("--text", help="Raw chat text to extract.")
    extract.add_argument("--file", help="Text file to extract.")
    extract.add_argument("--confidence-threshold", type=float, default=0.7)
    extract.add_argument("--fallback-rules", action="store_true", help="Use rule-based fallback if no LLM is configured.")

    report = subparsers.add_parser("report", help="Generate daily operating report.")
    report.add_argument("--date", help="Report date, for example 2026-06-04.")

    daily_run = subparsers.add_parser("daily-run", help="Run AI Director daily autopilot.")
    daily_run.add_argument("--date", help="Run date, for example 2026-06-04.")
    daily_run.add_argument("--no-collect", action="store_true", help="Only analyze existing records.")
    daily_run.add_argument("--no-llm", action="store_true", help="Use rule-based analysis even if an LLM is configured.")

    auto_run = subparsers.add_parser("auto-run", help="Run fully autonomous safe-mode director workflow.")
    auto_run.add_argument("--date", help="Run date, for example 2026-06-04.")

    idle_run = subparsers.add_parser("idle-run", help="Run lightweight idle learning and strategy memory workflow.")
    idle_run.add_argument("--date", help="Run date, for example 2026-06-04.")

    loop_run = subparsers.add_parser("loop-run", help="Run the autonomous learning and execution loop.")
    loop_run.add_argument("--at", help="Run timestamp, for example 2026-06-08T08:00:00+00:00.")

    v2_run = subparsers.add_parser("v2-mvp-run", help="Run Autonomous Commerce OS v2 money-first MVP loop.")
    v2_run.add_argument("--at", help="Run timestamp, for example 2026-06-08T08:00:00+00:00.")

    api_run = subparsers.add_parser("api-run", help="Run configured read-only API data sources.")
    api_run.add_argument("--date", help="Run date, for example 2026-06-04.")

    cleanup_run = subparsers.add_parser("cleanup-run", help="Classify and deduplicate the Data Lake.")
    cleanup_run.add_argument("--dry-run", action="store_true", help="Only report cleanup changes; do not rewrite data files.")

    distill_run = subparsers.add_parser("knowledge-distill-run", help="Redistill existing knowledge into fine taxonomy, risk quarantine and word banks.")
    distill_run.add_argument("--date", help="Run date, for example 2026-06-09.")
    distill_run.add_argument("--max-records", type=int, default=2500, help="Maximum recent source records to distill.")

    amazon_training = subparsers.add_parser("amazon-training-bootstrap", help="Register Amazon multimodal sources, policy references, evals and the project Skill pack.")
    amazon_training.add_argument("--date", help="Run date, for example 2026-07-18.")

    ai_onboard = subparsers.add_parser("ai-onboard-run", help="Run AI worker onboarding and review meeting.")
    ai_onboard.add_argument("--date", help="Run date, for example 2026-06-04.")
    ai_onboard.add_argument("--rounds", type=int, default=2, help="How many training/review rounds to run.")

    course_mindmap = subparsers.add_parser("course-mindmap-run", help="Generate a detailed per-lesson course mind map report.")
    course_mindmap.add_argument("--title", required=True, help="Course or lesson title.")
    course_mindmap.add_argument("--lesson", default="lesson-01", help="Lesson id, for example lesson-01.")
    course_mindmap.add_argument("--text", help="Raw lesson transcript or notes.")
    course_mindmap.add_argument("--file", help="Text file containing the lesson transcript or notes.")
    course_mindmap.add_argument("--date", help="Run date, for example 2026-06-09.")

    course_import = subparsers.add_parser("course-corpus-import-run", help="Import course originals and strategy documents into the learning Data Lake.")
    course_import.add_argument("--date", help="Run date, for example 2026-06-09.")
    course_import.add_argument("--file", action="append", help="Optional source file. Pass multiple times to import several files.")
    course_import.add_argument("--min-training-samples", type=int, default=100)

    feishu_import = subparsers.add_parser("feishu-learning-register", help="Register Feishu docs as pending learning sources.")
    feishu_import.add_argument("--date", help="Run date, for example 2026-06-09.")
    feishu_import.add_argument("--url", action="append", required=True, help="Feishu doc/wiki URL. Pass multiple times.")

    director_agent = subparsers.add_parser("director-agent-run", help="Run AI Ecommerce Director Agent V1 exam loop.")
    director_agent.add_argument("--text", help="Case, link notes, meeting notes, or training material.")
    director_agent.add_argument("--file", help="Text file to analyze.")
    director_agent.add_argument("--platform", default="TikTok")
    director_agent.add_argument("--country", default="US")
    director_agent.add_argument("--category", default="All Category Radar")

    high_frequency_training = subparsers.add_parser("high-frequency-training-run", help="Run local-only high-frequency AI employee training.")
    high_frequency_training.add_argument("--date", help="Run date, for example 2026-06-09.")
    high_frequency_training.add_argument("--rounds", type=int, default=30, help="Internal micro-training rounds. Config max defaults to 30/minute.")

    employee_workspace = subparsers.add_parser("employee-workspace-run", help="Create proactive AI employee data workspaces, tasks, word bank and distillation packs.")
    employee_workspace.add_argument("--date", help="Run date, for example 2026-06-09.")
    employee_workspace.add_argument("--no-seed-collection-jobs", action="store_true", help="Do not seed category collection jobs.")

    market_coverage = subparsers.add_parser("market-coverage-run", help="Run P0 market coverage intelligence: category, segment, mid-rank, long-tail, creator, video and review signals.")
    market_coverage.add_argument("--date", help="Run date, for example 2026-06-09.")

    store_ops = subparsers.add_parser("store-ops-run", help="Create store operation runbooks, tasks and approval-gated execution packages.")
    store_ops.add_argument("--date", help="Run date, for example 2026-06-09.")
    store_ops.add_argument("--platform", default="TikTok Shop")
    store_ops.add_argument("--country", default="US")
    store_ops.add_argument("--store-id", default="UNASSIGNED-STORE")
    store_ops.add_argument("--store-mode", default="protected_legacy_store", choices=["experimental_new_store", "protected_legacy_store", "locked_revenue_store"])

    platform_run = subparsers.add_parser("platform-run", help="Open/check configured platform pages in safe read-only mode.")
    platform_run.add_argument("--date", help="Run date, for example 2026-06-04.")
    platform_run.add_argument("--no-open-browser", action="store_true", help="Do not open platform pages in the browser.")
    platform_run.add_argument("--no-collect-public", action="store_true", help="Only open pages; do not fetch public pages.")

    patent_run = subparsers.add_parser("patent-run", help="Run patent, trademark, copyright, and design IP search.")
    patent_run.add_argument("--date", help="Run date, for example 2026-06-04.")

    tiktok_lake = subparsers.add_parser("tiktok-lake-run", help="Create the safe TikTok video knowledge-lake pilot queue.")
    tiktok_lake.add_argument("--date", help="Run date, for example 2026-06-08.")

    tk_overnight = subparsers.add_parser("tk-overnight-run", help="Run TK-first overnight product-selection retake workflow.")
    tk_overnight.add_argument("--date", help="Run date, for example 2026-06-08.")
    tk_overnight.add_argument("--case-limit", type=int, default=300, help="How many TK case learning jobs to seed this round.")

    tk_overnight_review = subparsers.add_parser("tk-overnight-review", help="Generate the 12-hour TK overnight retake review.")
    tk_overnight_review.add_argument("--date", help="Review date, for example 2026-06-09.")
    tk_overnight_review.add_argument("--since-hours", type=int, default=12, help="How many recent hours to include.")

    tk_health = subparsers.add_parser("tk-health-check", help="Run 24h TK supervision health check for blockers, evidence growth and category depth coverage.")
    tk_health.add_argument("--date", help="Review date, for example 2026-06-09.")
    tk_health.add_argument("--since-hours", type=int, default=24, help="How many recent hours to include.")

    tk_recovery = subparsers.add_parser("tk-recovery-run", help="Convert TK health recovery tasks into executable logged-in capture jobs.")
    tk_recovery.add_argument("--date", help="Run date, for example 2026-06-09.")
    tk_recovery.add_argument("--limit", type=int, default=8, help="How many recovery tasks to queue this round.")
    tk_recovery.add_argument("--open-browser", action="store_true", help="Open recovery URLs. Default is queue-only to avoid opening logged-out browsers.")

    serve = subparsers.add_parser("serve", help="Run local browser capture server and dashboard.")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=DEFAULT_PORT)

    list_cmd = subparsers.add_parser("list", help="List stored records.")
    list_cmd.add_argument("--type", choices=sorted(RECORD_TYPES))
    list_cmd.add_argument("--limit", type=int, default=10)

    subparsers.add_parser("demo", help="Create demo records and generate a report.")
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_stdout()
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()

    if args.command == "intake":
        text = read_input(args.text, args.file)
        record, path = intake_text(root, text, args.type, args.source)
        print(json.dumps({"saved_to": str(path), "record": record.to_dict()}, ensure_ascii=False, indent=2))
        return 0

    if args.command == "import":
        mapping = json.loads(args.mapping) if args.mapping else None
        summary = import_table(
            root=root,
            file_path=Path(args.file).resolve(),
            record_type=args.type,
            worksheet=args.worksheet,
            explicit_mapping=mapping,
            confidence_threshold=args.confidence_threshold,
            update_on_duplicate=args.update_on_duplicate,
        )
        print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "export":
        count = export_table(root, args.type, Path(args.file).resolve())
        print(json.dumps({"exported": count, "file": str(Path(args.file).resolve())}, ensure_ascii=False, indent=2))
        return 0

    if args.command == "extract":
        text = read_input(args.text, args.file)
        try:
            summary = extract_chat_text(
                root,
                text,
                confidence_threshold=args.confidence_threshold,
                fallback_rules=args.fallback_rules,
            )
        except ExtractionError as exc:
            print(json.dumps({"error": str(exc), "persisted": 0}, ensure_ascii=False, indent=2))
            return 2
        print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "report":
        content, path = generate_daily_report(root, args.date)
        print(f"Report saved to: {path}")
        print("")
        print(content)
        return 0

    if args.command == "daily-run":
        result = run_daily_director(
            root,
            args.date,
            collect=not args.no_collect,
            use_llm=not args.no_llm,
        )
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "auto-run":
        result = run_autonomous_director(root, args.date)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "idle-run":
        result = run_idle_learning(root, args.date)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "loop-run":
        result = run_autonomous_loop(root, args.at)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "v2-mvp-run":
        result = run_autonomous_v2_mvp(root, args.at)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "api-run":
        result = run_api_sources(root, args.date)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "cleanup-run":
        result = run_data_lake_cleanup(root, apply=not args.dry_run)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "knowledge-distill-run":
        result = run_knowledge_distillation(root, run_date=args.date, max_records=args.max_records)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "amazon-training-bootstrap":
        result = run_amazon_training_bootstrap(root, run_date=args.date)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "ai-onboard-run":
        result = run_ai_worker_onboarding_meeting(root, args.date, rounds=args.rounds)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "course-mindmap-run":
        text = read_input(args.text, args.file)
        result = run_course_mindmap(root, title=args.title, source_text=text, lesson=args.lesson, run_date=args.date)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "course-corpus-import-run":
        source_paths = [Path(item).resolve() for item in args.file] if args.file else None
        result = run_course_corpus_import(root, run_date=args.date, source_paths=source_paths, min_training_samples=args.min_training_samples)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "feishu-learning-register":
        result = register_feishu_learning_sources(root, args.url, run_date=args.date)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "director-agent-run":
        text = read_input(args.text, args.file) if args.text or args.file else ""
        result = run_ecommerce_director_analysis(
            root,
            {
                "input_text": text,
                "platform": args.platform,
                "country": args.country,
                "category": args.category,
            },
        )
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "high-frequency-training-run":
        result = run_high_frequency_training(root, args.date, rounds=args.rounds)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "employee-workspace-run":
        result = run_ai_employee_workspace(root, args.date, seed_collection_jobs=not args.no_seed_collection_jobs)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "market-coverage-run":
        result = run_market_coverage_intelligence(root, args.date)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "store-ops-run":
        result = run_store_operations_autopilot(
            root,
            args.date,
            platform=args.platform,
            country=args.country,
            store_id=args.store_id,
            store_mode=args.store_mode,
        )
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "platform-run":
        result = run_platform_autopilot(
            root,
            args.date,
            open_browser=not args.no_open_browser,
            collect_public=not args.no_collect_public,
        )
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "patent-run":
        result = run_patent_search_agent(root, args.date)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "tiktok-lake-run":
        result = run_tiktok_knowledge_lake_pilot(root, args.date)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "tk-overnight-run":
        result = run_tk_overnight_round(root, args.date, case_limit=args.case_limit)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "tk-overnight-review":
        result = run_tk_overnight_review(root, args.date, since_hours=args.since_hours)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "tk-health-check":
        result = run_tk_supervision_health(root, args.date, since_hours=args.since_hours)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "tk-recovery-run":
        result = run_tk_evidence_recovery(root, args.date, limit=args.limit, open_browser=args.open_browser)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "serve":
        run_server(root, args.host, args.port)
        return 0

    if args.command == "list":
        records = read_records(root, args.type)
        for record in records[-args.limit :]:
            print(json.dumps(record.to_dict(), ensure_ascii=False))
        return 0

    if args.command == "demo":
        run_demo(root)
        return 0

    return 1


def configure_stdout() -> None:
    for stream in [sys.stdout, sys.stderr]:
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def read_input(text: str | None, file_path: str | None) -> str:
    if text:
        return text
    if file_path:
        return Path(file_path).read_text(encoding="utf-8")
    if not sys.stdin.isatty():
        return sys.stdin.read()
    raise SystemExit("Please pass --text or --file.")


def supported_record_type_choices() -> list[str]:
    return sorted({*RECORD_TYPES, *RECORD_TYPE_ALIASES})


def run_demo(root: Path) -> None:
    demo_records = [
        (
            "money_case",
            """
产品：香水
售价：29.99
成本：4
达人类型：美女达人
素材动作：喷一下香水，路人回头
ROI：3.2
生命周期：3 个月
赚钱原因：画面简单、情绪直接、客单价容易冲动下单
""",
        ),
        (
            "influencer_cooperation",
            """
达人昵称：demo_beauty_creator
平台：TikTok
粉丝：85000
均播：32000
报价：100
寄样成本：8
是否发视频：是
出单：50
ROI：3.5
""",
        ),
        (
            "hot_link",
            """
来源：FastMoss
链接：https://example.com/hot-product
产品：Blue Collar Dad Shirt
增长信号：近 7 天销量快速上升，评论集中在 Father's Day Gift
""",
        ),
    ]
    for record_type, text in demo_records:
        record, path = intake_text(root, text, record_type, "demo")
        print(f"Saved {record.record_type} -> {path}")
    _, report_path = generate_daily_report(root)
    print(f"Demo report saved to: {report_path}")


if __name__ == "__main__":
    raise SystemExit(main())
