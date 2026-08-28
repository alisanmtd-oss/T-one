from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}


def _metric_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if value >= 0 else None
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "")
        if re.fullmatch(r"\d+(?:\.\d+)?", cleaned):
            return float(cleaned)
    return None


def _performance_evidence(performance: dict[str, Any]) -> dict[str, Any]:
    views = _metric_number(performance.get("views"))
    baseline = _metric_number(performance.get("account_baseline_views"))
    interactions = sum(
        value or 0
        for value in (
            _metric_number(performance.get("likes")),
            _metric_number(performance.get("comments")),
            _metric_number(performance.get("shares")),
            _metric_number(performance.get("saves")),
        )
    )
    normalized = {
        "views": views,
        "account_baseline_views": baseline,
        "baseline_multiple": round(views / baseline, 3) if views is not None and baseline else None,
        "engagement_rate": round(interactions / views, 5) if views else None,
        "paid_or_organic": str(performance.get("paid_or_organic") or "unknown"),
        "post_age_hours": _metric_number(performance.get("post_age_hours")),
    }
    has_source = bool(performance.get("source_url") or performance.get("source_file"))
    has_comparison = views is not None and baseline is not None and baseline > 0
    is_outlier = bool(has_source and has_comparison and views >= baseline * 3)
    if is_outlier:
        claim_status = "evidence_backed_outlier"
        claim_label = "有证据的异常高表现内容"
    elif has_source and views is not None:
        claim_status = "performance_observed_not_normalized"
        claim_label = "已观察表现，但缺少账号基线，不能断言爆款"
    else:
        claim_status = "high_potential_unverified"
        claim_label = "仅可称为高潜结构，不能断言爆款"
    return {
        "claim_status": claim_status,
        "claim_label": claim_label,
        "normalized_metrics": normalized,
        "missing_evidence": [
            field
            for field, present in (
                ("source_url_or_file", has_source),
                ("views", views is not None),
                ("account_baseline_views", baseline is not None and baseline > 0),
                ("paid_or_organic", normalized["paid_or_organic"] != "unknown"),
                ("post_age_hours", normalized["post_age_hours"] is not None),
            )
            if not present
        ],
    }


def build_creative_variation_plan(
    *,
    product_facts: dict[str, Any],
    observations: dict[str, Any] | None = None,
    performance: dict[str, Any] | None = None,
    platform: str = "TikTok Shop",
    country_site: str = "US",
) -> dict[str, Any]:
    """Turn a reference structure into original, measurable creative branches.

    Product facts are immutable anchors. Observations are hypotheses until a
    reviewer confirms them, and performance evidence controls whether the
    reference may be described as an outlier rather than merely high-potential.
    """
    observed = observations if isinstance(observations, dict) else {}
    evidence = _performance_evidence(performance if isinstance(performance, dict) else {})
    protected_anchors = {
        "product_facts": dict(product_facts),
        "platform": platform,
        "country_site": country_site,
        "rights_constraints": [
            "不复制原视频人物、商标、台词、受保护画面或未授权音乐",
            "不改变商品颜色、材质、件数、尺码关系、功能或履约事实",
            "没有证据的效果、销量、评价或承诺不得写入脚本",
        ],
    }
    shared = {
        "reference_hook": str(observed.get("hook_0_3s") or "待视觉复核"),
        "reference_proof": str(observed.get("proof_type") or "待视觉复核"),
        "reference_pace": str(observed.get("edit_rhythm") or "待视觉复核"),
        "reference_cta": str(observed.get("cta") or "待视觉复核"),
        "unknowns": list(observed.get("unknowns") or []),
    }
    branch_specs = [
        (
            "control_structure",
            ["visual_style", "shot_order", "cta"],
            "保留经确认的节奏机制，同时用全新的场景、镜头顺序和 CTA 建立原创对照组。",
            ["原创场景建立", "真实商品动作证明", "与承接页一致的 CTA"],
        ),
        (
            "pain_hook",
            ["hook", "audience", "shot_order"],
            "明确的真实痛点比泛化开场更能提升前三秒留存。",
            ["痛点一句话", "立即展示商品如何参与解决", "近景事实证明"],
        ),
        (
            "result_hook",
            ["hook", "proof", "pacing"],
            "先展示可验证结果，再回到过程证明，可提高继续观看意愿。",
            ["真实结果先行", "过程拆解", "商品事实与限制说明"],
        ),
        (
            "identity_hook",
            ["hook", "audience", "use_case"],
            "用具体人群与使用场景开场，可提高目标受众的自我识别。",
            ["人群身份开场", "具体场景", "商品动作与适用边界"],
        ),
        (
            "proof_first",
            ["proof", "shot_order", "camera_language"],
            "把材质、做工、上身或设备结果等可见证据前置，可提升信任和点击质量。",
            ["微距或实拍证据", "完整商品关系", "购买前必须知道的事实"],
        ),
        (
            "visual_novelty",
            ["visual_style", "camera_language", "transition"],
            "在不改变商品事实的前提下，用原创构图、运镜和转场制造视觉新鲜感。",
            ["原创视觉钩子", "动作匹配转场", "稳定清楚的商品收尾"],
        ),
    ]
    branches = []
    for branch_id, axes, hypothesis, storyboard in branch_specs:
        branches.append(
            {
                "id": branch_id,
                "modified_axes": axes,
                "originality_change_count": len(axes),
                "hypothesis": hypothesis,
                "storyboard_focus": storyboard,
                "prompt_rule": "只使用 protected_anchors 中的已确认商品事实；未确认字段留空或标记待核。",
                "primary_metric": "3秒留存率",
                "secondary_metrics": ["完播率", "点击率", "加购或询盘率"],
                "stop_rule": "达到项目设定的最小样本量后，若主指标和成交相关指标均不优于对照组，则停止该分支。",
            }
        )
    return {
        "schema_version": 1,
        "evidence": evidence,
        "reference_observations": shared,
        "protected_anchors": protected_anchors,
        "minimum_originality_changes": 3,
        "branches": branches,
        "review_gates": ["visual_fact_review", "brand_review", "rights_review", "platform_policy_review", "publish_approval"],
    }


