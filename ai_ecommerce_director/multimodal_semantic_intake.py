from __future__ import annotations

import base64
import hashlib
import json
import re
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .llm import LLMConfig, classify_provider_error, load_ai_configs
from .task_execution_runtime import append_business_event


IMAGE_SUFFIXES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
MAX_OBSERVATIONS = 12
MAX_INFERENCES = 8
MAX_STATEMENT_CHARS = 1200
SECRET_PATTERN = re.compile(
    r"(?i)(?:api[_-]?key|access[_-]?token|authorization|bearer|password)\s*[:=]\s*\S+"
)


def _safe_text(value: Any, limit: int = MAX_STATEMENT_CHARS) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()[:limit]
    if SECRET_PATTERN.search(text):
        raise ValueError("多模态分析结果疑似包含密钥或令牌，已阻断保存。")
    return text


def _inside_root(root: Path, relative: str) -> Path:
    root_resolved = root.resolve()
    target = (root / relative).resolve()
    try:
        target.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError("附件路径超出当前工作区。") from exc
    if not target.is_file():
        raise ValueError(f"附件不存在：{relative}")
    return target


def _load_manifest(root: Path, manifest_ref: str) -> tuple[dict[str, Any], Path]:
    path = _inside_root(root, manifest_ref)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("files"), list):
        raise ValueError("附件清单格式无效。")
    return payload, path


def _pdf_semantics(path: Path) -> dict[str, Any]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ValueError("当前运行环境缺少 pypdf，无法读取 PDF。") from exc

    reader = PdfReader(str(path), strict=False)
    pages: list[dict[str, Any]] = []
    key_values: dict[str, str] = {}
    for page_number, page in enumerate(reader.pages, start=1):
        text = str(page.extract_text() or "").replace("\x00", "").strip()
        safe_page_text = _safe_text(text, 5000)
        for raw_line in text.splitlines():
            if ":" not in raw_line:
                continue
            key, value = raw_line.split(":", 1)
            key = _safe_text(key, 80)
            value = _safe_text(value, 300)
            if key and value and key not in key_values:
                key_values[key] = value
        pages.append(
            {
                "page": page_number,
                "text": safe_page_text,
                "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "character_count": len(text),
            }
        )
    return {
        "method": "pypdf_text_layer",
        "page_count": len(reader.pages),
        "pages": pages,
        "candidate_key_values": key_values,
        "semantic_status": "text_layer_extracted" if any(item["text"] for item in pages) else "no_text_layer",
    }


def _image_metadata(path: Path) -> dict[str, Any]:
    try:
        from PIL import Image
    except ImportError as exc:
        raise ValueError("当前运行环境缺少 Pillow，无法读取图片。") from exc
    with Image.open(path) as image:
        image.verify()
    with Image.open(path) as image:
        return {
            "format": str(image.format or "").upper(),
            "width": int(image.width),
            "height": int(image.height),
            "mode": str(image.mode or ""),
        }


def _extract_json_object(text: str) -> dict[str, Any]:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*", "", candidate, flags=re.I)
        candidate = re.sub(r"\s*```$", "", candidate)
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("视觉模型没有返回可解析的 JSON 对象。")
        payload = json.loads(candidate[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("视觉模型返回值必须是 JSON 对象。")
    return payload


def _normalized_items(value: Any, limit: int) -> list[dict[str, str]]:
    items = value if isinstance(value, list) else []
    normalized: list[dict[str, str]] = []
    for item in items[:limit]:
        if isinstance(item, str):
            statement, region, confidence = item, "", "unknown"
        elif isinstance(item, dict):
            statement = item.get("statement") or item.get("text")
            region = item.get("region")
            confidence = item.get("confidence")
        else:
            continue
        safe_statement = _safe_text(statement)
        if not safe_statement:
            continue
        normalized.append(
            {
                "statement": safe_statement,
                "region": _safe_text(region, 160),
                "confidence": _safe_text(confidence, 40) or "unknown",
            }
        )
    return normalized


def _vision_prompt() -> str:
    return (
        "Inspect this commerce-related image. Return JSON only with keys observations, inferences, unknowns, draft. "
        "observations is a list of objects with statement, region and confidence and may contain only directly visible content. "
        "inferences is a separate list using the same object shape and must be conservative. "
        "unknowns is a list of short strings. draft is an optional short next-step draft, never an executed action. "
        "Do not claim that a listing, order, advertisement, message, refund or upload was executed. "
        "Do not output secrets or guess hidden store/account identity."
    )


def _vision_request(config: LLMConfig, path: Path) -> dict[str, Any]:
    if config.api_format != "openai" or not config.ready:
        raise ValueError("所选视觉模型尚未通过 OpenAI-compatible 配置就绪检查。")
    mime = IMAGE_SUFFIXES.get(path.suffix.lower())
    if not mime:
        raise ValueError("视觉模型仅接收 JPG、PNG 或 WebP。")
    data_uri = f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"
    endpoint = str(config.base_url or "").rstrip("/") + "/chat/completions"
    payload = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": "You are a provenance-first visual evidence extractor."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _vision_prompt()},
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ],
            },
        ],
        "temperature": 0.1,
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        **config.headers,
        **({"Authorization": f"Bearer {config.api_key}"} if config.api_key else {}),
    }
    started = time.perf_counter()
    request = urllib.request.Request(endpoint, data=body, method="POST", headers=headers)
    with urllib.request.urlopen(request, timeout=max(1, int(config.timeout_seconds))) as response:
        response_payload = json.loads(response.read().decode("utf-8"))
    content = response_payload["choices"][0]["message"]["content"]
    parsed = _extract_json_object(str(content))
    observations = _normalized_items(parsed.get("observations"), MAX_OBSERVATIONS)
    inferences = _normalized_items(parsed.get("inferences"), MAX_INFERENCES)
    unknowns = [_safe_text(item, 240) for item in (parsed.get("unknowns") or [])[:12] if _safe_text(item, 240)]
    return {
        "provider": config.name,
        "model": str(config.model or ""),
        "latency_ms": round((time.perf_counter() - started) * 1000),
        "observations": observations,
        "inferences": inferences,
        "unknowns": unknowns,
        "draft": _safe_text(parsed.get("draft"), 600),
        "raw_response_sha256": hashlib.sha256(str(content).encode("utf-8")).hexdigest(),
        "semantic_status": "model_observations_extracted",
    }


