from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any


MATRIX_PATH = Path("config") / "u25_framework_adoption_matrix.json"
EXPECTED_REPOSITORIES = {
    "KunAgent/Kun",
    "openai/codex",
    "multica-ai/multica",
    "farion1231/cc-switch",
}
DECISION_DIMENSIONS = {"adopt", "adapt", "retain", "remove"}
IDENTITY_FIELDS = (
    "project_id",
    "platform",
    "site",
    "store_id",
    "store_mode",
    "browser_profile_id",
    "network_profile_id",
)


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_framework_adoption_matrix(root: Path) -> dict[str, Any]:
    payload = json.loads((root / MATRIX_PATH).read_text(encoding="utf-8"))
    if int(payload.get("schema_version") or 0) != 1:
        raise ValueError("U25 framework matrix schema is not supported.")
    if str(payload.get("configuration_authority") or "") != "t_one_only":
        raise ValueError("U25 framework matrix must keep T One as configuration authority.")
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("U25 framework matrix candidates are missing.")
    repos = {str(item.get("repo") or "") for item in candidates if isinstance(item, dict)}
    if repos != EXPECTED_REPOSITORIES:
        raise ValueError("U25 framework matrix must cover exactly four reviewed candidates.")
    for item in candidates:
        if not isinstance(item, dict):
            raise ValueError("U25 framework candidate must be an object.")
        if not str(item.get("pinned_release") or ""):
            raise ValueError("U25 framework candidate release is not pinned.")
        commit = str(item.get("pinned_commit") or "")
        if len(commit) != 40 or any(char not in "0123456789abcdef" for char in commit):
            raise ValueError("U25 framework candidate commit is not a full SHA-1.")
        matrix = item.get("matrix")
        if not isinstance(matrix, dict) or set(matrix) != DECISION_DIMENSIONS:
            raise ValueError("U25 framework candidate decision dimensions are incomplete.")
        if item.get("installed_by_u25") is not False:
            raise ValueError("U25 may not mark any third-party candidate installed.")
        if int(item.get("external_calls_by_u25") or 0) != 0:
            raise ValueError("U25 may not call a third-party framework runtime.")
    return payload


def evaluate_framework_surface(
    root: Path, repo: str, surface: str
) -> dict[str, Any]:
    matrix = load_framework_adoption_matrix(root)
    candidate = next(
        (item for item in matrix["candidates"] if item["repo"] == repo), None
    )
    if candidate is None:
        return {
            "allowed": False,
            "code": "unknown_repository_blocked",
            "repo": repo,
            "surface": surface,
            "external_action_count": 0,
        }
    blocked = next(
        (
            item
            for item in candidate.get("blocked_surfaces", [])
            if isinstance(item, dict) and item.get("surface") == surface
        ),
        None,
    )
    if blocked:
        return {
            "allowed": False,
            "code": str(blocked.get("code") or "blocked"),
            "repo": repo,
            "surface": surface,
            "external_action_count": 0,
        }
    if surface not in candidate.get("allowed_surfaces", []):
        return {
            "allowed": False,
            "code": "unreviewed_surface_blocked",
            "repo": repo,
            "surface": surface,
            "external_action_count": 0,
        }
    return {
        "allowed": True,
        "code": "reviewed_reference_or_clean_room_surface",
        "repo": repo,
        "surface": surface,
        "external_action_count": 0,
    }


def run_synthetic_framework_slice(
    root: Path, envelope: dict[str, Any]
) -> dict[str, Any]:
    matrix = load_framework_adoption_matrix(root)
    task_id = str(envelope.get("task_id") or "").strip()
    task_type = str(envelope.get("task_type") or "").strip()
    identity = envelope.get("execution_identity")
    payload = envelope.get("payload")
    if not task_id or not task_type:
        raise ValueError("Synthetic framework envelope requires task_id and task_type.")
    if not isinstance(identity, dict):
        raise ValueError("Synthetic framework envelope requires execution_identity.")
    missing = [field for field in IDENTITY_FIELDS if not str(identity.get(field) or "")]
    if missing:
        raise ValueError(
            "Synthetic framework execution identity is incomplete: " + ", ".join(missing)
        )
    if not isinstance(payload, dict) or payload.get("fixture") != "synthetic-only":
        raise ValueError("U25 vertical slice accepts synthetic-only fixtures.")

    identity_copy = deepcopy(identity)
    identity_hash = _canonical_hash(identity_copy)
    lifecycle = list(matrix["synthetic_vertical_slice"]["lifecycle"])
    if lifecycle != ["queued", "claimed", "running", "completed"]:
        raise ValueError("U25 synthetic lifecycle is not the reviewed state sequence.")
    identity_immutable = identity_hash == _canonical_hash(identity_copy)
    return {
        "schema_version": 1,
        "task_id": task_id,
        "task_type": task_type,
        "provider": "local-synthetic-worker",
        "state_history": lifecycle,
        "execution_identity": identity_copy,
        "execution_identity_sha256": identity_hash,
        "identity_immutable": identity_immutable,
        "result": {"fixture": "synthetic-only", "status": "contract_verified"},
        "external_ai_call_count": 0,
        "external_business_action_count": 0,
    }


def framework_adoption_snapshot(root: Path) -> dict[str, Any]:
    matrix = load_framework_adoption_matrix(root)
    slice_result = run_synthetic_framework_slice(
        root,
        {
            "task_id": "u25-snapshot-slice",
            "task_type": "local_contract_check",
            "execution_identity": {
                "project_id": "u25-project",
                "platform": "synthetic-platform",
                "site": "sandbox-site",
                "store_id": "synthetic-store",
                "store_mode": "local_store",
                "browser_profile_id": "browser-u25",
                "network_profile_id": "network-u25",
            },
            "payload": {"fixture": "synthetic-only"},
        },
    )
    candidates = matrix["candidates"]
    return {
        "candidate_count": len(candidates),
        "installed_candidate_count": sum(
            1 for item in candidates if item.get("installed_by_u25") is True
        ),
        "external_call_count": sum(
            int(item.get("external_calls_by_u25") or 0) for item in candidates
        ),
        "configuration_authority": matrix["configuration_authority"],
        "synthetic_slice_verified": bool(
            slice_result.get("identity_immutable")
            and slice_result.get("state_history")
            == ["queued", "claimed", "running", "completed"]
        ),
        "synthetic_slice": slice_result,
        "candidates": [
            {
                "repo": item["repo"],
                "pinned_release": item["pinned_release"],
                "pinned_commit": item["pinned_commit"],
                "license": item["license"],
                "primary_decision": item["primary_decision"],
                "matrix": item["matrix"],
            }
            for item in candidates
        ],
    }