def build_image_prompt_reconstruction(
    *,
    subject_facts: dict[str, Any],
    visible_facts: dict[str, Any] | None = None,
    visual_inferences: dict[str, Any] | None = None,
    unknowns: list[str] | None = None,
    objective: str = "商品图片",
    aspect_ratio: str = "1:1",
) -> dict[str, Any]:
    """Build a prompt from reviewed image evidence without filling unknown facts."""
    visible = visible_facts if isinstance(visible_facts, dict) else {}
    inferred = visual_inferences if isinstance(visual_inferences, dict) else {}
    missing = [str(item) for item in (unknowns or []) if str(item).strip()]
    fact_lines = [f"{key}: {value}" for key, value in subject_facts.items() if value not in (None, "", [])]
    visual_lines = [f"{key}: {value}" for key, value in visible.items() if value not in (None, "", [])]
    prompt_parts = [
        f"目标：{objective}，画幅 {aspect_ratio}。",
        "商品事实：" + ("；".join(fact_lines) if fact_lines else "未提供，停止生成并补充真实商品资料。"),
        "已核对画面事实：" + ("；".join(visual_lines) if visual_lines else "待视觉复核。"),
        "保持商品颜色、材质、数量、结构、比例、文字和品牌标识与已确认素材一致。",
        "只复用构图、光线、镜头语言和信息层级，不复制参考图的人物身份、商标、受保护布景或独特创作表达。",
    ]
    return {
        "schema_version": 1,
        "evidence_map": {
            "subject_facts": dict(subject_facts),
            "visible_facts": visible,
            "visual_inferences": inferred,
            "unknowns": missing,
        },
        "consistency_anchors": list(subject_facts.keys()),
        "prompt": "\n".join(prompt_parts),
        "inference_rule": "visual_inferences仅供复核，不自动写入事实提示词。",
        "negative_constraints": [
            "不改变商品颜色、材质、数量、结构、比例或文字",
            "不补写未知品牌、性能、评价、销量或认证",
            "不复制参考图人物、商标、受保护场景或独特表达",
            "不使用无法证明授权的素材或音乐",
        ],
        "ready_for_generation": bool(fact_lines) and not missing,
        "review_gates": ["product_fact_review", "visual_fact_review", "brand_and_rights_review"],
    }