def _provider(root: Path, provider_name: str) -> LLMConfig:
    configs, _ = load_ai_configs(root)
    match = next((item for item in configs if item.name == provider_name), None)
    if match is None:
        raise ValueError("未找到指定视觉模型配置。")
    if not match.ready:
        raise ValueError("指定视觉模型缺少可用配置或凭据。")
    return match


def analyze_image_evidence(
    root: Path,
    image_ref: str,
    *,
    project_id: str,
    task_id: str,
    conversation_id: str = "",
    run_id: str = "",
    provider_name: str = "zhipu-glm-vision",
    allow_external_vision: bool = False,
    business_object_refs: list[dict[str, str]] | None = None,
    record_events: bool = True,
) -> dict[str, Any]:
    """Analyze one workspace-owned image without pretending it is native video input.

    This entry point is used after local video preprocessing creates a contact
    sheet.  The model receives only that derived JPG/PNG evidence.  Directly
    visible observations, conservative inferences, unknowns and an unexecuted
    draft remain separate in both the result and the business-event log.
    """

    path = _inside_root(root, image_ref)
    if path.suffix.lower() not in IMAGE_SUFFIXES:
        raise ValueError("视觉语义路由仅接收工作区内的 JPG、PNG 或 WebP。")
    metadata = _image_metadata(path)
    source_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    refs = [
        {
            "object_type": _safe_text(item.get("object_type"), 80),
            "object_id": _safe_text(item.get("object_id"), 160),
            "version_ref": _safe_text(item.get("version_ref"), 300),
            "source_ref": _safe_text(item.get("source_ref"), 300),
        }
        for item in (business_object_refs or [])
        if isinstance(item, dict) and item.get("object_type") and item.get("object_id")
    ]
    result: dict[str, Any] = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "status": "blocked_until_explicit_external_vision_approval",
        "source_ref": image_ref,
        "source_sha256": source_sha256,
        "image": metadata,
        "provider": provider_name,
        "model": "",
        "observations": [],
        "inferences": [],
        "unknowns": ["未获准把本地派生画面发送给已配置视觉模型。"],
        "draft": "",
        "business_object_refs": refs,
        "business_event_ids": [],
        "external_ai_call_count": 0,
        "external_business_action_count": 0,
        "approval_action_count": 0,
        "native_video_model_used": False,
        "input_representation": "derived_video_contact_sheet",
    }
    if not allow_external_vision:
        return result

    try:
        config = _provider(root, provider_name)
        semantic = _vision_request(config, path)
    except Exception as exc:  # noqa: BLE001 - preserve a safe provider diagnostic.
        return {
            **result,
            **classify_provider_error(exc, provider=provider_name, model=""),
            "status": "vision_provider_failed",
        }

    result.update(
        {
            "status": "model_observations_extracted",
            "provider": semantic["provider"],
            "model": semantic["model"],
            "latency_ms": semantic["latency_ms"],
            "observations": semantic["observations"],
            "inferences": semantic["inferences"],
            "unknowns": semantic["unknowns"],
            "draft": semantic["draft"],
            "raw_response_sha256": semantic["raw_response_sha256"],
            "external_ai_call_count": 1,
        }
    )
    if not record_events:
        return result

    common = {
        "workspace_id": "local-workspace",
        "project_id": project_id,
        "task_id": task_id,
        "conversation_id": conversation_id or task_id,
        "run_id": run_id,
        "source_refs": [image_ref],
        "business_object_refs": refs,
        "actor": "multimodal-semantic-intake",
    }
    items_by_kind: tuple[tuple[str, list[dict[str, str]]], ...] = (
        ("observation", result["observations"]),
        ("inference", result["inferences"]),
        (
            "draft",
            [
                {
                    "statement": result["draft"],
                    "region": "model_draft",
                    "confidence": "draft_not_executed",
                }
            ]
            if result["draft"]
            else [],
        ),
    )
    for kind, items in items_by_kind:
        for item in items:
            event = append_business_event(
                root,
                {
                    **common,
                    "event_type": "multimodal_intake_recorded",
                    "kind": kind,
                    "statement": item["statement"],
                    "confidence": item.get("confidence") or "unknown",
                    "payload": {"region": item.get("region") or ""},
                },
            )
            result["business_event_ids"].append(event["event_id"])
    return result


