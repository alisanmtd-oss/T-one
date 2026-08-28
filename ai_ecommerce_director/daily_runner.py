from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin

from .api_connectors import load_api_sources, run_api_sources
from .llm import LLMClient
from .parser import canonical_record_type, normalize_fields
from .pod_admin import build_pod_admin_snapshot, load_pod_admin_config
from .reporting import generate_daily_report
from .scoring import score_record
from .storage import append_record, read_records
from .types import IntakeRecord


WATCH_SOURCE_CONFIG = Path("config") / "watch_sources.json"
AUTOPILOT_REPORT_PREFIX = "ai_director_autopilot"


@dataclass(slots=True)
class CollectedPage:
    url: str
    title: str
    text: str
    links: list[dict[str, str]]
    metric_lines: list[str]


@dataclass(slots=True)
class DailyRunResult:
    run_date: str
    collected_records: list[IntakeRecord]
    collection_status: list[dict[str, Any]]
    strategy_report: str
    strategy_report_path: Path
    daily_report_path: Path
    llm_used: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_date": self.run_date,
            "collected": len(self.collected_records),
            "collection_status": self.collection_status,
            "strategy_report": self.strategy_report,
            "strategy_report_path": str(self.strategy_report_path),
            "daily_report_path": str(self.daily_report_path),
            "llm_used": self.llm_used,
            "records": [record.to_dict() for record in self.collected_records],
        }


Fetcher = Callable[[str], CollectedPage]


def run_daily_director(
    root: Path,
    run_date: str | None = None,
    *,
    collect: bool = True,
    use_llm: bool = True,
    collect_api_sources: bool = True,
    fetcher: Fetcher | None = None,
) -> DailyRunResult:
    root = root.resolve()
    report_date = run_date or date.today().isoformat()
    sources = load_watch_sources(root)
    collected_records: list[IntakeRecord] = []
    collection_status: list[dict[str, Any]] = []

    if collect:
        for source in sources:
            status = collect_source(root, source, report_date, fetcher=fetcher)
            collection_status.append(status)
            record = status.get("record")
            if isinstance(record, IntakeRecord):
                collected_records.append(record)
                status["record"] = record.to_dict()
        pod_status = collect_pod_admin(root)
        if pod_status:
            collection_status.append(pod_status)
            record = pod_status.get("record")
            if isinstance(record, IntakeRecord):
                collected_records.append(record)
                pod_status["record"] = record.to_dict()
        if collect_api_sources and load_api_sources(root):
            api_result = run_api_sources(root, report_date)
            collection_status.extend(api_result.statuses)
            collected_records.extend(api_result.records)
    else:
        collection_status.append({"status": "skipped", "reason": "collection disabled for this run"})

    all_records = read_records(root)
    strategy_report, llm_used = build_strategy_report(
        root,
        all_records,
        collected_records,
        collection_status,
        report_date,
        use_llm=use_llm,
    )
    strategy_path = write_strategy_report(root, report_date, strategy_report)
    _, daily_report_path = generate_daily_report(root, report_date)
    return DailyRunResult(
        run_date=report_date,
        collected_records=collected_records,
        collection_status=collection_status,
        strategy_report=strategy_report,
        strategy_report_path=strategy_path,
        daily_report_path=daily_report_path,
        llm_used=llm_used,
    )


def load_watch_sources(root: Path) -> list[dict[str, Any]]:
    path = root / WATCH_SOURCE_CONFIG
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    sources = payload.get("sources", [])
    if not isinstance(sources, list):
        return []
    return [source for source in sources if isinstance(source, dict)]


def collect_source(
    root: Path,
    source: dict[str, Any],
    run_date: str,
    *,
    fetcher: Fetcher | None = None,
) -> dict[str, Any]:
    source_id = str(source.get("id") or source.get("url") or "unnamed-source").strip()
    if not source.get("enabled", False):
        return {"source_id": source_id, "status": "skipped", "reason": "source disabled"}
    if source.get("requires_login", False):
        return {
            "source_id": source_id,
            "status": "skipped",
            "reason": "requires login or restricted browser session; confirm before enabling automation",
        }

    url = str(source.get("url") or "").strip()
    if not url:
        return {"source_id": source_id, "status": "failed", "reason": "missing url"}
    if already_collected_today(root, source_id, url, run_date):
        return {"source_id": source_id, "status": "skipped", "reason": "already collected today"}

    try:
        page = (fetcher or fetch_public_page)(url)
        record = build_record_from_source(source, page, run_date)
        append_record(root, record)
        return {
            "source_id": source_id,
            "status": "collected",
            "title": page.title,
            "url": page.url,
            "record": record,
        }
    except Exception as exc:  # noqa: BLE001 - report source-level failures in the UI.
        return {"source_id": source_id, "status": "failed", "url": url, "reason": str(exc)}