def load_capabilities(root: Path) -> dict[str, Any]:
    path = root / "config" / "creative_video_capabilities.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def resolve_generation_route(root: Path, route_id: str = "") -> dict[str, Any]:
    """Resolve a configured generation route without claiming external access."""
    config = load_capabilities(root)
    routes = [
        item for item in config.get("generation_routes", [])
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    ]
    if not routes:
        routes = [
            {
                "id": "local_prompt_only",
                "label": "本地提示词与分镜导出",
                "provider": "local",
                "mode": "local_prompt_export",
                "connection_state": "available",
                "default": True,
                "prompt_export_available": True,
                "external_generation_available": False,
                "owner_configuration_required": False,
                "note": "在本机生成提示词，不调用外部生成服务。",
            }
        ]
    requested = str(route_id or "").strip().lower()
    if requested:
        route = next(
            (item for item in routes if str(item.get("id") or "").strip().lower() == requested),
            None,
        )
        if route is None:
            return {
                "id": requested,
                "label": requested,
                "connection_state": "unknown_route",
                "prompt_export_available": False,
                "external_generation_available": False,
                "owner_configuration_required": True,
                "ready_for_prompt_export": False,
                "ready_for_external_generation": False,
                "external_action_performed": False,
                "reason": "生成路线不存在，已阻止猜测供应商或模型。",
            }
    else:
        route = next((item for item in routes if item.get("default") is True), routes[0])
    result = dict(route)
    state = str(result.get("connection_state") or "not_configured")
    prompt_ready = bool(result.get("prompt_export_available"))
    external_ready = bool(result.get("external_generation_available")) and state == "connected"
    result.update(
        {
            "ready_for_prompt_export": prompt_ready,
            "ready_for_external_generation": external_ready,
            "external_action_performed": False,
            "reason": (
                "本地提示词与分镜可直接生成。"
                if state == "available" and prompt_ready
                else "当前仅可导出提示词；负责人完成账号、地区、计费、条款和素材上传边界配置前不调用外部生成。"
            ),
        }
    )
    return result


def _task_product_type(task_context: dict[str, Any]) -> str:
    explicit = str(task_context.get("product_type") or "").strip().lower()
    if explicit:
        return explicit
    task_id = str(task_context.get("task_id") or task_context.get("id") or "").lower()
    product_id = str(task_context.get("product_id") or "").lower()
    if "machine" in task_id or "machine" in product_id or "printer" in product_id:
        return "equipment"
    if product_id == "10001" or any(token in task_id for token in ("apparel", "shirt", "tee")):
        return "apparel"
    return "unknown"