def analyze_attachment_manifest(
    root: Path,
    manifest_ref: str,
    *,
    project_id: str,
    task_id: str,
    conversation_id: str = "",
    run_id: str = "",
    provider_name: str = "zhipu-glm-vision",
    provider_config: LLMConfig | None = None,
    allow_external_vision: bool = False,
    record_events: bool = True,
) -> dict[str, Any]:
    """Read PDF text layers and, only when explicitly allowed, send images to a scoped vision provider.

    The result keeps file facts, visible observations, model inferences and drafts separate. It never
    performs a store, message, advertising or publishing action.
    """

    manifest, manifest_path = _load_manifest(root, manifest_ref)
    manifest_project_id = str(manifest.get("project_id") or "").strip().lower()
    clean_project_id = str(project_id or "").strip().lower()
    if clean_project_id and manifest_project_id != clean_project_id:
        raise ValueError("附件清单与当前项目不一致，已阻断语义分析。")
    expected_project_root = (root / "data" / "product_intake" / clean_project_id).resolve()
    if clean_project_id:
        try:
            manifest_path.resolve().relative_to(expected_project_root)
        except ValueError as exc:
            raise ValueError("附件清单不在当前项目的数据目录内。") from exc
    selected_provider_name = provider_config.name if provider_config else provider_name
    selected_model = str(provider_config.model or "") if provider_config else "configured_at_runtime"
    analysis_fingerprint = hashlib.sha256(
        json.dumps(
            {
                "schema_version": 1,
                "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                "file_sha256s": [
                    str(item.get("sha256") or "")
                    for item in manifest.get("files", [])
                    if isinstance(item, dict)
                ],
                "provider": selected_provider_name,
                "model": selected_model,
                "allow_external_vision": bool(allow_external_vision),
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    sidecar_path = manifest_path.parent / "semantic-analysis.json"
    if record_events and sidecar_path.is_file():
        try:
            cached = json.loads(sidecar_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            cached = {}
        if (
            isinstance(cached, dict)
            and cached.get("analysis_fingerprint") == analysis_fingerprint
            and cached.get("status") == "semantic_routing_complete"
        ):
            return {**cached, "cache_hit": True}
    business_object_refs = [
        {
            "object_type": "product_intake_batch",
            "object_id": manifest_path.parent.name,
            "version_ref": str(manifest.get("catalog_path") or ""),
            "source_ref": manifest_ref,
        }
    ]
    files: list[dict[str, Any]] = []
    all_observations: list[dict[str, Any]] = []
    all_inferences: list[dict[str, Any]] = []
    all_drafts: list[dict[str, Any]] = []
    event_ids: list[str] = []

    for source in manifest.get("files", []):
        if not isinstance(source, dict) or str(source.get("kind") or "") != "media":
            continue
        relative = str(source.get("path") or "")
        path = _inside_root(root, relative)
        raw = path.read_bytes()
        actual_sha = hashlib.sha256(raw).hexdigest()
        expected_sha = str(source.get("sha256") or "")
        if expected_sha and actual_sha != expected_sha:
            raise ValueError(f"附件哈希不一致：{relative}")
        suffix = path.suffix.lower()
        record: dict[str, Any] = {
            "source_ref": relative,
            "name": str(source.get("name") or path.name),
            "sha256": actual_sha,
            "size_bytes": len(raw),
            "facts": [],
            "observations": [],
            "inferences": [],
            "drafts": [],
        }
        record["facts"].append({"statement": f"附件 SHA256 为 {actual_sha}，大小 {len(raw)} 字节。", "confidence": "verified"})
        if suffix == ".pdf":
            semantic = _pdf_semantics(path)
            record["pdf"] = semantic
            record["facts"].append({"statement": f"PDF 共 {semantic['page_count']} 页。", "confidence": "verified"})
            for page in semantic["pages"]:
                if page["text"]:
                    record["observations"].append(
                        {
                            "statement": page["text"],
                            "region": f"page:{page['page']}",
                            "confidence": "text_layer",
                        }
                    )
            for key, value in semantic["candidate_key_values"].items():
                record["inferences"].append(
                    {
                        "statement": f"候选字段 {key}: {value}",
                        "region": "pdf_text_layer",
                        "confidence": "candidate_requires_verification",
                    }
                )
        elif suffix in IMAGE_SUFFIXES:
            metadata = _image_metadata(path)
            record["image"] = metadata
            record["facts"].append(
                {
                    "statement": f"图片格式 {metadata['format']}，尺寸 {metadata['width']}x{metadata['height']}，模式 {metadata['mode']}。",
                    "confidence": "verified",
                }
            )
            if allow_external_vision:
                try:
                    config = provider_config or _provider(root, provider_name)
                    semantic = _vision_request(config, path)
                except Exception as exc:  # noqa: BLE001 - return a safe provider diagnostic.
                    failed_provider = provider_config.name if provider_config else provider_name
                    failed_model = str(provider_config.model or "") if provider_config else ""
                    record["vision"] = {
                        **classify_provider_error(exc, provider=failed_provider, model=failed_model),
                        "semantic_status": "vision_provider_failed",
                    }
                else:
                    record["vision"] = semantic
                    record["observations"].extend(semantic["observations"])
                    record["inferences"].extend(semantic["inferences"])
                    if semantic["draft"]:
                        record["drafts"].append(
                            {
                                "statement": semantic["draft"],
                                "region": "model_draft",
                                "confidence": "draft_not_executed",
                            }
                        )
            else:
                record["vision"] = {
                    "semantic_status": "blocked_until_explicit_external_vision_approval",
                    "provider": provider_name,
                }
        else:
            record["semantic_status"] = "unsupported_media_for_semantic_analysis"

        all_observations.extend({**item, "source_ref": relative} for item in record["observations"])
        all_inferences.extend({**item, "source_ref": relative} for item in record["inferences"])
        all_drafts.extend({**item, "source_ref": relative} for item in record["drafts"])
        files.append(record)

        if record_events:
            common = {
                "workspace_id": "local-workspace",
                "project_id": project_id,
                "task_id": task_id,
                "conversation_id": conversation_id or task_id,
                "run_id": run_id,
                "source_refs": [manifest_ref, relative],
                "business_object_refs": business_object_refs,
                "actor": "multimodal-semantic-intake",
            }
            fact = append_business_event(
                root,
                {
                    **common,
                    "event_type": "multimodal_intake_recorded",
                    "kind": "fact",
                    "statement": record["facts"][0]["statement"],
                    "confidence": "verified",
                    "payload": {"sha256": actual_sha, "size_bytes": len(raw)},
                },
            )
            event_ids.append(fact["event_id"])
            for kind, items in (("observation", record["observations"]), ("inference", record["inferences"]), ("draft", record["drafts"])):
                for item in items:
                    event = append_business_event(
                        root,
                        {
                            **common,
                            "event_type": "multimodal_intake_recorded",
                            "kind": kind,
                            "statement": item["statement"],
                            "confidence": item.get("confidence") or "unknown",
                            "payload": {"region": item.get("region") or ""},
                        },
                    )
                    event_ids.append(event["event_id"])

    complete = bool(files) and all(
        item.get("pdf", {}).get("semantic_status") == "text_layer_extracted"
        or item.get("vision", {}).get("semantic_status") == "model_observations_extracted"
        for item in files
        if Path(str(item.get("source_ref") or "")).suffix.lower() in ({".pdf"} | set(IMAGE_SUFFIXES))
    )
    result = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "analysis_fingerprint": analysis_fingerprint,
        "cache_hit": False,
        "status": "semantic_routing_complete" if complete else "semantic_routing_partial",
        "manifest_ref": manifest_ref,
        "project_id": project_id,
        "task_id": task_id,
        "conversation_id": conversation_id or task_id,
        "run_id": run_id,
        "business_object_refs": business_object_refs,
        "files": files,
        "observations": all_observations,
        "inferences": all_inferences,
        "drafts": all_drafts,
        "business_event_ids": event_ids,
        "external_ai_call_count": sum(1 for item in files if item.get("vision", {}).get("semantic_status") == "model_observations_extracted"),
        "external_business_action_count": 0,
        "approval_action_count": 0,
    }
    if record_events:
        sidecar_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return result
