from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from .storage import append_record
from .types import IntakeRecord


SOURCE_REGISTRY = Path("config") / "amazon_multimodal_training_sources.json"
EVAL_REGISTRY = Path("config") / "amazon_training_eval_cases.json"
CURRICULUM_REGISTRY = Path("config") / "amazon_training_curriculum.json"
AGENT_ID = "amazon-commerce-operator"


@dataclass(slots=True)
class AmazonTrainingBootstrapResult:
    run_date: str
    sources_registered: int
    official_policy_documents: int
    verified_seed_claims: int
    curriculum_domains: int
    eval_cases_registered: int
    pack_id: str
    report_path: Path
    manifest_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_date": self.run_date,
            "sources_registered": self.sources_registered,
            "official_policy_documents": self.official_policy_documents,
            "verified_seed_claims": self.verified_seed_claims,
            "curriculum_domains": self.curriculum_domains,
            "eval_cases_registered": self.eval_cases_registered,
            "pack_id": self.pack_id,
            "report_path": str(self.report_path),
            "manifest_path": str(self.manifest_path),
        }


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _content_hash(root: Path, source: dict[str, Any]) -> tuple[str, str]:
    location = str(source.get("location") or "")
    if source.get("source_type") == "local_canonical":
        path = root / location
        return sha256(path.read_bytes()).hexdigest(), "verified_local_file"
    metadata = json.dumps(
        {
            "location": location,
            "captured_at": source.get("captured_at"),
            "name": source.get("name"),
        },
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    return sha256(metadata).hexdigest(), "metadata_registered_requires_capture"


def run_amazon_training_bootstrap(root: Path, run_date: str | None = None) -> AmazonTrainingBootstrapResult:
    root = root.resolve()
    day = run_date or date.today().isoformat()
    now = datetime.now(timezone.utc).isoformat()
    source_registry = _load_json(root / SOURCE_REGISTRY)
    eval_registry = _load_json(root / EVAL_REGISTRY)
    curriculum_registry = _load_json(root / CURRICULUM_REGISTRY)
    domains = curriculum_registry.get("domains") or []
    source_ids: list[str] = []
    policy_ids: list[str] = []

    for source in source_registry.get("sources") or []:
        source_id = str(source["id"])
        digest, capture_status = _content_hash(root, source)
        source_ids.append(source_id)
        fields = {
            "source_id": source_id,
            "checksum": digest,
            "title": source["name"],
            "source_type": source["source_type"],
            "modality": source["modality"],
            "authority_tier": source["authority_tier"],
            "location": source["location"],
            "captured_at_utc": source["captured_at"],
            "rights_status": source["rights_status"],
            "raw_reuse_allowed": source["raw_reuse_allowed"],
            "commercial_use_allowed": source["commercial_use_allowed"],
            "platform": source["marketplace"],
            "country_site": source["country_site"],
            "store_scope": source["store_scope"],
            "update_frequency": source["update_frequency"],
            "capture_status": capture_status,
            "status": "verified" if capture_status == "verified_local_file" else "captured",
        }
        append_record(
            root,
            IntakeRecord(
                record_type="source_document",
                record_id=f"src_{source_id}",
                source="amazon_training_source_registry",
                raw_text=f"{source['name']} | {source['location']}",
                fields=fields,
                review_status="approved" if capture_status == "verified_local_file" else "pending_capture",
                confidence=1.0 if capture_status == "verified_local_file" else 0.75,
            ),
        )
        if source["authority_tier"] == "official_current":
            policy_id = f"pdoc_{source_id}"
            policy_ids.append(policy_id)
            append_record(
                root,
                IntakeRecord(
                    record_type="policy_document",
                    record_id=policy_id,
                    source="amazon_training_source_registry",
                    raw_text=f"Registered official Amazon reference: {source['name']}",
                    fields={
                        "policy_document_id": policy_id,
                        "platform": source["marketplace"],
                        "document_type": source["source_type"],
                        "title": source["name"],
                        "source_url": source["location"],
                        "source_id": source_id,
                        "version_label": source["captured_at"],
                        "captured_at_utc": source["captured_at"],
                        "content_hash": digest,
                        "status": "active",
                        "capture_status": capture_status,
                    },
                    review_status="pending_capture",
                    confidence=0.75,
                ),
            )

    eval_ids: list[str] = []
    eval_suite = str(eval_registry["eval_suite"])
    for case in eval_registry.get("cases") or []:
        eval_id = str(case["eval_case_id"])
        eval_ids.append(eval_id)
        append_record(
            root,
            IntakeRecord(
                record_type="eval_case",
                record_id=eval_id,
                source="amazon_training_eval_registry",
                raw_text=str(case["prompt"]),
                fields={**case, "eval_suite": eval_suite, "status": "active"},
                review_status="approved",
                confidence=1.0,
            ),
        )

    claim_ids: list[str] = []
    for claim in source_registry.get("verified_seed_claims") or []:
        claim_id = str(claim["evidence_claim_id"])
        claim_ids.append(claim_id)
        append_record(
            root,
            IntakeRecord(
                record_type="evidence_claim",
                record_id=claim_id,
                source="amazon_training_verified_seed_claims",
                raw_text=str(claim["claim_text"]),
                fields={
                    **claim,
                    "source_chunk_id": "metadata_verified_web_capture",
                    "review_status": "verified",
                    "status": "active",
                },
                review_status="approved",
                confidence=0.9,
            ),
        )

    pack_id = f"adp_amazon_commerce_operator_{day}"
    append_record(
        root,
        IntakeRecord(
            record_type="agent_distillation_pack",
            record_id=pack_id,
            source="amazon_training_bootstrap",
            raw_text="Amazon evidence-first multimodal source and regression-eval pack.",
            fields={
                "distillation_pack_id": pack_id,
                "agent_id": AGENT_ID,
                "run_date": day,
                "skill_path": "skills/amazon-commerce-operator/SKILL.md",
                "source_ids": source_ids,
                "policy_document_ids": policy_ids,
                "eval_suite": eval_suite,
                "eval_case_ids": eval_ids,
                "evidence_claim_ids": claim_ids,
                "curriculum_domain_ids": [domain["id"] for domain in domains],
                "curriculum_graduation_policy": curriculum_registry.get("graduation_policy") or {},
                "safe_mode": True,
                "external_effects_require_confirmation": True,
                "generated_at_utc": now,
            },
            review_status="approved",
            confidence=1.0,
        ),
    )

    output_dir = root / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / f"amazon_training_bootstrap_{day}.json"
    report_path = output_dir / f"AMAZON_TRAINING_BOOTSTRAP_{day}.md"
    manifest = {
        "run_date": day,
        "generated_at_utc": now,
        "agent_id": AGENT_ID,
        "pack_id": pack_id,
        "source_ids": source_ids,
        "policy_document_ids": policy_ids,
        "eval_suite": eval_suite,
        "eval_case_ids": eval_ids,
        "evidence_claim_ids": claim_ids,
        "curriculum_domain_ids": [domain["id"] for domain in domains],
        "safe_mode": True,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                f"# Amazon Training Bootstrap - {day}",
                "",
                f"- Agent: `{AGENT_ID}`",
                f"- Registered sources: {len(source_ids)}",
                f"- Official policy references: {len(policy_ids)}",
                f"- Regression eval cases: {len(eval_ids)}",
                f"- Verified seed claims: {len(claim_ids)}",
                f"- Independent curriculum domains: {len(domains)}",
                "- Mode: safe learning, read-only collection, approval-gated external effects",
                "",
                "## Next learning loop",
                "",
                "1. Refresh due official sources and store captures.",
                "2. Extract claims with spans, regions or timestamps.",
                "3. Run contradiction and stale-evidence checks.",
                "4. Run the Amazon eval suite before memory promotion.",
                "5. Feed verified store outcomes back into StrategyMemory and the operation ledger.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return AmazonTrainingBootstrapResult(day, len(source_ids), len(policy_ids), len(claim_ids), len(domains), len(eval_ids), pack_id, report_path, manifest_path)
