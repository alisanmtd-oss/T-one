from __future__ import annotations

import json
from pathlib import Path
from typing import Any


POLICY_PATH = Path("config") / "expert_learning_source_policy.json"


def load_expert_learning_policy(root: Path) -> dict[str, Any]:
    policy = json.loads((root / POLICY_PATH).read_text(encoding="utf-8-sig"))
    if not isinstance(policy, dict):
        raise ValueError("专家学习来源策略必须是对象。")
    validate_expert_learning_policy(policy)
    return policy


def validate_expert_learning_policy(policy: dict[str, Any]) -> None:
    allocation = policy.get("work_allocation") or {}
    if float(allocation.get("mainline_completion_minimum_ratio") or 0) < 0.7:
        raise ValueError("主线任务占比不能低于 70%。")
    if float(allocation.get("knowledge_package_discovery_audit_reuse_minimum_ratio_in_learning_round") or 0) < 0.5:
        raise ValueError("增量学习的知识包发现、审计、复用占比不能低于 50%。")
    stages = policy.get("stage_contract") or {}
    if (stages.get("knowledge_pack") or {}).get("may_claim_live_operation") is not False:
        raise ValueError("知识包不能冒充真实执行智能体。")
    required = set((stages.get("operational_agent") or {}).get("required") or [])
    if not {
        "store_scoped_execution_identity",
        "approval_policy",
        "effect_verification",
        "audit_receipt",
    }.issubset(required):
        raise ValueError("真实执行智能体缺少身份、审批、效果验证或回执边界。")
    shared = policy.get("shared_cross_cutting_capabilities") or {}
    if shared.get("single_instance_only") is not True:
        raise ValueError("跨岗位通用能力必须复用唯一实例。")
    video = policy.get("video_learning") or {}
    if video.get("download_connector_status") != "blocked_not_implemented":
        raise ValueError("未接入合规下载连接器前必须保持阻断。")
    if "bulk_or_full_network_scrape" not in set(video.get("stop_rules") or []):
        raise ValueError("视频学习必须阻断全网批量抓取。")