def already_collected_today(root: Path, source_id: str, url: str, run_date: str) -> bool:
    for record in read_records(root):
        metadata = record.metadata or {}
        fields = record.fields or {}
        if metadata.get("automation_source_id") != source_id:
            continue
        if fields.get("url") != url and metadata.get("automation_url") != url:
            continue
        if str(metadata.get("automation_run_date") or record.created_at[:10]) == run_date:
            return True
    return False


def collect_pod_admin(root: Path) -> dict[str, Any] | None:
    config = load_pod_admin_config(root)
    if not config.enabled:
        return {"source_id": "pod-admin", "status": "skipped", "reason": "POD admin connector disabled"}
    try:
        snapshot, record = build_pod_admin_snapshot(root, persist=True)
    except Exception as exc:  # noqa: BLE001 - keep the daily run alive.
        return {"source_id": "pod-admin", "status": "failed", "reason": str(exc)}
    return {
        "source_id": "pod-admin",
        "status": "collected",
        "title": str(snapshot.fields.get("platform_name") or "POD Platform"),
        "url": str(snapshot.fields.get("admin_url") or snapshot.fields.get("base_url") or ""),
        "record": record,
    }


def fetch_public_page(url: str) -> CollectedPage:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AI-Ecommerce-Director/0.1 research reader"
            )
        },
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        content_type = response.headers.get("Content-Type", "")
        raw = response.read(1_500_000)
    encoding = "utf-8"
    match = re.search(r"charset=([\w-]+)", content_type, re.IGNORECASE)
    if match:
        encoding = match.group(1)
    html = raw.decode(encoding, errors="replace")
    return parse_html_page(url, html)


def parse_html_page(url: str, html: str) -> CollectedPage:
    parser = _SimpleHTMLCollector()
    parser.feed(html)
    parser.close()
    text = normalize_space("\n".join(parser.text_chunks))
    lines = extract_metric_lines(text)
    return CollectedPage(
        url=url,
        title=normalize_space(parser.title or ""),
        text=text[:12000],
        links=parser.links[:80],
        metric_lines=lines[:80],
    )


class _SimpleHTMLCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self._in_title = False
        self._skip_depth = 0
        self.text_chunks: list[str] = []
        self.links: list[dict[str, str]] = []
        self._current_href: str | None = None
        self._current_link_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
            return
        if tag == "title":
            self._in_title = True
        if tag == "a":
            attrs_dict = dict(attrs)
            href = attrs_dict.get("href")
            if href:
                self._current_href = href
                self._current_link_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if tag == "title":
            self._in_title = False
        if tag == "a" and self._current_href:
            text = normalize_space(" ".join(self._current_link_text))
            if text:
                self.links.append({"text": text[:180], "href": self._current_href})
            self._current_href = None
            self._current_link_text = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        clean = normalize_space(data)
        if not clean:
            return
        if self._in_title:
            self.title += clean
        else:
            self.text_chunks.append(clean)
        if self._current_href:
            self._current_link_text.append(clean)


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def extract_metric_lines(text: str) -> list[str]:
    pattern = re.compile(
        r"(GMV|sales?|sold|revenue|price|rank|ranking|growth|views?|review|rating|BSR|Best Sellers|New Releases|榜单|排名|销量|价格|评论|评分|增长)",
        re.IGNORECASE,
    )
    candidates = re.split(r"[\r\n]+|(?<=[。.!?])\s+", text)
    return [line[:500] for line in candidates if pattern.search(line)][:100]


