from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import posixpath
import re
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse
from xml.etree import ElementTree


MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_ROWS = 10_000
MAX_COLUMNS = 256
MAX_CELL_CHARACTERS = 20_000
_ALLOWED_EXTENSIONS = {"csv", "json", "xlsx"}
_CREDENTIAL_COLUMN_NAMES = {
    "password",
    "passwd",
    "pwd",
    "token",
    "secret",
    "api_key",
    "apikey",
    "cookie",
    "cookies",
    "authorization",
    "session",
    "session_id",
    "mfa",
    "otp",
    "verification_code",
    "private_key",
    "access_token",
    "refresh_token",
    "client_secret",
}


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"采集工具注册表无法读取：{path}") from exc
    if not isinstance(value, dict):
        raise ValueError("采集工具注册表格式无效。")
    return value


def load_data_acquisition_registry(root: Path) -> dict[str, Any]:
    registry = _load_json(root / "config" / "data_acquisition_connectors.json")
    providers = registry.get("providers")
    if not isinstance(providers, list) or not providers:
        raise ValueError("采集工具注册表中没有可用提供方。")
    seen: set[str] = set()
    for provider in providers:
        if not isinstance(provider, dict):
            raise ValueError("采集工具提供方格式无效。")
        provider_id = str(provider.get("id") or "").strip()
        if not provider_id or provider_id in seen:
            raise ValueError("采集工具提供方 ID 缺失或重复。")
        seen.add(provider_id)
    return registry


def _receipt_rows(root: Path, limit: int = 10) -> list[dict[str, Any]]:
    receipt_dir = root / "outputs" / "data_acquisition" / "receipts"
    if not receipt_dir.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(receipt_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(value, dict):
            rows.append(value)
        if len(rows) >= limit:
            break
    return rows


def data_acquisition_snapshot(root: Path) -> dict[str, Any]:
    registry = load_data_acquisition_registry(root)
    providers = [dict(item) for item in registry.get("providers", []) if isinstance(item, dict)]
    receipts = _receipt_rows(root)
    return {
        "ok": True,
        "schema_version": int(registry.get("schema_version") or 1),
        "updated_at": str(registry.get("updated_at") or ""),
        "truth_contract": registry.get("truth_contract") or {},
        "provider_count": len(providers),
        "connected_count": sum(bool(item.get("connected")) for item in providers),
        "local_import_available_count": sum(
            str(item.get("status") or "") == "local_file_import_available"
            for item in providers
        ),
        "providers": providers,
        "recent_imports": receipts,
        "market_observation_import_count": sum(
            item.get("source_layer") == "market_observation" for item in receipts
        ),
        "owned_operating_candidate_import_count": sum(
            item.get("source_layer") == "owned_operating_truth" for item in receipts
        ),
        "external_actions": [],
    }


def _normalize_header(value: Any, index: int) -> str:
    header = str(value or "").strip().replace("\ufeff", "")
    return header or f"column_{index + 1}"


def _deduplicate_headers(values: list[Any]) -> list[str]:
    headers: list[str] = []
    counts: dict[str, int] = {}
    for index, value in enumerate(values[:MAX_COLUMNS]):
        base = _normalize_header(value, index)
        normalized_key = base.casefold()
        counts[normalized_key] = counts.get(normalized_key, 0) + 1
        suffix = counts[normalized_key]
        headers.append(base if suffix == 1 else f"{base}_{suffix}")
    if len(values) > MAX_COLUMNS:
        raise ValueError(f"字段数超过上限 {MAX_COLUMNS}。")
    return headers


def _credential_header(header: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "_", header.casefold()).strip("_")
    return normalized in _CREDENTIAL_COLUMN_NAMES


def _validate_headers(headers: list[str]) -> None:
    blocked = [header for header in headers if _credential_header(header)]
    if blocked:
        raise ValueError(
            "导入文件包含凭据类字段，已阻止：" + "、".join(blocked)
        )


def _cell_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    elif isinstance(value, (str, int, float, bool)):
        text = value if not isinstance(value, str) else value.strip()
    else:
        text = str(value)
    if isinstance(text, str) and len(text) > MAX_CELL_CHARACTERS:
        return text[:MAX_CELL_CHARACTERS]
    return text


def _rows_from_matrix(matrix: list[list[Any]]) -> tuple[list[str], list[dict[str, Any]]]:
    if not matrix:
        raise ValueError("文件中没有可导入的数据。")
    headers = _deduplicate_headers(matrix[0])
    _validate_headers(headers)
    records: list[dict[str, Any]] = []
    for raw_row in matrix[1:]:
        if len(records) >= MAX_ROWS:
            raise ValueError(f"数据行数超过上限 {MAX_ROWS}。")
        values = list(raw_row[: len(headers)])
        if not any(str(value or "").strip() for value in values):
            continue
        values.extend([""] * (len(headers) - len(values)))
        records.append({header: _cell_value(values[index]) for index, header in enumerate(headers)})
    if not records:
        raise ValueError("文件只有表头，没有可导入的数据行。")
    return headers, records


def _parse_csv(data: bytes) -> tuple[list[str], list[dict[str, Any]]]:
    text = ""
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if not text:
        raise ValueError("CSV 文件编码无法识别，请导出 UTF-8 CSV。")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",\t;")
    except csv.Error:
        dialect = csv.excel
    matrix = [list(row) for row in csv.reader(io.StringIO(text), dialect)]
    return _rows_from_matrix(matrix)


