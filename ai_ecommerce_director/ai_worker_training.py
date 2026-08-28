from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from .course_mindmap import build_course_outline, build_course_mindmap_report
from .llm import LLMClient


AI_WORKER_TRAINING_PREFIX = "ai_worker_onboarding_meeting"

CURRICULUM_CHECKS = {
    "strategic_positioning": ["Global Commerce OS", "AI Ecommerce Director", "Commerce Brain"],
    "data_lake": ["Data Lake", "Product DB", "Video DB", "Store DB"],
    "learning_layer": ["Learning Engine", "Knowledge Graph", "StrategyMemory", "FeedbackTicket"],
    "autonomous_loop": ["Signal", "Hypothesis", "Experiment", "Reinforcement"],
    "tiktok_content": ["TikTok", "Video", "Hook", "Creator"],
    "amazon_product": ["Amazon", "BSR", "New Release", "Review"],
    "store_protection": ["Human Confirmation", "Old Store Protection", "No Unauthorized Real Actions"],
    "risk_ip": ["IP", "Trademark", "Copyright", "TRO"],
    "report_review": ["Report", "Review", "Missing Data", "Action Queue"],
}


@dataclass(slots=True)
class AIWorkerTrainingResult:
    run_date: str
    providers: list[str]
    transcript: list[dict[str, Any]]
    review: str
    report: str
    report_path: Path
    json_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_date": self.run_date,
            "providers": self.providers,
            "transcript": self.transcript,
            "review": self.review,
            "report": self.report,
            "report_path": str(self.report_path),
            "json_path": str(self.json_path),
        }


def run_ai_worker_onboarding_meeting(root: Path, run_date: str | None = None, *, rounds: int = 2) -> AIWorkerTrainingResult:
    root = root.resolve()
    report_date = run_date or date.today().isoformat()
    providers = ready_provider_names(root)
    transcript: list[dict[str, Any]] = []

    for round_index in range(1, max(1, rounds) + 1):
        for provider in providers:
            statement, ok = ask_provider_to_review(root, provider, round_index)
            transcript.append(
                {
                    "round": round_index,
                    "provider": provider,
                    "ok": ok,
                    "coverage": evaluate_curriculum_coverage(statement),
                    "statement": statement,
                }
            )

    review = build_chair_review(transcript)
    report = build_training_report(report_date, providers, transcript, review)
    report_path = write_training_report(root, report_date, report)
    json_path = write_training_json(root, report_date, providers, transcript, review)
    return AIWorkerTrainingResult(report_date, providers, transcript, review, report, report_path, json_path)


def ready_provider_names(root: Path) -> list[str]:
    status = LLMClient(root=root, task="strategy").status().to_dict()
    providers = []
    for item in status.get("providers", []):
        if not isinstance(item, dict) or not item.get("ready"):
            continue
        name = str(item.get("name") or "").strip()
        if name:
            providers.append(name)
    return providers


def ask_provider_to_review(root: Path, provider: str, round_index: int) -> tuple[str, bool]:
    client = LLMClient(root=root, task="strategy", provider=provider)
    prompt = training_prompt(round_index, provider)
    last_error = ""
    for attempt in range(1, 3):
        try:
            reply = client.chat(
                "You are an AI worker being onboarded into Global Commerce OS. Follow the onboarding pack exactly.",
                prompt,
                task="strategy",
                context={"scope": "ai_worker_onboarding", "user_role": "operator", "round": str(round_index)},
            )
            return reply.strip(), True
        except Exception as exc:  # noqa: BLE001 - training report should record failures.
            last_error = str(exc)[:500]
            if attempt < 2:
                time.sleep(3)
    return f"Training call failed after retry and was logged for repair: {last_error}", False


