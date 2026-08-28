"""POD 平台对外 API 的只读 + 写回客户端（stdlib only，松耦合）。

tk智能体作为"分析大脑"，通过 POD 平台的 /api/public/* 接口读取设计师作品、商品、
订单汇总，并把选品结论写回 design.tkSelection。鉴权用 x-api-key（在 POD 管理员后台生成）。

与 POD 平台保持松耦合：这里只发 HTTP，不直接读 POD 的数据库。
对应 POD 端实现：`新建文件夹 (6)/src/publicapi.py`（实际为 publicapi.js）。
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class PodPublicClient:
    def __init__(self, base_url: str, api_key: str, *, timeout: float = 8.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def _request(self, method: str, path: str, *, query: dict[str, Any] | None = None, body: dict[str, Any] | None = None) -> Any:
        url = self.base_url + path
        if query:
            url += "?" + urllib.parse.urlencode({k: v for k, v in query.items() if v is not None})
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"x-api-key": self.api_key, "Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:  # surface API error bodies
            detail = exc.read().decode("utf-8", "replace")
            raise PodApiError(f"POD API {method} {path} -> HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise PodApiError(f"POD API {method} {path} 连接失败：{exc.reason}") from exc
        return json.loads(raw) if raw else {}

    # ---- 只读 ----
    def designs(self, *, limit: int = 50, designer_id: int | None = None) -> list[dict[str, Any]]:
        out = self._request("GET", "/api/public/designs", query={"limit": limit, "designerId": designer_id})
        return list(out.get("designs", []))

    def products(self) -> list[dict[str, Any]]:
        out = self._request("GET", "/api/public/products")
        return list(out.get("products", []))

    def orders_summary(self) -> dict[str, Any]:
        return self._request("GET", "/api/public/orders-summary")

    # ---- 写回选品结论 ----
    def post_selection_verdict(
        self,
        design_id: int,
        verdict: str,
        *,
        score: float | None = None,
        note: str = "",
        channels: list[str] | None = None,
    ) -> dict[str, Any]:
        body = {
            "designId": design_id,
            "verdict": verdict,
            "score": score,
            "note": note,
            "channels": channels or [],
        }
        return self._request("POST", "/api/public/selection-verdict", body=body)

    # ---- 写入一条「运营建议」到平台 AI 运营队列（仅平台托管作品；需 Key 带 ops 权限）----
    # 注意：这只是建议，平台侧需人工审批后才生效；AI 不直接改价/上架/动钱。
    def post_ops_recommendation(
        self,
        design_id: int,
        rec_type: str,
        suggestion: str,
        *,
        rationale: str = "",
        proposed_value: Any = None,
        confidence: float | None = None,
    ) -> dict[str, Any]:
        body = {
            "designId": design_id,
            "type": rec_type,  # pricing/content/restock/selection/ad/listing/other
            "suggestion": suggestion,
            "rationale": rationale,
            "proposedValue": proposed_value,
            "confidence": confidence,
        }
        return self._request("POST", "/api/public/ops-recommendation", body=body)


class PodApiError(RuntimeError):
    """POD 对外 API 调用失败（连接错误或非 2xx）。"""


def client_from_config(config: dict[str, Any]) -> PodPublicClient:
    """从配置字典构造客户端。期望键：base_url / api_key。"""
    base_url = str(config.get("base_url") or "http://127.0.0.1:3100")
    api_key = str(config.get("api_key") or "")
    if not api_key:
        raise PodApiError("缺少 POD 对外 API Key（在 POD 管理员后台生成后填入配置）")
    return PodPublicClient(base_url, api_key)