def _parse_json(data: bytes) -> tuple[list[str], list[dict[str, Any]]]:
    try:
        value = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("JSON 文件无法解析。") from exc
    if isinstance(value, dict):
        for key in ("records", "items", "data"):
            candidate = value.get(key)
            if isinstance(candidate, list):
                value = candidate
                break
    if not isinstance(value, list) or not value:
        raise ValueError("JSON 必须是对象数组，或包含 records/items/data 数组。")
    if len(value) > MAX_ROWS:
        raise ValueError(f"数据行数超过上限 {MAX_ROWS}。")
    if not all(isinstance(item, dict) for item in value):
        raise ValueError("JSON 数组中的每一项都必须是对象。")
    headers: list[str] = []
    seen: set[str] = set()
    for item in value:
        for key in item:
            header = str(key).strip()
            if header and header not in seen:
                seen.add(header)
                headers.append(header)
                if len(headers) > MAX_COLUMNS:
                    raise ValueError(f"字段数超过上限 {MAX_COLUMNS}。")
    headers = _deduplicate_headers(headers)
    _validate_headers(headers)
    records = [
        {header: _cell_value(item.get(header)) for header in headers}
        for item in value
    ]
    return headers, records


def _xlsx_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return ["".join(node.itertext()) for node in root]


def _xlsx_first_sheet_path(archive: zipfile.ZipFile) -> str:
    try:
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        relationships = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        relationship_map = {
            str(item.attrib.get("Id") or ""): str(item.attrib.get("Target") or "")
            for item in relationships
        }
        sheet = next(node for node in workbook.iter() if node.tag.endswith("}sheet"))
        relationship_id = next(
            (value for key, value in sheet.attrib.items() if key.endswith("}id")),
            "",
        )
        target = relationship_map.get(relationship_id, "")
        if target:
            if target.startswith("/"):
                return target.lstrip("/")
            return posixpath.normpath(str(PurePosixPath("xl") / target))
    except (KeyError, StopIteration, ElementTree.ParseError):
        pass
    candidates = sorted(
        name for name in archive.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name)
    )
    if not candidates:
        raise ValueError("XLSX 中没有可读取的工作表。")
    return candidates[0]


def _column_index(reference: str) -> int:
    letters = re.match(r"[A-Za-z]+", reference or "")
    if letters is None:
        return 0
    value = 0
    for character in letters.group(0).upper():
        value = value * 26 + ord(character) - 64
    return max(value - 1, 0)