def evaluate_template_gate(
    root: Path,
    template_id: str,
    task_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = task_context if isinstance(task_context, dict) else {}
    config = load_capabilities(root)
    templates = [item for item in config.get("templates", []) if isinstance(item, dict)]
    template = next((item for item in templates if str(item.get("id") or "") == template_id), None)
    if template is None:
        return {
            "allowed": False,
            "template": {},
            "template_id": template_id,
            "product_type": _task_product_type(context),
            "reasons": ["模板不存在或已停用"],
        }

    reasons: list[str] = []
    product_type = _task_product_type(context)
    allowed_types = [str(value).strip().lower() for value in template.get("product_types", []) if str(value).strip()]
    if allowed_types and product_type not in allowed_types:
        labels = {"apparel": "服装", "equipment": "设备"}
        expected = "、".join(labels.get(value, value) for value in allowed_types)
        actual = labels.get(product_type, product_type or "未知")
        reasons.append(f"只适用于{expected}，当前任务是{actual}")

    flag_labels = {
        "warehouse_media_verified": "真实仓库素材尚未核验",
        "equipment_specs_verified": "设备规格与产能数据尚未核验",
        "equipment_demo_media_verified": "设备实拍演示素材尚未核验",
    }
    for flag in template.get("required_context_flags", []):
        key = str(flag).strip()
        if key and context.get(key) is not True:
            reasons.append(flag_labels.get(key, f"缺少事实条件：{key}"))

    if template.get("requires_us_warehouse_location"):
        state = load_json_file(root / "outputs" / "amazon_10001_operating_state_latest.json")
        fulfillment = state.get("fulfillment") if isinstance(state.get("fulfillment"), dict) else {}
        if fulfillment.get("us_warehouse_location_configured") is not True:
            reasons.append("Amazon 权威状态中尚未配置已核准的美国仓发货地")

    return {
        "allowed": not reasons,
        "template": template,
        "template_id": template_id,
        "product_type": product_type,
        "reasons": reasons,
    }


def load_json_file(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _version_key(path: Path) -> tuple[int, ...]:
    numbers = re.findall(r"\d+", path.parent.name)
    return tuple(int(value) for value in numbers) if numbers else (0,)


def find_capcut() -> Path | None:
    local = Path.home() / "AppData" / "Local" / "CapCut" / "Apps"
    candidates = list(local.glob("*/CapCut.exe"))
    direct = local / "CapCut.exe"
    if direct.exists():
        candidates.append(direct)
    return max(candidates, key=_version_key) if candidates else None


def find_ffmpeg() -> Path | None:
    system = shutil.which("ffmpeg")
    if system:
        return Path(system)
    capcut = find_capcut()
    if capcut:
        bundled = capcut.parent / "ffmpeg.exe"
        if bundled.exists():
            return bundled
    return None


def detect_toolchain(root: Path) -> list[dict[str, Any]]:
    config = load_capabilities(root)
    configured = {
        str(item.get("id")): item
        for item in config.get("tools", [])
        if isinstance(item, dict) and item.get("id")
    }
    capcut = find_capcut()
    ffmpeg = find_ffmpeg()
    runtime = {
        "capcut": {"available": bool(capcut), "path": str(capcut or "")},
        "ffmpeg": {"available": bool(ffmpeg), "path": str(ffmpeg or "")},
        "pyscenedetect": {"available": False, "path": ""},
        "whisper_cpp": {"available": False, "path": ""},
        "remotion": {"available": False, "path": ""},
        "opentimelineio": {"available": False, "path": ""},
        "librosa": {"available": False, "path": ""},
        "opencut": {"available": False, "path": ""},
    }
    result = []
    for tool_id, details in runtime.items():
        item = configured.get(tool_id, {})
        result.append({
            "id": tool_id,
            "role": str(item.get("role") or ""),
            "decision": str(item.get("decision") or "unconfigured"),
            **details,
        })
    return result


def _run_ffmpeg(ffmpeg: Path, arguments: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(ffmpeg), *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        check=False,
    )


def _technical_metadata(ffmpeg: Path, video: Path) -> dict[str, Any]:
    result = _run_ffmpeg(ffmpeg, ["-hide_banner", "-i", str(video)], timeout=45)
    raw = "\n".join([result.stdout, result.stderr])
    duration_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", raw)
    duration = 0.0
    if duration_match:
        hours, minutes, seconds = duration_match.groups()
        duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    video_line = next((line for line in raw.splitlines() if "Video:" in line), "")
    resolution_match = re.search(r"(?<!\d)(\d{2,5})x(\d{2,5})(?!\d)", video_line)
    fps_match = re.search(r"(\d+(?:\.\d+)?)\s*fps", video_line)
    width = int(resolution_match.group(1)) if resolution_match else 0
    height = int(resolution_match.group(2)) if resolution_match else 0
    return {
        "duration_seconds": round(duration, 3),
        "width": width,
        "height": height,
        "aspect_ratio": f"{width}:{height}" if width and height else "unknown",
        "fps": float(fps_match.group(1)) if fps_match else 0.0,
        "audio_present": any("Audio:" in line for line in raw.splitlines()),
    }


def _scene_times(ffmpeg: Path, video: Path) -> list[float]:
    result = _run_ffmpeg(
        ffmpeg,
        [
            "-hide_banner", "-i", str(video), "-vf",
            "select='gt(scene,0.28)',showinfo", "-an", "-f", "null", "NUL",
        ],
        timeout=180,
    )
    raw = "\n".join([result.stdout, result.stderr])
    values = []
    for match in re.finditer(r"pts_time:([0-9.]+)", raw):
        value = round(float(match.group(1)), 3)
        if value > 0 and (not values or abs(value - values[-1]) > 0.15):
            values.append(value)
    return values[:40]


def _capture_frames(ffmpeg: Path, video: Path, output_dir: Path, times: list[float], duration: float) -> list[Path]:
    uniform_times = []
    if duration > 0:
        count = min(9, max(5, int(duration // 3) + 1))
        uniform_times = [round(duration * index / max(1, count - 1), 3) for index in range(count)]
    combined = sorted([0.0, *uniform_times, *times])
    unique_times: list[float] = []
    for value in combined:
        if not unique_times or abs(value - unique_times[-1]) > 0.35:
            unique_times.append(value)
    frames = []
    for index, timestamp in enumerate(unique_times[:12], start=1):
        target = output_dir / f"frame_{index:02d}_{timestamp:.2f}s.jpg"
        result = _run_ffmpeg(
            ffmpeg,
            ["-hide_banner", "-loglevel", "error", "-ss", str(timestamp), "-i", str(video), "-frames:v", "1", "-vf", "scale=640:-2", "-y", str(target)],
            timeout=60,
        )
        if result.returncode == 0 and target.exists():
            frames.append(target)
    return frames


def _contact_sheet(frames: list[Path], target: Path) -> Path | None:
    if not frames:
        return None
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None
    loaded = []
    for path in frames:
        try:
            image = Image.open(path).convert("RGB")
            image.thumbnail((360, 240))
            loaded.append((path, image.copy()))
        except OSError:
            continue
    if not loaded:
        return None
    columns = 3
    cell_width, cell_height = 380, 285
    rows = (len(loaded) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * cell_width, rows * cell_height), "white")
    draw = ImageDraw.Draw(sheet)
    font_path = Path(r"C:\Windows\Fonts\msyh.ttc")
    font = ImageFont.truetype(str(font_path), 18) if font_path.exists() else ImageFont.load_default()
    for index, (path, image) in enumerate(loaded):
        x = (index % columns) * cell_width
        y = (index // columns) * cell_height
        sheet.paste(image, (x + (cell_width - image.width) // 2, y + 8))
        draw.text((x + 12, y + 252), path.stem.replace("frame_", "镜头 "), fill="#222222", font=font)
    sheet.save(target, quality=90)
    return target


def _clean_subtitle_text(raw: str) -> str:
    lines: list[str] = []
    for line in raw.replace("\ufeff", "").splitlines():
        value = line.strip()
        if not value or value.isdigit() or "-->" in value:
            continue
        value = re.sub(r"<[^>]+>", "", value).strip()
        if value and (not lines or lines[-1] != value):
            lines.append(value)
    return "\n".join(lines)[:20000]


def _extract_embedded_subtitles(ffmpeg: Path, video: Path, output_dir: Path) -> dict[str, Any]:
    """Prefer an embedded subtitle track before considering any transcription route."""

    target = output_dir / "embedded_subtitles.srt"
    result = _run_ffmpeg(
        ffmpeg,
        [
            "-hide_banner", "-loglevel", "error", "-i", str(video),
            "-map", "0:s:0?", "-c:s", "srt", "-y", str(target),
        ],
        timeout=90,
    )
    if result.returncode != 0 or not target.is_file() or target.stat().st_size == 0:
        target.unlink(missing_ok=True)
        return {
            "status": "no_embedded_subtitle_track",
            "text": "",
            "path": "",
            "sha256": "",
        }
    raw = target.read_text(encoding="utf-8", errors="replace")
    text = _clean_subtitle_text(raw)
    if not text:
        return {
            "status": "subtitle_track_empty",
            "text": "",
            "path": str(target),
            "sha256": _sha256_file(target),
        }
    return {
        "status": "embedded_subtitle_extracted",
        "text": text,
        "path": str(target),
        "sha256": _sha256_file(target),
    }


def build_prompt_pack(
    root: Path,
    *,
    template_id: str = "ugc-pain-solution-15",
    product: str = "当前商品",
    platform: str = "TikTok Shop",
    country: str = "US",
    observations: dict[str, Any] | None = None,
    task_context: dict[str, Any] | None = None,
) -> str:
    config = load_capabilities(root)
    templates = [item for item in config.get("templates", []) if isinstance(item, dict)]
    if not templates:
        raise ValueError("没有可用的视频模板配置。")
    gate = evaluate_template_gate(root, template_id, task_context)
    if not gate.get("allowed"):
        reasons = "；".join(str(item) for item in gate.get("reasons") or [])
        raise ValueError(f"模板“{template_id}”当前不可用：{reasons}")
    template = gate.get("template") if isinstance(gate.get("template"), dict) else {}
    observations = observations or {}
    context = task_context if isinstance(task_context, dict) else {}
    generation_route = resolve_generation_route(
        root, str(context.get("generation_route_id") or "")
    )
    if not generation_route.get("ready_for_prompt_export"):
        raise ValueError(str(generation_route.get("reason") or "生成路线不可用。"))
    structure = "\n".join(f"{index}. {step}" for index, step in enumerate(template.get("structure", []), start=1))
    return f"""# AI 视频提示词包

## 任务
- 平台/站点：{platform} / {country}
- 商品：{product}
- 目标：在保持商品真实颜色、材质、件数和版型的前提下，生成可测试的带货短视频。
- 时长/画幅：{template.get('duration_seconds', 15)} 秒 / {template.get('aspect_ratio', '9:16')}
- 模板：{template.get('name', template_id)}
- 生成路线：{generation_route.get('label', generation_route.get('id', '本地提示词导出'))}
- 路线状态：{generation_route.get('connection_state', 'unknown')}；{generation_route.get('reason', '')}
- 本次外部生成：未执行

## 同行结构观察
- 前3秒钩子：{observations.get('hook_0_3s', '先写明真实痛点、结果或身份场景，禁止空泛开场。')}
- 节奏：{observations.get('edit_rhythm', '前3秒快切，中段用可看清的产品动作证明，结尾停留CTA。')}
- 可复用模式：{observations.get('reusable_pattern', '复用结构和节奏，不复制商标、人物、台词、画面或音乐。')}

## 分镜
{structure}

## 生成提示词
真实商业短视频，{template.get('aspect_ratio', '9:16')}，总时长 {template.get('duration_seconds', 15)} 秒。主角清楚展示“{product}”，商品颜色、材质纹理、数量、尺码关系和版型必须与参考素材一致。镜头按上述分镜推进：先给可理解的痛点或结果，再给连续的产品动作与近景证据，最后给自然的购买场景。使用真实室内或仓库光线，肤色与商品色不漂移，镜头稳定但保留轻微手持感，字幕避开商品主体和平台按钮区域。剪辑在动作点和音乐重拍处切换，保留足够时间看清面料、做工、上身或设备结果。

## 剪辑与声音
- 字幕：每屏一句，关键词高亮，不遮挡商品。
- 音乐：只使用自有、委托、平台商用曲库或已购买商业授权的音轨。
- 声音结构：0-3秒用短促起拍；证明段降低音乐给环境声/旁白；CTA恢复节拍。
- 禁止：抓取同行原音、复制同行台词、伪造测评、夸大承诺、改变商品件数或颜色。

## 变体测试
1. 痛点钩子版：先说使用前的真实问题。
2. 结果钩子版：先展示成品/上身/打印结果。
3. 身份场景版：先说明“给谁、在什么场景使用”。
"""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _deconstruction_brief(result: dict[str, Any]) -> str:
    metadata = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
    subtitles = result.get("subtitles") if isinstance(result.get("subtitles"), dict) else {}
    semantics = result.get("visual_semantics") if isinstance(result.get("visual_semantics"), dict) else {}
    frame_rows = []
    for index, frame in enumerate(result.get("frame_files") or [], start=1):
        match = re.search(r"_([0-9.]+)s\.jpg$", str(frame))
        timestamp = match.group(1) if match else "待核"
        frame_rows.append(f"| {index} | {timestamp}s | 待视觉复核 | 待填写 | 待填写 | 待填写 |")
    rows = "\n".join(frame_rows) or "| 1 | 0.00s | 待视觉复核 | 待填写 | 待填写 | 待填写 |"
    return f"""# 同行视频拆解复核表

## 证据
- 文件：`{result.get('source_file', '')}`
- SHA256：`{result.get('source_sha256', '')}`
- 分析时间：{result.get('analyzed_at', '')}
- 原则：技术字段来自工具；画面含义、钩子和商业判断必须由视觉模型或负责人复核，不能把推断写成事实。

## 技术结构
- 时长：{metadata.get('duration_seconds', 0)} 秒
- 分辨率：{metadata.get('width', 0)} × {metadata.get('height', 0)}
- 帧率：{metadata.get('fps', 0)} fps
- 音轨：{'有' if metadata.get('audio_present') else '无'}
- 明显切点：{', '.join(str(item) for item in result.get('scene_cut_seconds') or []) or '未检测到'}
- 字幕路线：{subtitles.get('status', '未检查')}
- 视觉路线：本地抽帧联系表 → {semantics.get('provider', '未选择模型')} / {semantics.get('model', '未知模型') or '未知模型'}
- 视觉状态：{semantics.get('status', '未执行')}（不是原生视频模型调用）

## 已提取字幕
{subtitles.get('text') or '没有可用的内嵌字幕；本次未擅自下载或调用未配置的转写服务。'}

## 模型画面观察（直接可见）
{chr(10).join('- ' + str(item.get('statement') or '') for item in semantics.get('observations', [])) or '- 未获得视觉模型观察。'}

## 模型推断（必须复核）
{chr(10).join('- ' + str(item.get('statement') or '') for item in semantics.get('inferences', [])) or '- 无。'}

## 未知项
{chr(10).join('- ' + str(item) for item in semantics.get('unknowns', [])) or '- 无额外未知项；仍需负责人核对商品、版权和表现数据。'}

## 镜头复核队列
| 镜头 | 时间 | 画面事实 | 镜头/运镜 | 字幕/声音 | 商业作用 |
|---|---:|---|---|---|---|
{rows}

## 必填创意结论
- 爆款证据状态：未提供播放、互动、发布时间、投流属性和账号基线时，只能标记“高潜结构”，不能断言爆款。
- 0-3 秒钩子：
- 痛点/人群：
- 产品动作与证据：
- 节奏与转场：
- 音乐的情绪/节拍作用：
- CTA 与承接页面：
- 评论区购买信号：
- 可复用结构：
- 不能复制的元素：人物、商标、台词、受保护画面、未授权音乐。
- 事实 / 推断 / 未知项：分别填写，禁止混写。
- 原创裂变要求：每个变体至少改变三个非事实创意轴，并写明假设、指标和停止规则。
"""


def analyze_video(
    root: Path,
    video_path: str | Path,
    task_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = task_context if isinstance(task_context, dict) else {}
    video = Path(video_path).expanduser().resolve()
    if not video.exists() or video.suffix.lower() not in VIDEO_EXTENSIONS:
        return {"ok": False, "error": "请选择存在的 MP4/MOV/MKV/WEBM/AVI/M4V 视频。"}
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return {"ok": False, "error": "未找到 FFmpeg。当前可先打开 CapCut，或在工具配置中安装隔离的视频分析运行时。"}
    source_hash = _sha256_file(video)
    digest = source_hash[:12]
    stamp = datetime.now(timezone.utc).astimezone().strftime("%Y%m%d-%H%M%S")
    output_dir = root / "outputs" / "creative_video" / f"{video.stem[:40]}-{digest}-{stamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata = _technical_metadata(ffmpeg, video)
    scenes = _scene_times(ffmpeg, video)
    frames = _capture_frames(ffmpeg, video, output_dir, scenes, float(metadata.get("duration_seconds") or 0))
    sheet = _contact_sheet(frames, output_dir / "contact_sheet.jpg")
    subtitles = _extract_embedded_subtitles(ffmpeg, video, output_dir)
    provider_name = str(context.get("model_provider") or "").strip()
    visual_semantics: dict[str, Any] = {
        "status": "not_requested",
        "provider": provider_name,
        "model": "",
        "observations": [],
        "inferences": [],
        "unknowns": ["画面语义尚未由已验证视觉模型分析。"],
        "draft": "",
        "external_ai_call_count": 0,
        "external_business_action_count": 0,
        "native_video_model_used": False,
        "input_representation": "derived_video_contact_sheet",
    }
    if sheet and bool(context.get("allow_external_vision")) and provider_name:
        from .multimodal_semantic_intake import analyze_image_evidence

        try:
            sheet_ref = sheet.resolve().relative_to(root.resolve()).as_posix()
            visual_semantics = analyze_image_evidence(
                root,
                sheet_ref,
                project_id=str(context.get("project_id") or ""),
                task_id=str(context.get("task_id") or context.get("id") or ""),
                conversation_id=str(context.get("conversation_id") or ""),
                run_id=str(context.get("run_id") or ""),
                provider_name=provider_name,
                allow_external_vision=True,
                business_object_refs=[
                    {
                        "object_type": "local_video_analysis",
                        "object_id": digest,
                        "version_ref": source_hash,
                        "source_ref": str(video),
                    }
                ],
            )
        except (OSError, RuntimeError, ValueError) as exc:
            visual_semantics = {
                **visual_semantics,
                "status": "vision_routing_failed",
                "error": str(exc),
            }
    elif bool(context.get("allow_external_vision")) and not provider_name:
        visual_semantics["status"] = "blocked_missing_task_vision_provider"
        visual_semantics["unknowns"] = ["当前任务没有选择视觉模型。"]
    semantic_path = output_dir / "visual_semantics.json"
    semantic_path.write_text(
        json.dumps(visual_semantics, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    from .skill_agents import run_skill_agent

    content_skill = run_skill_agent(
        root,
        "tk-content-hooks",
        {
            "product_name": str(context.get("product_id") or "").strip(),
            "audience": str(context.get("verified_target_audience") or "").strip(),
            "verified_benefit": str(context.get("verified_benefit") or "").strip(),
            "observations": list(visual_semantics.get("observations") or []),
        },
    )
    content_skill_path = output_dir / "content_skill_result.json"
    content_skill_path.write_text(
        json.dumps(content_skill, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    result = {
        "ok": True,
        "source_file": str(video),
        "source_sha256": source_hash,
        "analyzed_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "tool": str(ffmpeg),
        "metadata": metadata,
        "scene_cut_seconds": scenes,
        "frame_files": [str(path) for path in frames],
        "contact_sheet": str(sheet or ""),
        "subtitles": subtitles,
        "visual_semantics": visual_semantics,
        "semantic_path": str(semantic_path),
        "content_skill": content_skill,
        "content_skill_path": str(content_skill_path),
        "output_dir": str(output_dir),
        "semantic_status": (
            "visual_observations_extracted"
            if visual_semantics.get("status") == "model_observations_extracted"
            else "ready_for_visual_review"
        ),
        "external_business_action_count": 0,
        "native_video_model_used": False,
        "template_id": str(context.get("template_id") or "ugc-pain-solution-15"),
        "generation_route": resolve_generation_route(
            root, str(context.get("generation_route_id") or "")
        ),
    }
    variation_plan = build_creative_variation_plan(
        product_facts={},
        observations={
            "edit_rhythm": f"检测到 {len(scenes)} 个明显切点；画面含义仍待视觉复核。",
            "unknowns": [
                "商品事实", "钩子含义", "证明类型", "CTA", "播放与互动表现",
                *[str(item) for item in visual_semantics.get("unknowns", [])],
            ],
        },
        performance={"source_file": str(video)},
    )
    variation_path = output_dir / "creative_variation_plan.json"
    variation_path.write_text(json.dumps(variation_plan, ensure_ascii=False, indent=2), encoding="utf-8")
    result["creative_variation_plan"] = str(variation_path)
    prompt = build_prompt_pack(
        root,
        template_id=str(context.get("template_id") or "ugc-pain-solution-15"),
        product=(
            "10001 230g 水洗T恤"
            if str(context.get("product_id") or "") == "10001"
            else str(context.get("product_id") or "当前商品")
        ),
        platform=str(context.get("target_platform") or "TikTok Shop"),
        country=str(context.get("country") or "US"),
        observations={"edit_rhythm": f"检测到 {len(scenes)} 个明显切点；先由视觉导演复核关键帧内容，再确定可复用节奏。"},
        task_context=context,
    )
    prompt_path = output_dir / "prompt_pack.md"
    prompt_path.write_text(prompt, encoding="utf-8")
    result["prompt_pack"] = str(prompt_path)
    brief_path = output_dir / "competitor_deconstruction.md"
    brief_path.write_text(_deconstruction_brief(result), encoding="utf-8")
    result["deconstruction_brief"] = str(brief_path)
    (output_dir / "analysis.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