def build_record_from_source(source: dict[str, Any], page: CollectedPage, run_date: str) -> IntakeRecord:
    record_type = canonical_record_type(str(source.get("record_type") or "hot_link"))
    fields = dict(source.get("fields") or {})
    fields.update(
        {
            "product_name": source.get("name") or page.title or source.get("id") or page.url,
            "url": page.url,
            "source_platform": source.get("source_platform") or fields.get("source_platform") or infer_source_from_url(page.url),
            "page_title": page.title,
            "page_url": page.url,
            "page_text": page.text,
            "page_links": page.links,
            "metric_lines": page.metric_lines,
            "visible_growth_signal": source.get("notes") or "Automated source snapshot.",
        }
    )
    if record_type == "platform_ranking_signal":
        fields.setdefault("marketplace", source.get("marketplace") or infer_source_from_url(page.url))
        fields.setdefault("ranking_type", source.get("ranking_type") or "Platform Ranking")
        fields.setdefault("ranking_page", page.url)
    if record_type == "viral_content_signal":
        fields.setdefault("video_url", page.url)
        fields.setdefault("product_theme", page.title or source.get("name") or "")
        fields.setdefault("content_theme", source.get("notes") or "")
    fields = normalize_fields(fields)
    score, notes = score_record(record_type, fields)
    return IntakeRecord(
        record_type=record_type,
        fields=fields,
        raw_text=json.dumps(
            {"source": source.get("id"), "url": page.url, "title": page.title, "run_date": run_date},
            ensure_ascii=False,
        ),
        source="daily_autopilot",
        score=score,
        director_notes=notes,
        metadata={
            "automation_source_id": source.get("id"),
            "automation_url": page.url,
            "automation_run_date": run_date,
            "automation_mode": "safe_read_only",
        },
    )


def build_records_from_source(source: dict[str, Any], page: CollectedPage, run_date: str) -> list[IntakeRecord]:
    record_type = canonical_record_type(str(source.get("record_type") or "hot_link"))
    if record_type == "platform_ranking_signal" and source.get("split_items", True):
        item_records = build_platform_ranking_item_records(source, page, run_date)
        if item_records:
            return item_records
    return [build_record_from_source(source, page, run_date)]


def build_platform_ranking_item_records(source: dict[str, Any], page: CollectedPage, run_date: str) -> list[IntakeRecord]:
    items = extract_platform_ranking_items(source, page)
    records: list[IntakeRecord] = []
    for item in items:
        fields = dict(source.get("fields") or {})
        fields.update(
            {
                "product_name": item["product_name"],
                "url": item["url"],
                "source_platform": source.get("source_platform") or infer_source_from_url(page.url),
                "marketplace": source.get("marketplace") or infer_source_from_url(page.url),
                "ranking_type": source.get("ranking_type") or "Platform Ranking",
                "ranking_page": page.url,
                "rank_position": item["rank_position"],
                "product_asin": item.get("product_asin", ""),
                "page_title": page.title,
                "visible_growth_signal": source.get("notes") or "Extracted from platform ranking page.",
            }
        )
        fields = normalize_fields(fields)
        score, notes = score_record("platform_ranking_signal", fields)
        records.append(
            IntakeRecord(
                record_type="platform_ranking_signal",
                fields=fields,
                raw_text=json.dumps(
                    {
                        "source": source.get("id"),
                        "ranking_page": page.url,
                        "item": item,
                        "run_date": run_date,
                    },
                    ensure_ascii=False,
                ),
                source="daily_autopilot",
                score=score,
                director_notes=notes,
                metadata={
                    "automation_source_id": source.get("id"),
                    "automation_url": page.url,
                    "automation_run_date": run_date,
                    "automation_mode": "safe_read_only",
                    "extraction_mode": "ranking_item",
                },
            )
        )
    return records


def extract_platform_ranking_items(source: dict[str, Any], page: CollectedPage) -> list[dict[str, Any]]:
    marketplace = str(source.get("marketplace") or source.get("source_platform") or infer_source_from_url(page.url)).lower()
    limit = int(source.get("item_limit", source.get("limit", 20)) or 20)
    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    for link in page.links:
        text = normalize_space(str(link.get("text") or ""))
        href = str(link.get("href") or "")
        if not is_ranking_product_link(marketplace, href, text):
            continue
        asin = extract_amazon_asin(href) if "amazon" in marketplace else ""
        absolute_url = urljoin(page.url, href)
        key = asin or absolute_url
        if key in seen:
            continue
        seen.add(key)
        items.append(
            {
                "rank_position": len(items) + 1,
                "product_name": text[:220],
                "url": absolute_url,
                "product_asin": asin,
            }
        )
        if len(items) >= limit:
            break
    return items


def is_ranking_product_link(marketplace: str, href: str, text: str) -> bool:
    if len(text) < 8:
        return False
    lowered_text = text.lower()
    if any(
        signal in lowered_text
        for signal in [
            "out of 5 stars",
            "offers from",
            "see more",
            "start over",
            "previous page",
            "next page",
            "customer support",
            "best sellers",
            "new releases",
        ]
    ):
        return False
    if "amazon" in marketplace:
        return bool(extract_amazon_asin(href))
    return any(signal in href.lower() for signal in ["/product", "/item", "/listing", "/dp/"])