def _parse_xlsx(data: bytes) -> tuple[list[str], list[dict[str, Any]]]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ValueError("XLSX 文件损坏或不是有效的 Excel 文件。") from exc
    with archive:
        shared_strings = _xlsx_shared_strings(archive)
        sheet_path = _xlsx_first_sheet_path(archive)
        try:
            sheet = ElementTree.fromstring(archive.read(sheet_path))
        except (KeyError, ElementTree.ParseError) as exc:
            raise ValueError("XLSX 工作表无法解析。") from exc
        matrix: list[list[Any]] = []
        for row_node in (node for node in sheet.iter() if node.tag.endswith("}row")):
            row: list[Any] = []
            for cell in (node for node in row_node if node.tag.endswith("}c")):
                index = _column_index(str(cell.attrib.get("r") or ""))
                if index >= MAX_COLUMNS:
                    raise ValueError(f"字段数超过上限 {MAX_COLUMNS}。")
                while len(row) <= index:
                    row.append("")
                cell_type = str(cell.attrib.get("t") or "")
                value_node = next((node for node in cell.iter() if node.tag.endswith("}v")), None)
                if cell_type == "inlineStr":
                    value: Any = "".join(
                        node.text or "" for node in cell.iter() if node.tag.endswith("}t")
                    )
                else:
                    raw_value = value_node.text if value_node is not None else ""
                    if cell_type == "s" and str(raw_value).isdigit():
                        shared_index = int(str(raw_value))
                        value = shared_strings[shared_index] if shared_index < len(shared_strings) else ""
                    elif cell_type == "b":
                        value = str(raw_value) == "1"
                    else:
                        value = raw_value
                row[index] = value
            matrix.append(row)
            if len(matrix) > MAX_ROWS + 1:
                raise ValueError(f"数据行数超过上限 {MAX_ROWS}。")
    return _rows_from_matrix(matrix)


def _decode_file(payload: dict[str, Any]) -> tuple[str, str, bytes]:
    filename = Path(str(payload.get("filename") or "")).name
    if not filename:
        raise ValueError("请先选择要导入的文件。")
    extension = Path(filename).suffix.lower().lstrip(".")
    if extension not in _ALLOWED_EXTENSIONS:
        raise ValueError("只支持 CSV、XLSX 和 JSON 文件。")
    encoded = str(payload.get("content_base64") or "").strip()
    if encoded.startswith("data:") and "," in encoded:
        encoded = encoded.split(",", 1)[1]
    try:
        data = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("文件内容不是有效的 Base64 数据。") from exc
    if not data:
        raise ValueError("导入文件为空。")
    if len(data) > MAX_FILE_BYTES:
        raise ValueError(f"文件大小超过上限 {MAX_FILE_BYTES // (1024 * 1024)} MB。")
    return filename, extension, data