def training_prompt(round_index: int, provider: str) -> str:
    anchors = coverage_anchor_line()
    if round_index == 1:
        return (
            f"You are {provider}. Reply in Chinese, but keep the exact English anchor terms below so the system can audit coverage.\n"
            "Complete a Global Commerce OS AI worker onboarding recap within 900 Chinese characters.\n"
            "Required structure:\n"
            "1. System positioning: include Global Commerce OS, Commerce Brain, AI Ecommerce Director.\n"
            "2. Data foundation: include Data Lake, Product DB, Video DB, Store DB.\n"
            "3. Learning foundation: include Learning Engine, Knowledge Graph, StrategyMemory, FeedbackTicket.\n"
            "4. Autonomous loop: include Signal, Hypothesis, Experiment, Reinforcement.\n"
            "5. TikTok content work: include TikTok, Video, Hook, Creator.\n"
            "6. Amazon product work: include Amazon, BSR, New Release, Review.\n"
            "7. Store safety: include Human Confirmation, Old Store Protection, No Unauthorized Real Actions.\n"
            "8. Risk: include IP, Trademark, Copyright, TRO.\n"
            "9. Output discipline: include Report, Review, Missing Data, Action Queue, mind map.\n"
            f"Final required line: {anchors}\n"
            "Do not invent platform data, sales, API status, store results, or private credentials."
        )
    return (
        f"You are {provider}. Reply in Chinese, but keep exact English anchor terms where relevant.\n"
        "Run a second-round self-review within 700 Chinese characters.\n"
        "Mandatory anchors to include once, exactly: Global Commerce OS, AI Ecommerce Director, Data Lake, Product DB, Video DB, Store DB, Learning Engine, Knowledge Graph, StrategyMemory, FeedbackTicket, Signal, Hypothesis, Experiment, Reinforcement, TikTok, Video, Hook, Creator, Amazon, BSR, New Release, Review, Human Confirmation, Old Store Protection, No Unauthorized Real Actions, IP, Trademark, Copyright, TRO, Report, Missing Data, Action Queue.\n"
        "Answer:\n"
        "1. Where are you most likely to drift away from the operator's system?\n"
        "2. How do you avoid becoming a generic chatbot?\n"
        "3. What do you do when data is missing, fake, blocked by verification, or related to an old profitable store?\n"
        "4. Before selection, video breakdown, listing, influencer, or risk work, what five questions must you ask yourself?\n"
        "5. What should be written into StrategyMemory, FeedbackTicket, Report, Review, Missing Data, and Action Queue?\n"
        "6. If a report lacks a mind map, missing-data list, risk list, or action queue, how should you repair it?\n"
        f"Final required line: {anchors}\n"
        "Do not output vague slogans. Be operational."
    )


def coverage_anchor_line() -> str:
    terms: list[str] = []
    for values in CURRICULUM_CHECKS.values():
        for value in values:
            if value not in terms:
                terms.append(value)
    return "Coverage anchors: " + " | ".join(terms)


def evaluate_curriculum_coverage(text: str) -> dict[str, Any]:
    lowered = text.lower()
    hits: dict[str, bool] = {}
    missing: list[str] = []
    for check_name, terms in CURRICULUM_CHECKS.items():
        matched = any(term.lower() in lowered for term in terms)
        hits[check_name] = matched
        if not matched:
            missing.append(check_name)
    score = int(round((len(hits) - len(missing)) / max(1, len(hits)) * 100))
    return {"score": score, "hits": hits, "missing": missing}


def build_chair_review(transcript: list[dict[str, Any]]) -> str:
    ok_count = len([item for item in transcript if item.get("ok")])
    failed = [str(item.get("provider") or "") for item in transcript if not item.get("ok")]
    providers = sorted({str(item.get("provider") or "") for item in transcript if item.get("provider")})
    low_coverage = [
        f"{item.get('provider')} round {item.get('round')} score {item.get('coverage', {}).get('score', 0)}"
        for item in transcript
        if isinstance(item.get("coverage"), dict) and int(item.get("coverage", {}).get("score", 0) or 0) < 80
    ]
    lines = [
        "Chair review:",
        f"- Providers trained: {', '.join(providers) if providers else 'none'}.",
        f"- Successful replies: {ok_count}/{len(transcript)}.",
        "- All workers must operate as Global Commerce OS / AI Ecommerce Director employees, not generic chatbots.",
        "- Every major task must produce evidence, Missing Data, risk notes, Report, Review, Action Queue, and a mind map when useful.",
        "- Real store actions remain blocked without Human Confirmation. Old Store Protection is mandatory.",
        "- Useful experience must go into StrategyMemory; problems go into FeedbackTicket; signals become Hypothesis, Experiment, PatternWeight, and PriorityScore.",
    ]
    if low_coverage:
        lines.append(f"- Low coverage items need retraining: {', '.join(low_coverage)}.")
    if failed:
        lines.append(f"- Failed providers need repair: {', '.join(failed)}.")
    lines.append("- Next step: run the same discipline on a real product, real video, and real platform page, then compare output to actual data.")
    return "\n".join(lines)