def extract_amazon_asin(href: str) -> str:
    match = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})(?:[/?#]|$)", href)
    return match.group(1) if match else ""


def infer_source_from_url(url: str) -> str:
    lowered = url.lower()
    if "amazon" in lowered:
        return "Amazon"
    if "tiktok" in lowered:
        return "TikTok"
    if "fastmoss" in lowered:
        return "FastMoss"
    if "kalodata" in lowered:
        return "Kalodata"
    if "echotik" in lowered:
        return "EchoTik"
    if "etsy" in lowered:
        return "Etsy"
    if "walmart" in lowered:
        return "Walmart"
    if "shein" in lowered:
        return "SHEIN"
    return "Web"


def build_strategy_report(
    root: Path,
    all_records: list[IntakeRecord],
    collected_records: list[IntakeRecord],
    collection_status: list[dict[str, Any]],
    run_date: str,
    *,
    use_llm: bool = True,
) -> tuple[str, bool]:
    fallback = build_rule_based_strategy(root, all_records, collected_records, collection_status, run_date)
    if not use_llm:
        return fallback, False
    client = LLMClient(root=root, task="strategy")
    if not client.enabled:
        return fallback + "\n\n## 模型状态\n\n- 尚未配置 Kiro / OpenAI-compatible 模型，当前使用规则版 AI 巡检。\n", False

    try:
        model_output = client.chat(
            build_system_prompt(),
            json.dumps(
                {
                    "run_date": run_date,
                    "collection_status": scrub_status(collection_status),
                    "collected_records": [record.to_dict() for record in collected_records],
                    "recent_records": [record.to_dict() for record in sort_by_priority(all_records)[:30]],
                    "base_report": fallback,
                },
                ensure_ascii=False,
            ),
        )
    except Exception as exc:  # noqa: BLE001 - keep the run useful when model endpoint fails.
        return fallback + f"\n\n## 模型状态\n\n- 模型调用失败，已回退到规则版巡检：{exc}\n", False
    return fallback + "\n\n## 模型深度拆解\n\n" + model_output.strip() + "\n", True


def build_system_prompt() -> str:
    return (
        "You are AI Ecommerce Director, a cross-border ecommerce growth and BD director. "
        "Analyze marketplace rankings, viral content, creator signals, store profiles, supply chain data, "
        "POD admin snapshots, OMS fulfillment signals, and selection playbooks. Output practical Chinese recommendations. "
        "Never claim you changed a store. For listing upload, discount setup, campaign signup, creator outreach, "
        "login, CAPTCHA, payments, or account settings, only propose the next action and mark it as needing user confirmation."
    )


def build_rule_based_strategy(
    root: Path,
    all_records: list[IntakeRecord],
    collected_records: list[IntakeRecord],
    collection_status: list[dict[str, Any]],
    run_date: str,
) -> str:
    grouped = group_records(all_records)
    priority_records = sort_by_priority(
        [
            *grouped.get("viral_content_signal", []),
            *grouped.get("video_breakdown", []),
            *grouped.get("hot_link", []),
            *grouped.get("platform_ranking_signal", []),
        ]
    )[:8]
    store_profiles = sort_by_priority(grouped.get("store_profile", []))[:8]
    supply = sort_by_priority(grouped.get("supply_chain", []))[:5]
    pod_snapshots = sort_by_priority(grouped.get("pod_admin_snapshot", []))[:3]

    lines: list[str] = [
        "# AI 自动运营总监巡检报告",
        "",
        f"日期：{run_date}",
        "",
        "## 今日自动采集状态",
        "",
    ]
    if collection_status:
        for status in collection_status:
            lines.append(f"- {status.get('source_id', 'source')}：{status.get('status')}，{status.get('reason') or status.get('title') or ''}")
    else:
        lines.append("- 暂无配置采集源。")
    lines.extend(["", "## 今日优先拆解对象", ""])
    if priority_records:
        for record in priority_records:
            lines.append(f"- {record_label(record)}｜优先级 {record.score.get('priority', '待定')}｜{record.fields.get('source_platform') or record.source}")
    else:
        lines.append("- 暂无爆款内容、榜单或链接。先配置采集源，或用插件采集 FastMoss / Kalodata / EchoTik / Amazon / TikTok Shop 页面。")

    lines.extend(["", "## 自动拆解结论", ""])
    lines.extend(build_breakdown_lines(priority_records))
    lines.extend(["", "## POD管理员端观察", ""])
    lines.extend(build_pod_admin_lines(pod_snapshots))
    lines.extend(["", "## 今日脚本方向", ""])
    lines.extend(build_script_lines(priority_records))
    lines.extend(["", "## 可应用到店铺的动作", ""])
    lines.extend(build_store_application_lines(store_profiles, supply, priority_records, pod_snapshots))
    lines.extend(["", "## 需要你确认后才能执行", ""])
    lines.extend(
        [
            "- 自动登录店铺、过验证、处理验证码。",
            "- 上架商品、修改标题/主图/价格/库存。",
            "- 设置折扣、报名活动、开启广告、调整预算。",
            "- 联系达人、发送消息、上传素材、提交申诉。",
            "- 购买 IP 节点、修改比特浏览器窗口配置、改变店铺主体资料。",
        ]
    )
    lines.extend(["", "## 下一步配置建议", ""])
    lines.extend(
        [
            "- 把 Amazon Best Sellers / New Releases、TikTok Shop 榜单、FastMoss、Kalodata、EchoTik 的固定观察页加入 `config/watch_sources.json`。",
            "- 给每个店铺补齐 store_profile：国家、平台、货币、时区、Bit 窗口、IP 区域、履约模式。",
            "- 给 POD 管理员端补齐底板、成本、库存、工厂产能和生产工单数据，让爆款内容能反推到可生产 SKU。",
            "- 配置 Kiro 或 OpenAI-compatible 模型环境变量后，巡检报告会追加“模型深度拆解”。",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def group_records(records: list[IntakeRecord]) -> dict[str, list[IntakeRecord]]:
    grouped: dict[str, list[IntakeRecord]] = {}
    for record in records:
        grouped.setdefault(record.record_type, []).append(record)
    return grouped


def sort_by_priority(records: list[IntakeRecord]) -> list[IntakeRecord]:
    return sorted(records, key=lambda record: float(record.score.get("priority", 0) or 0), reverse=True)


def record_label(record: IntakeRecord) -> str:
    fields = record.fields
    for key in [
        "product_name",
        "product_theme",
        "content_theme",
        "video_url",
        "creator_handle",
        "marketplace",
        "ranking_type",
        "url",
        "store_id",
        "platform_name",
        "admin_url",
        "base_url",
    ]:
        value = fields.get(key)
        if value:
            return str(value)[:160]
    return record.record_id[:8]


def build_breakdown_lines(records: list[IntakeRecord]) -> list[str]:
    if not records:
        return ["- 暂无可拆解对象。"]
    lines: list[str] = []
    for record in records[:5]:
        fields = record.fields
        label = record_label(record)
        if record.record_type == "platform_ranking_signal":
            ranking_type = fields.get("ranking_type") or "榜单"
            lines.append(f"- {label}：来自 {ranking_type}，先反推类目需求、关键词、价格带、评论痛点和可替代供应链。")
        elif record.record_type in {"viral_content_signal", "video_breakdown"}:
            lines.append(f"- {label}：优先拆 0-2 秒钩子、镜头顺序、身份人群、场景、情绪和评论区购买原因。")
        else:
            lines.append(f"- {label}：先判断它是产品爆、达人爆、素材爆还是平台推荐爆，再决定是否复刻。")
    return lines


def build_script_lines(records: list[IntakeRecord]) -> list[str]:
    themes = [extract_theme(record) for record in records]
    themes = [theme for theme in themes if theme]
    if not themes:
        themes = ["Blue Collar Dad", "Dog Dad", "Fishing Dad"]
    lines: list[str] = []
    for theme in themes[:5]:
        lines.append(f"- {theme}｜店铺自播版：开头 2 秒给身份共鸣；中段必须拍清产品版型、面料、上身/使用场景；结尾用限时优惠、送礼理由或店铺商品卡 CTA 承接。")
        lines.append(f"- {theme}｜店铺脚本：Nobody talks about people like us. This is for the dads who show up every day.")
        lines.append(f"- {theme}｜达人合作版：保留达人真实生活语气，给 3 个必拍镜头和 1 个必说卖点，其余让达人自由发挥；结尾挂车或评论区引导。")
        lines.append(f"- {theme}｜达人脚本：I did not expect this shirt to hit this hard. It feels like something made for people like us.")
    return lines[:10]


def extract_theme(record: IntakeRecord) -> str:
    fields = record.fields
    for key in ["product_theme", "content_theme", "product_name", "hook_text", "category_path"]:
        value = fields.get(key)
        if value:
            return str(value)[:80]
    return ""


def build_pod_admin_lines(pod_snapshots: list[IntakeRecord]) -> list[str]:
    if not pod_snapshots:
        return ["- 暂无 POD 管理员端快照。先在 `/pod-admin` 生成一次，或保持自动巡检开启。"]
    lines: list[str] = []
    for record in pod_snapshots:
        fields = record.fields
        platform = fields.get("platform_name") or "POD Platform"
        lines.append(
            f"- {platform}：底板 {fields.get('blank_count', 0)}，作品 {fields.get('design_count', 0)}，订单 {fields.get('order_count', 0)}，"
            f"待生产 {fields.get('pending_print_job_count', 0)}，异常 {fields.get('exception_job_count', 0)}，低库存SKU {fields.get('low_stock_sku_count', 0)}。"
        )
        lines.append(
            f"- 渠道中台：接口 {fields.get('channel_analytics_status', 'unknown')}，支持渠道 {fields.get('supported_channel_count', 0)}，"
            f"渠道订单 {fields.get('channel_orders', 0)}，渠道销售 {fields.get('channel_sales', 0)}，待上架同步 {fields.get('channel_pending_listing_count', 0)}，待发货同步 {fields.get('channel_pending_shipment_count', 0)}。"
        )
        lines.append(
            f"- 平台代运营：已申请 {fields.get('platform_ops_opt_in_count', 0)}，待审核 {fields.get('platform_ops_pending_count', 0)}，未达标 {fields.get('platform_ops_below_target_count', 0)}。"
        )
        for action in fields.get("recommended_actions", [])[:2] if isinstance(fields.get("recommended_actions"), list) else []:
            lines.append(f"- POD建议：{action}")
    return lines


def build_store_application_lines(
    store_profiles: list[IntakeRecord],
    supply: list[IntakeRecord],
    priority_records: list[IntakeRecord],
    pod_snapshots: list[IntakeRecord],
) -> list[str]:
    lines: list[str] = []
    if store_profiles:
        for store in store_profiles[:5]:
            fields = store.fields
            store_name = fields.get("store_id") or fields.get("store_name") or "未命名店铺"
            country = fields.get("country_code") or fields.get("shop_region") or "未知国家"
            lines.append(f"- {store_name}（{country}）：先匹配榜单趋势与当地履约能力，再输出 Listing、素材和达人方向。")
    else:
        lines.append("- 还没有完整店铺档案，无法判断哪个店最适合承接今天的爆款方向。")
    if supply:
        lines.append("- 供应链优先级：优先选择有库存、成本低、能快速发货、合规风险低的款。")
    if pod_snapshots:
        pod = pod_snapshots[0].fields
        lines.append(
            f"- POD承接能力：先看底板 {pod.get('blank_count', 0)}、作品 {pod.get('design_count', 0)}、待生产 {pod.get('pending_print_job_count', 0)}、低库存SKU {pod.get('low_stock_sku_count', 0)}，再决定今天哪些爆款方向能复制到自有POD平台。"
        )
        lines.append(
            f"- POD渠道承接：渠道接口状态 {pod.get('channel_analytics_status', 'unknown')}，先用 TikTok/SHEIN/Shopee/Lazada/Amazon/Etsy/Walmart/eBay/Shopify/WooCommerce 做上架优先级建议；真正发布、下架、同步发货前等你确认。"
        )
    if priority_records:
        lines.append("- 今日候选品不要直接上架，先用选品SOP检查趋势、生命周期、评论、侵权、物流和价格带。")
    return lines


def scrub_status(statuses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scrubbed: list[dict[str, Any]] = []
    for status in statuses:
        item = dict(status)
        if isinstance(item.get("record"), IntakeRecord):
            item["record"] = item["record"].to_dict()
        scrubbed.append(item)
    return scrubbed


def write_strategy_report(root: Path, report_date: str, content: str) -> Path:
    output_dir = root / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{AUTOPILOT_REPORT_PREFIX}_{report_date}.md"
    path.write_text(content, encoding="utf-8")
    return path


def latest_autopilot_report(root: Path) -> tuple[str, Path | None]:
    output_dir = root / "outputs"
    paths = sorted(output_dir.glob(f"{AUTOPILOT_REPORT_PREFIX}_*.md"), reverse=True)
    if not paths:
        return "还没有 AI 自动巡检报告。点击“运行今日AI巡检”先跑一次。", None
    path = paths[0]
    return path.read_text(encoding="utf-8"), path