def _validate_source_url(value: Any) -> str:
    source_url = str(value or "").strip()
    if not source_url:
        return ""
    parsed = urlparse(source_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("来源网址必须是有效的 HTTP/HTTPS 地址。")
    return source_url[:2048]


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _source_truth_contract(payload: dict[str, Any]) -> dict[str, Any]:
    source_layer = str(payload.get("source_layer") or "unclassified_local_import").strip()
    if source_layer not in {
        "unclassified_local_import",
        "market_observation",
        "owned_operating_truth",
    }:
        raise ValueError("source_layer 必须是 market_observation 或 owned_operating_truth。")
    if source_layer == "market_observation":
        required = ["project_id", "platform", "country_site", "collected_at", "source_url"]
        missing = [field for field in required if not str(payload.get(field) or "").strip()]
        if missing:
            raise ValueError("市场观察缺少精确来源字段：" + ", ".join(missing))
        if str(payload.get("store_binding_id") or "").strip():
            raise ValueError("市场观察不能绑定 store_binding_id，也不能进入自有经营真值。")
        return {
            "source_layer": source_layer,
            "promotion_state": "research_observation_only",
            "canonical_truth": False,
            "truth_boundary": {
                "owned_operating_truth": False,
                "allowed_consumers": ["market_research", "product_selection_research", "competitor_observation"],
                "blocked_consumers": ["finance_actual", "orders_actual", "inventory_actual", "ad_spend_actual", "store_health_actual"],
            },
        }
    if source_layer == "owned_operating_truth":
        required = [
            "project_id", "platform", "country_site", "store_binding_id",
            "account_id", "execution_identity_id",
        ]
        missing = [field for field in required if not str(payload.get(field) or "").strip()]
        if missing:
            raise ValueError("自有经营导出缺少精确账号作用域：" + ", ".join(missing))
        attested = payload.get("owner_attested_source") is True or str(
            payload.get("owner_attested_source") or ""
        ).strip().casefold() in {"1", "true", "yes"}
        if not attested:
            raise ValueError("自有经营导出必须由负责人确认来源；未确认时不能进入候选经营数据层。")
        return {
            "source_layer": source_layer,
            "promotion_state": "owned_operating_candidate_pending_validation",
            "canonical_truth": False,
            "truth_boundary": {
                "owned_operating_truth": False,
                "allowed_consumers": ["owned_operating_candidate_validation"],
                "blocked_consumers": ["finance_actual", "orders_actual", "inventory_actual", "ad_spend_actual"],
            },
        }
    return {
        "source_layer": source_layer,
        "promotion_state": "untrusted_imported_evidence",
        "canonical_truth": False,
        "truth_boundary": {
            "owned_operating_truth": False,
            "allowed_consumers": ["manual_review"],
            "blocked_consumers": ["all_canonical_operating_metrics"],
        },
    }


def import_data_acquisition_file(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    registry = load_data_acquisition_registry(root)
    providers = {
        str(item.get("id") or ""): item
        for item in registry.get("providers", [])
        if isinstance(item, dict)
    }
    provider_id = str(payload.get("provider_id") or "").strip()
    provider = providers.get(provider_id)
    if provider is None:
        raise ValueError("请选择已登记的采集工具。")
    truth_contract = _source_truth_contract(payload)
    filename, extension, data = _decode_file(payload)
    supported = {str(value).lower() for value in provider.get("supported_file_formats", [])}
    if extension not in supported:
        raise ValueError(f"{provider.get('name') or provider_id} 当前不接收 {extension.upper()} 导出文件。")
    if extension == "csv":
        columns, rows = _parse_csv(data)
    elif extension == "json":
        columns, rows = _parse_json(data)
    else:
        columns, rows = _parse_xlsx(data)

    captured_at = _now()
    digest = hashlib.sha256(data).hexdigest().upper()
    import_id = f"DAI-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8].upper()}"
    source_url = _validate_source_url(payload.get("source_url"))
    project_id = str(payload.get("project_id") or "").strip()[:160]
    store_binding_id = str(payload.get("store_binding_id") or "").strip()[:160]
    dataset_type = str(payload.get("dataset_type") or "general_public_data").strip()[:120]
    collected_at = str(payload.get("collected_at") or "").strip()[:80]
    normalized_record = {
        "schema_version": 1,
        "import_id": import_id,
        "status": "imported_local_evidence",
        "promotion_state": truth_contract["promotion_state"],
        "source_layer": truth_contract["source_layer"],
        "canonical_truth": truth_contract["canonical_truth"],
        "truth_boundary": truth_contract["truth_boundary"],
        "provider": {
            "id": provider_id,
            "name": str(provider.get("name") or provider_id),
            "connected": False,
        },
        "file": {
            "filename": filename,
            "extension": extension,
            "size_bytes": len(data),
            "sha256": digest,
        },
        "provenance": {
            "source_url": source_url,
            "dataset_type": dataset_type,
            "collected_at": collected_at,
            "imported_at": captured_at,
            "method": "owner_supplied_local_export",
        },
        "scope": {
            "project_id": project_id,
            "store_binding_id": store_binding_id,
            "platform": str(payload.get("platform") or "").strip()[:120],
            "country_site": str(payload.get("country_site") or "").strip().upper()[:40],
            "account_id": str(payload.get("account_id") or "").strip()[:160],
            "execution_identity_id": str(payload.get("execution_identity_id") or "").strip()[:160],
        },
        "columns": columns,
        "row_count": len(rows),
        "rows": rows,
        "external_actions": [],
    }
    import_path = root / "outputs" / "data_acquisition" / "imports" / f"{import_id}.json"
    receipt_path = root / "outputs" / "data_acquisition" / "receipts" / f"{import_id}.json"
    receipt = {
        "schema_version": 1,
        "import_id": import_id,
        "status": "imported_local_evidence",
        "provider_id": provider_id,
        "provider_name": str(provider.get("name") or provider_id),
        "filename": filename,
        "sha256": digest,
        "row_count": len(rows),
        "column_count": len(columns),
        "imported_at": captured_at,
        "promotion_state": truth_contract["promotion_state"],
        "source_layer": truth_contract["source_layer"],
        "canonical_truth": truth_contract["canonical_truth"],
        "connected": False,
        "external_actions": [],
        "record_path": str(import_path),
    }
    _atomic_write_json(import_path, normalized_record)
    _atomic_write_json(receipt_path, receipt)
    return {**receipt, "receipt_path": str(receipt_path)}