def build_training_report(run_date: str, providers: list[str], transcript: list[dict[str, Any]], review: str) -> str:
    training_text = "\n\n".join(str(item.get("statement") or "") for item in transcript)
    mindmap_report = build_course_mindmap_report(
        run_date,
        build_course_outline(
            title="AI Ecommerce Director 员工训练总纲",
            source_text=training_text,
            lesson="ai-worker-onboarding",
        ),
    )
    mindmap_section = mindmap_report.split("## 细节思维导图", 1)[1].split("<details>", 1)[0].strip()
    lines = [
        f"# AI Worker Onboarding Meeting - {run_date}",
        "",
        "## Training Goal",
        "Train all connected AI providers to behave as AI employees inside Global Commerce OS, serving the AI Ecommerce Director.",
        "",
        "## Providers",
        ", ".join(providers) if providers else "No ready provider",
        "",
        "## Chair Review",
        review,
        "",
        "## Mind Map",
        mindmap_section,
        "",
        "## Curriculum Coverage",
    ]
    for item in transcript:
        coverage = item.get("coverage") if isinstance(item.get("coverage"), dict) else {}
        missing = coverage.get("missing") if isinstance(coverage.get("missing"), list) else []
        missing_text = ", ".join(str(name) for name in missing) if missing else "all core anchors covered"
        lines.append(f"- Round {item.get('round')} / {item.get('provider')}: {coverage.get('score', 0)} - {missing_text}")
    lines.extend(["", "## AI Worker Statements"])
    for item in transcript:
        status = "OK" if item.get("ok") else "FAILED"
        coverage = item.get("coverage") if isinstance(item.get("coverage"), dict) else {}
        lines.append(f"### Round {item.get('round')} - {item.get('provider')} - {status}")
        lines.append(f"Coverage: {coverage.get('score', 0)}")
        lines.append(str(item.get("statement") or "").strip())
        lines.append("")
    lines.extend(
        [
            "## Fixed Rules",
            "- This training is not one-time only. `config/ai_worker_onboarding.md` is injected into normal model calls.",
            "- External models are stateless; long-term memory must be written back to Data Lake / StrategyMemory / FeedbackTicket / Knowledge Graph.",
            "- A task is not complete without a useful report, evidence, missing-data list, risk list, and next action.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def write_training_report(root: Path, run_date: str, report: str) -> Path:
    path = root / "outputs" / f"{AI_WORKER_TRAINING_PREFIX}_{run_date}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report, encoding="utf-8-sig")
    return path


def write_training_json(root: Path, run_date: str, providers: list[str], transcript: list[dict[str, Any]], review: str) -> Path:
    path = root / "outputs" / f"{AI_WORKER_TRAINING_PREFIX}_{run_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "run_date": run_date,
                "providers": providers,
                "transcript": transcript,
                "review": review,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8-sig",
    )
    return path


def latest_ai_worker_onboarding_report(root: Path) -> tuple[str, Path | None]:
    paths = sorted((root / "outputs").glob(f"{AI_WORKER_TRAINING_PREFIX}_*.md"), reverse=True)
    if not paths:
        return "No AI worker onboarding report yet.", None
    path = paths[0]
    return path.read_text(encoding="utf-8"), path
