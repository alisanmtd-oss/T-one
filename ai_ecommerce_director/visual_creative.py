from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from .product_targets import load_product_targets
from .scoring import score_record
from .storage import append_record, read_records
from .types import IntakeRecord
from .video_policy import allows_tiktok_video_strategy


VISUAL_CREATIVE_REPORT_PREFIX = "visual_creative"
VISUAL_CREATIVE_BRIEFS_PREFIX = "visual_creative_briefs"


@dataclass(slots=True)
class VisualCreativeResult:
    run_date: str
    product_briefs: list[dict[str, Any]]
    report: str
    report_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_date": self.run_date,
            "product_briefs": self.product_briefs,
            "report": self.report,
            "report_path": str(self.report_path),
        }


def run_visual_creative_director(root: Path, run_date: str | None = None) -> VisualCreativeResult:
    root = root.resolve()
    report_date = run_date or date.today().isoformat()
    records = read_records(root)
    product_records = [*product_target_visual_records(root), *select_visual_products(records)]
    briefs = [build_visual_brief(record, records) for record in product_records[:20]]
    persist_creative_inspirations(root, briefs)
    persist_video_script_assets(root, briefs)
    persist_ai_video_prompt_training_assets(root, briefs)
    report = build_visual_creative_report(report_date, briefs)
    report_path = write_visual_creative_report(root, report_date, report)
    write_visual_creative_briefs(root, report_date, briefs)
    return VisualCreativeResult(report_date, briefs, report, report_path)


def product_target_visual_records(root: Path) -> list[IntakeRecord]:
    config = load_product_targets(root)
    records: list[IntakeRecord] = []
    for target in config.get("targets", []):
        if not isinstance(target, dict) or not target.get("enabled", True):
            continue
        keywords = target.get("keywords") if isinstance(target.get("keywords"), list) else []
        platforms = target.get("platforms") if isinstance(target.get("platforms"), list) else []
        fields = {
            "product_name": target.get("name") or "",
            "product_family": target.get("product_family") or target.get("name") or "",
            "product_target_id": target.get("id") or "",
            "product_target_name": target.get("name") or "",
            "source_platform": "Product Target Monitor",
            "marketplace": ", ".join(str(item) for item in platforms if str(item).strip()),
            "target_keywords": keywords,
            "keyword_cluster": keywords,
            "notes": target.get("notes") or "",
            "monitoring_scope": "product_target",
        }
        records.append(
            IntakeRecord(
                record_type="product_case",
                fields=fields,
                raw_text=json.dumps(fields, ensure_ascii=False),
                source="product_target_monitor",
                score={"priority": 88},
                director_notes=["Focused product target promoted into visual and video planning."],
            )
        )
    return records


def select_visual_products(records: list[IntakeRecord]) -> list[IntakeRecord]:
    candidates = [
        record
        for record in records
        if record.record_type in {"platform_ranking_signal", "hot_link", "viral_content_signal", "product_case", "money_case"}
    ]
    return sorted(candidates, key=lambda item: float(item.score.get("priority", 0) or 0), reverse=True)


def build_visual_brief(record: IntakeRecord, all_records: list[IntakeRecord] | None = None) -> dict[str, Any]:
    fields = record.fields
    product_name = str(
        fields.get("product_name")
        or fields.get("product_theme")
        or fields.get("page_title")
        or fields.get("url")
        or record.record_id[:8]
    )
    marketplace = str(fields.get("marketplace") or fields.get("source_platform") or "")
    product_family = str(fields.get("product_family") or fields.get("target_keyword") or infer_product_family(product_name))
    keyword_cluster = fields.get("target_keywords") or fields.get("keyword_cluster") or fields.get("keyword") or ""
    if isinstance(keyword_cluster, list):
        keyword_text = " ".join(str(item) for item in keyword_cluster)
    else:
        keyword_text = str(keyword_cluster)
    product_type = infer_product_type(f"{product_name} {product_family} {keyword_text}")
    logo_strategy = logo_placement_strategy(product_type, marketplace)
    video_allowed = allows_tiktok_video_strategy(record)
    creative_memory = collect_creative_memory(all_records or [], product_name, product_family)
    if video_allowed:
        original_ideas = original_material_ideas(product_type, product_name, product_family, creative_memory)
    else:
        original_ideas = image_only_original_material_ideas(product_type, product_name, product_family, creative_memory)
    brief = {
        "source_record_id": record.record_id,
        "source_url": str(fields.get("url") or fields.get("page_url") or fields.get("video_url") or fields.get("product_url") or ""),
        "product_name": product_name,
        "product_target_id": str(fields.get("product_target_id") or ""),
        "product_target_name": str(fields.get("product_target_name") or ""),
        "marketplace": marketplace,
        "product_family": product_family,
        "product_type": product_type,
        "video_allowed": video_allowed,
        "video_policy": "TikTok-only video strategy. Non-TikTok marketplace records stay on product images, listing, reviews, price and ranking analysis.",
        "image_set": image_set_for_product(product_type, product_name),
        "logo_strategy": logo_strategy,
        "video_brief": video_brief_for_product(product_type, product_name, product_family),
        "ai_video_workflow": ai_video_workflow_for_product(product_type, product_name, product_family),
        "creative_memory": creative_memory,
        "original_material_ideas": original_ideas,
        "generation_prompts": generation_prompts(product_type, product_name, product_family, logo_strategy),
        "ai_video_prompt_training": ai_video_prompt_training_pack(
            product_type,
            product_name,
            product_family,
            creative_memory,
            logo_strategy,
            video_allowed,
        ),
        "platform_notes": platform_image_notes(marketplace),
    }
    return brief


def collect_creative_memory(records: list[IntakeRecord], product_name: str, product_family: str) -> dict[str, Any]:
    keys = [product_name.lower(), product_family.lower()]
    matching = [
        record
        for record in records
        if record.record_type
        in {
            "video_script",
            "video_breakdown",
            "viral_content_signal",
            "video_publish_plan",
            "strategy_memory",
            "review_insight",
            "creative_inspiration",
        }
        and record_matches_product(record, keys)
    ]
    if not matching:
        matching = [
            record
            for record in records
            if record.record_type
            in {
                "video_script",
                "video_breakdown",
                "viral_content_signal",
                "video_publish_plan",
                "strategy_memory",
                "review_insight",
                "creative_inspiration",
            }
        ][:20]
    top_records = sorted(matching, key=lambda item: float(item.score.get("priority", 0) or 0), reverse=True)[:12]
    return {
        "source_record_count": len(matching),
        "hooks": top_unique(fields_value(record, ["hook_text", "hook", "creative_angle"]) for record in top_records),
        "titles": top_unique(fields_value(record, ["publish_title", "caption_text", "page_title", "product_name"]) for record in top_records),
        "tags": top_unique(flatten_tag_values(fields_value(record, ["publish_tags", "seo_tags", "keyword_cluster"]) for record in top_records)),
        "scenes": top_unique(fields_value(record, ["scene", "shot_list", "timeline_structure", "original_shot_plan"]) for record in top_records),
        "scripts": top_unique(fields_value(record, ["script_lines", "voiceover", "store_script", "influencer_script"]) for record in top_records),
        "pain_points": top_unique(fields_value(record, ["pain_point", "user_pain_point", "comment_insights", "refund_reason"]) for record in top_records),
        "source_record_ids": [record.record_id for record in top_records],
    }


def record_matches_product(record: IntakeRecord, keys: list[str]) -> bool:
    haystack = " ".join(str(value) for value in record.fields.values()).lower()
    return any(key and key in haystack for key in keys)


def fields_value(record: IntakeRecord, keys: list[str]) -> str:
    for key in keys:
        value = record.fields.get(key)
        if value is None or value == "":
            continue
        if isinstance(value, list):
            if value:
                return ", ".join(str(item) for item in value if str(item).strip())
            continue
        return str(value)
    return ""


def flatten_tag_values(values: Any) -> list[str]:
    result: list[str] = []
    for value in values:
        if not value:
            continue
        text = str(value)
        for part in text.replace("#", " #").replace(",", " ").split():
            clean = part.strip()
            if clean:
                result.append(clean)
    return result


def top_unique(values: Any, limit: int = 8) -> list[str]:
    result: list[str] = []
    for value in values:
        clean = str(value or "").strip()
        if not clean:
            continue
        if len(clean) > 180:
            clean = clean[:177] + "..."
        if clean not in result:
            result.append(clean)
        if len(result) >= limit:
            break
    return result


def original_material_ideas(product_type: str, product_name: str, product_family: str, memory: dict[str, Any]) -> list[dict[str, Any]]:
    hooks = memory.get("hooks") or []
    titles = memory.get("titles") or []
    tags = memory.get("tags") or []
    scenes = memory.get("scenes") or []
    pain_points = memory.get("pain_points") or []
    hook_seed = hooks[0] if hooks else f"I did not expect {product_family} to matter this much."
    title_seed = titles[0] if titles else product_name
    tag_seed = tags[:5] if tags else [f"#{product_family.replace(' ', '').lower()}", "#tiktokshop", "#finds"]
    scene_seed = scenes[0] if scenes else default_scene_for_product(product_type)
    pain_seed = pain_points[0] if pain_points else "buyers need proof, clarity, and a reason to care"
    return [
        {
            "creative_angle": f"Original proof remix for {product_family}",
            "material_type": "store_owned_video",
            "originality_type": "original_remix_from_memory",
            "source_memory": {"hook": hook_seed, "title": title_seed, "tags": tag_seed, "scene": scene_seed, "pain_point": pain_seed},
            "hook": rewrite_hook(hook_seed, product_family),
            "title": rewrite_title(title_seed, product_family),
            "tags": tag_seed,
            "shot_plan": f"0-2s new hook; 2-5s real product proof; 5-10s original scene: {scene_seed}; 10-16s solve pain point: {pain_seed}; 16-22s product-card CTA.",
            "creative_prompt": f"Create an original ecommerce short-video concept for {product_name}. Use historical hook/tag logic but do not copy competitor visuals. Show real product proof, original scene, clear CTA, and safe music.",
            "reuse_boundaries": "Reuse only abstract structure, timing, audience emotion, and tag logic. Do not copy exact footage, exact script, brand marks, characters, music, or competitor layout.",
        },
        {
            "creative_angle": f"Problem-to-proof original material for {product_family}",
            "material_type": "image_set_and_short_video",
            "originality_type": "new_original_angle",
            "source_memory": {"pain_point": pain_seed, "tags": tag_seed},
            "hook": f"Here is the detail most people miss about {product_family}.",
            "title": f"{product_family.title()} real-use proof and details",
            "tags": tag_seed,
            "shot_plan": f"Main image: clean product proof. Detail image: texture/label/fit. Video: pain point -> close-up proof -> lifestyle use -> CTA.",
            "creative_prompt": f"Generate original image and video material for {product_name}: white-background main image, detail proof image, lifestyle use scene, and a 20-second proof-first video.",
            "reuse_boundaries": "Build from our own product photos, own model/scene, and original wording. Avoid unauthorized music and any IP-sensitive visual elements.",
        },
    ]


def image_only_original_material_ideas(product_type: str, product_name: str, product_family: str, memory: dict[str, Any]) -> list[dict[str, Any]]:
    tags = memory.get("tags") or []
    pain_points = memory.get("pain_points") or []
    tag_seed = tags[:5] if tags else [f"#{product_family.replace(' ', '').lower()}", "#ecommerce", "#productdetails"]
    pain_seed = pain_points[0] if pain_points else "buyers need proof, clarity, and a reason to compare"
    return [
        {
            "creative_angle": f"Marketplace image proof set for {product_family}",
            "material_type": "image_set",
            "originality_type": "new_original_angle",
            "source_memory": {"pain_point": pain_seed, "tags": tag_seed},
            "hook": f"Show the product proof buyers need before comparing {product_family}.",
            "title": f"{product_family.title()} image proof set",
            "tags": tag_seed,
            "shot_plan": f"Main image: clean white-background product proof. Detail image: label/material/feature close-up. Lifestyle image: buyer use context for {product_family}.",
            "creative_prompt": f"Generate original ecommerce image directions for {product_name}: white-background main image, detail proof image, bundle/scale image, and lifestyle/model image. Do not generate video scenes for non-TikTok sources.",
            "reuse_boundaries": "Use our own product photos, own model/scene, and original wording. Do not copy competitor layout, copyrighted marks, characters, music, or creator likeness.",
        }
    ]


def default_scene_for_product(product_type: str) -> str:
    return {
        "supplement": "morning/night routine with product close-up and compliant lifestyle context",
        "apparel": "garage, family, outdoor, or daily identity scene with real fit proof",
        "hat": "outdoor walk, workbench, fishing, gym, or truck scene with hat fit proof",
        "fragrance": "clean mirror, getting-ready, walk-by reaction, and bottle close-up",
        "screen_protector": "desk install scene with phone close-up, alignment frame, bubble-free finish, and scratch/fingerprint proof",
    }.get(product_type, "daily use scene with real product proof")


def rewrite_hook(hook: str, product_family: str) -> str:
    if not hook:
        return f"I kept seeing {product_family}, so I tested the detail everyone skips."
    clean = hook.strip().rstrip(".")
    return f"I took this idea and made a {product_family} version: {clean}."


def rewrite_title(title: str, product_family: str) -> str:
    clean = title.strip() if title else product_family
    return f"Original {product_family} test inspired by: {clean}"


def persist_creative_inspirations(root: Path, briefs: list[dict[str, Any]]) -> None:
    for brief in briefs:
        for idea in brief.get("original_material_ideas", [])[:3]:
            fields = {
                "product_name": brief.get("product_name"),
                "product_theme": brief.get("product_family"),
                "creative_angle": idea.get("creative_angle"),
                "material_type": idea.get("material_type"),
                "originality_type": idea.get("originality_type"),
                "source_hooks": idea.get("source_memory", {}).get("hook"),
                "source_titles": idea.get("source_memory", {}).get("title"),
                "source_tags": ", ".join(idea.get("tags") or []),
                "derived_from_memory": brief.get("creative_memory", {}).get("source_record_ids", []),
                "original_shot_plan": idea.get("shot_plan"),
                "creative_prompt": idea.get("creative_prompt"),
                "reuse_boundaries": idea.get("reuse_boundaries"),
            }
            score, notes = score_record("creative_inspiration", fields)
            append_record(
                root,
                IntakeRecord(
                    record_type="creative_inspiration",
                    fields=fields,
                    raw_text=json.dumps(idea, ensure_ascii=False),
                    source="visual_creative_director",
                    score=score,
                    director_notes=notes,
                ),
            )


def persist_video_script_assets(root: Path, briefs: list[dict[str, Any]]) -> None:
    for brief in briefs:
        if not brief.get("video_allowed"):
            continue
        video_brief = brief.get("video_brief") if isinstance(brief.get("video_brief"), dict) else {}
        scripts = [
            {
                "script_type": "store_owned",
                "content_owner": "owned_account",
                "title": "Store-owned proof script",
                "script": video_brief.get("store_owned_script") or "",
            },
            {
                "script_type": "influencer",
                "content_owner": "creator",
                "title": "Influencer proof script",
                "script": video_brief.get("influencer_script") or "",
            },
        ]
        for script in scripts:
            script_text = str(script.get("script") or "").strip()
            if not script_text:
                continue
            source_key = brief.get("product_target_id") or brief.get("source_record_id")
            fields = {
                "script_key": f"visual:{source_key}:{script['script_type']}",
                "script_type": script["script_type"],
                "content_owner": script["content_owner"],
                "product_name": brief.get("product_name"),
                "product_family": brief.get("product_family"),
                "product_target_id": brief.get("product_target_id") or "",
                "product_target_name": brief.get("product_target_name") or brief.get("product_name") or "",
                "product_type": brief.get("product_type"),
                "marketplace": brief.get("marketplace"),
                "title": script["title"],
                "hook_text": first_script_sentence(script_text),
                "script_lines": script_text,
                "shot_order": video_brief.get("shot_order") or "",
                "seedance_2_workflow": brief.get("ai_video_workflow", {}).get("mixed_edit_order", []),
                "music_rule": "Use commercially safe music only. Keep music volume below product voiceover and real product sound.",
                "production_ready": True,
                "human_confirmation_required": True,
                "publish_guardrail": "Do not upload, publish, set music, bind product card, or change shop settings without human confirmation.",
                "reuse_boundaries": "Use original footage and original wording. Do not copy competitor footage, copyrighted music, brand marks, characters, or creator likeness.",
            }
            score, notes = score_record("video_script", fields)
            append_record(
                root,
                IntakeRecord(
                    record_type="video_script",
                    fields=fields,
                    raw_text=json.dumps(fields, ensure_ascii=False),
                    source="visual_creative_director",
                    score=score,
                    director_notes=notes,
                ),
            )


def persist_ai_video_prompt_training_assets(root: Path, briefs: list[dict[str, Any]]) -> None:
    for brief in briefs:
        if not brief.get("video_allowed"):
            continue
        pack = brief.get("ai_video_prompt_training")
        if not isinstance(pack, dict) or not pack.get("enabled"):
            continue
        source_key = brief.get("product_target_id") or brief.get("source_record_id")
        fields = {
            "prompt_key": f"seedance:{source_key}",
            "product_name": brief.get("product_name"),
            "product_family": brief.get("product_family"),
            "product_type": brief.get("product_type"),
            "marketplace": brief.get("marketplace"),
            "ai_video_tool": pack.get("ai_video_tool"),
            "base_prompt": pack.get("base_prompt"),
            "negative_prompt": pack.get("negative_prompt"),
            "shot_prompts": pack.get("shot_prompts", []),
            "camera_motion_bank": pack.get("camera_motion_bank", []),
            "edit_rules": pack.get("edit_rules", []),
            "training_tags": pack.get("training_tags", []),
            "quality_checklist": pack.get("quality_checklist", []),
            "music_rule": pack.get("music_rule"),
            "human_confirmation_required": True,
            "reuse_boundaries": pack.get("reuse_boundaries"),
        }
        score, notes = score_record("ai_video_prompt_training", fields)
        append_record(
            root,
            IntakeRecord(
                record_type="ai_video_prompt_training",
                fields=fields,
                raw_text=json.dumps(pack, ensure_ascii=False),
                source="visual_creative_director",
                score=score,
                director_notes=notes,
            ),
        )


def first_script_sentence(value: str) -> str:
    text = " ".join(str(value or "").split())
    for separator in [". ", "; ", ": "]:
        if separator in text:
            return text.split(separator, 1)[0].strip().rstrip(".;:")
    return text[:140]


def infer_product_type(text: str) -> str:
    lowered = text.lower()
    if any(word in lowered for word in ["screen protector", "tempered glass", "phone film", "camera lens protector", "anti spy", "privacy screen"]):
        return "screen_protector"
    if any(word in lowered for word in ["melatonin", "supplement", "vitamin", "gummies", "capsule"]):
        return "supplement"
    if any(word in lowered for word in ["tee", "t-shirt", "shirt", "hoodie", "sweatshirt"]):
        return "apparel"
    if any(word in lowered for word in ["hat", "cap"]):
        return "hat"
    if any(word in lowered for word in ["perfume", "fragrance", "cologne"]):
        return "fragrance"
    return "general_product"


def infer_product_family(product_name: str) -> str:
    words = [word.strip(" ,.-") for word in product_name.split()[:4]]
    return " ".join(word for word in words if word)


def image_set_for_product(product_type: str, product_name: str) -> list[dict[str, str]]:
    if product_type == "supplement":
        return [
            {"type": "main_white_background", "goal": "Clean bottle/gummy pack on pure white, label readable, no lifestyle clutter."},
            {"type": "detail_label", "goal": "Zoom label, dosage, count, flavor, key compliant benefits without medical claims."},
            {"type": "ingredient_or_texture", "goal": "Show gummies/capsules texture and package scale."},
            {"type": "lifestyle_nightstand", "goal": "Soft bedroom/nightstand scene, calm sleep routine, avoid cure/disease claims."},
            {"type": "comparison_infographic", "goal": "Simple icons for count, flavor, sugar-free/vegan if true, and use timing."},
        ]
    if product_type == "apparel":
        return [
            {"type": "main_white_background", "goal": "Flat lay or ghost mannequin on white; print centered and readable."},
            {"type": "model_front", "goal": "Model wearing product, natural fit, neutral background."},
            {"type": "detail_fabric_print", "goal": "Close-up of fabric, wash, print texture, neck label or sleeve."},
            {"type": "size_fit_chart", "goal": "Clear fit/size guidance and body-type expectation."},
            {"type": "lifestyle_scene", "goal": "Scene matching audience identity: garage, fishing, gym, church, family BBQ."},
        ]
    if product_type == "hat":
        return [
            {"type": "main_white_background", "goal": "Front 3/4 hat angle on white, embroidery or patch readable."},
            {"type": "detail_patch_stitch", "goal": "Close-up of patch, stitching, brim and closure."},
            {"type": "model_outdoor", "goal": "Model wearing hat in target scene."},
            {"type": "fit_adjustment", "goal": "Back closure and size adjustability."},
        ]
    if product_type == "screen_protector":
        return [
            {"type": "main_white_background", "goal": "Phone screen protector pack on pure white, model compatibility visible, included pieces clearly arranged."},
            {"type": "edge_cutout_clarity", "goal": "Close-up showing edge coverage, speaker/camera cutouts, and touch clarity without fake effects."},
            {"type": "installation_steps", "goal": "Three-step install image: clean screen, alignment frame, one-press bubble-free finish."},
            {"type": "proof_detail", "goal": "Fingerprint, scratch, or privacy-angle proof using honest product demonstrations only."},
            {"type": "bundle_contents", "goal": "Show 3-pack or 3+3 bundle contents: screen protectors, lens protectors, wipes, dust stickers, frame."},
        ]
    return [
        {"type": "main_white_background", "goal": "Product isolated on white, shape and packaging clear."},
        {"type": "detail_texture", "goal": "Close-up of material, label, or feature."},
        {"type": "lifestyle_scene", "goal": "Show product in use with target audience."},
        {"type": "scale_context", "goal": "Show size, included items, and usage context."},
    ]


def logo_placement_strategy(product_type: str, marketplace: str) -> dict[str, str]:
    marketplace_lower = marketplace.lower()
    if "amazon" in marketplace_lower:
        return {
            "main_image": "Do not add a floating brand logo unless it is physically printed on the product/package. Amazon main images should stay clean and product-first.",
            "secondary_images": "Place small brand mark on bottom-right or package label only; keep it below the product hierarchy.",
            "video": "Use logo as a 1-second end card or subtle package label, not as a large overlay during product proof shots.",
        }
    return {
        "main_image": "Use product-first composition. If logo is needed, keep it small and aligned with packaging or bottom-right safe area.",
        "secondary_images": "Use logo on comparison/detail cards, lower corner, with enough margin.",
        "video": "Use logo in opening/closing card and keep main demonstration clean.",
    }


def platform_image_notes(marketplace: str) -> list[str]:
    if "amazon" in marketplace.lower():
        return [
            "Main image should usually be white background and product-only.",
            "Avoid exaggerated badges, medical claims, before/after claims, and heavy text on the main image.",
            "Use secondary images for benefits, instructions, comparison, and lifestyle scenes.",
        ]
    return [
        "Keep the first image clear and product-identifiable.",
        "Use secondary images for audience emotion, scene, proof, and social context.",
    ]


def video_brief_for_product(product_type: str, product_name: str, product_family: str) -> dict[str, str]:
    if product_type == "supplement":
        return {
            "store_owned_script": f"Night routine angle for {product_name}: show bottle, texture, routine timing, calm bedroom scene, compliant CTA.",
            "influencer_script": f"Creator shows personal wind-down routine with {product_family}, focuses on habit and taste/format, avoids cure claims.",
            "shot_order": "0-2s routine hook, 2-5s product/package, 5-10s texture/detail, 10-18s lifestyle use, 18-22s CTA.",
        }
    if product_type == "screen_protector":
        return {
            "store_owned_script": f"Installation-proof angle for {product_name}: dusty/scratched phone close-up, alignment frame, one clean press, bubble-free close-up, scratch/fingerprint proof, bundle CTA.",
            "influencer_script": f"Creator opens with install anxiety for {product_family}, shows real hand installation, clean result, privacy or camera-lens detail, and why the bundle is worth it.",
            "shot_order": "0-2s anxiety hook, 2-5s dirty or scratched phone close-up, 5-10s alignment-frame install, 10-15s bubble-free/proof detail, 15-20s bundle/value CTA.",
        }
    return {
        "store_owned_script": f"Product proof angle for {product_name}: white-background detail, model/use scene, audience reason, CTA.",
        "influencer_script": f"Creator frames {product_family} around identity, use case, gift reason, or pain point.",
        "shot_order": "0-2s hook, 2-5s product proof, 5-12s detail/model scene, 12-18s emotional reason, 18-22s CTA.",
    }


def ai_video_workflow_for_product(product_type: str, product_name: str, product_family: str) -> dict[str, Any]:
    real_shots = [
        "real product/package close-up",
        "real texture/material/detail proof",
        "real hand-use or model-fit proof",
    ]
    if product_type == "apparel":
        real_shots.append("real fabric, wash, print, size/fit proof")
    if product_type == "supplement":
        real_shots.append("real label, count, flavor/texture proof without medical claims")
    if product_type == "screen_protector":
        real_shots.extend(
            [
                "real phone model compatibility and package contents",
                "real alignment-frame installation with hands visible",
                "real bubble-free finish, edge/cutout close-up, and honest fingerprint/scratch proof",
            ]
        )
    return {
        "preferred_ai_video_tool": "Seedance 2.0",
        "real_shot_must_have": real_shots,
        "seedance_support_shots": [
            f"lifestyle scene for {product_family}",
            "motion transition between product proof and use scene",
            "clean B-roll background that does not fake product performance",
        ],
        "mixed_edit_order": [
            "0-2s hook subtitle with strongest audience reason",
            "2-5s real product proof",
            "5-10s Seedance 2.0 support scene or motion shot",
            "10-16s real detail/use proof",
            "16-22s offer, product-card CTA, or live-room link cue",
        ],
        "guardrails": [
            "Do not use unauthorized celebrity likeness, copyrighted characters, brand marks, competitor footage, or unsafe music.",
            "Do not create fake product effects, false before/after, medical claims, or unrealistic performance proof.",
            "Publish/upload/live use requires human confirmation.",
        ],
    }


def ai_video_prompt_training_pack(
    product_type: str,
    product_name: str,
    product_family: str,
    memory: dict[str, Any],
    logo_strategy: dict[str, str],
    video_allowed: bool,
) -> dict[str, Any]:
    if not video_allowed:
        return {
            "enabled": False,
            "reason": "TikTok video prompt training is created only from TikTok / TikTok Shop / FastMoss / Kalodata video-side signals.",
        }
    hooks = memory.get("hooks") or []
    scenes = memory.get("scenes") or []
    tags = memory.get("tags") or []
    pain_points = memory.get("pain_points") or []
    hook_seed = hooks[0] if hooks else f"Why are people suddenly talking about {product_family}?"
    scene_seed = scenes[0] if scenes else default_scene_for_product(product_type)
    pain_seed = pain_points[0] if pain_points else "buyer needs fast visual proof before trusting the product"
    tag_seed = tags[:6] if tags else [f"#{product_family.replace(' ', '').lower()}", "#tiktokshop", "#productfinds"]
    shot_prompts = ai_video_shot_prompts(product_type, product_name, product_family, hook_seed, scene_seed, pain_seed)
    return {
        "enabled": True,
        "ai_video_tool": "Seedance 2.0",
        "training_goal": "Build reusable ecommerce video prompt patterns from proven TikTok hooks, scenes, proof shots, and CTA structures.",
        "base_prompt": (
            f"Create a vertical 9:16 ecommerce short-video support sequence for {product_name}. "
            f"Audience theme: {product_family}. Keep the product truthful and visible. "
            "Use AI-generated video only for support scenes, motion transitions, lifestyle atmosphere, and B-roll. "
            "Reserve real product footage for package, texture, installation, fit, label, and performance proof. "
            f"Opening hook logic: {hook_seed}. Buyer pain point to answer: {pain_seed}. "
            f"Logo rule: {logo_strategy['video']}"
        ),
        "negative_prompt": (
            "No unauthorized celebrity likeness, no copyrighted character, no competitor logo, no copied creator footage, "
            "no platform UI impersonation, no fake before-after result, no medical cure claim, no exaggerated product performance, "
            "no unreadable text, no unsafe music reference, no watermark-like fake brand overlay."
        ),
        "shot_prompts": shot_prompts,
        "camera_motion_bank": [
            "slow push-in on product proof",
            "macro pan across texture or detail",
            "handheld UGC-style reveal",
            "top-down demonstration angle",
            "match cut from real proof to AI lifestyle scene",
            "soft parallax product-card transition",
        ],
        "edit_rules": [
            "0-2s must show hook subtitle or strongest visual problem.",
            "Every AI support shot must be followed or preceded by real product proof.",
            "Keep music under voice/product sound; music volume target 0.18-0.30 when voiceover exists.",
            "Use commercial-safe music only; if copyright is uncertain, mark for human review.",
            "End with product card, offer, live-room cue, or comment/save CTA.",
        ],
        "music_rule": "Use commercial-safe music only. Keep BGM lower than voiceover and real demonstration sounds.",
        "quality_checklist": [
            "Hook is clear within 2 seconds.",
            "Product is identifiable before the CTA.",
            "At least two real proof shots exist.",
            "AI scene does not fake product performance.",
            "Script, title, tags, and product-card CTA match the same product.",
            "Rights, music, claims, and brand/IP risks are checked before publishing.",
        ],
        "training_tags": [
            f"product_type:{product_type}",
            f"product_family:{product_family}",
            "platform:tiktok",
            "tool:seedance_2",
            "mode:real_shot_plus_ai_mixed_edit",
            *[f"tag:{tag.lstrip('#')}" for tag in tag_seed[:4]],
        ],
        "reuse_boundaries": (
            "Train and reuse only the structure: hook type, shot order, camera motion, proof logic, scene category, and CTA pattern. "
            "Do not reuse exact competitor footage, exact voiceover, protected music, celebrity likeness, branded graphics, or copyrighted characters."
        ),
    }


def ai_video_shot_prompts(
    product_type: str,
    product_name: str,
    product_family: str,
    hook_seed: str,
    scene_seed: str,
    pain_seed: str,
) -> list[dict[str, str]]:
    common = [
        {
            "shot": "hook_opening",
            "time_range": "0-2s",
            "prompt": f"Vertical TikTok-style opening shot for {product_family}: visually express the buyer problem without showing fake results. Hook subtitle direction: {hook_seed}",
            "must_use_real_footage": "optional",
        },
        {
            "shot": "real_product_proof_slot",
            "time_range": "2-5s",
            "prompt": f"Reserve this slot for real footage of {product_name}: package, texture, label, fit, or use proof. Do not replace this slot with AI-only visuals.",
            "must_use_real_footage": "yes",
        },
        {
            "shot": "ai_lifestyle_support",
            "time_range": "5-9s",
            "prompt": f"Generate an AI support scene for {product_family}: {scene_seed}. Make it realistic, clean, and product-adjacent, but do not invent false product performance.",
            "must_use_real_footage": "no",
        },
        {
            "shot": "pain_to_proof_bridge",
            "time_range": "9-14s",
            "prompt": f"Create a transition from buyer pain point to proof: {pain_seed}. Use close-up motion, hand movement, or scene change to make the proof easy to understand.",
            "must_use_real_footage": "mixed",
        },
        {
            "shot": "cta_support",
            "time_range": "14-20s",
            "prompt": "Generate a clean support shot for product-card CTA: space for short subtitle, coupon/live-room cue, or comment/save prompt. Keep the product category clear.",
            "must_use_real_footage": "optional",
        },
    ]
    if product_type == "screen_protector":
        common.insert(
            2,
            {
                "shot": "installation_macro",
                "time_range": "5-8s",
                "prompt": "Close-up phone installation scene: alignment frame, dust removal, one smooth press, bubble-free finish. Use real footage for the final proof; AI may only support motion or background.",
                "must_use_real_footage": "mixed",
            },
        )
    elif product_type == "apparel":
        common.insert(
            2,
            {
                "shot": "fit_and_texture_macro",
                "time_range": "5-8s",
                "prompt": "Realistic apparel detail scene: fabric texture, wash effect, print edge, neckline, sleeve, and model fit. Avoid fake logos or copied brand styling.",
                "must_use_real_footage": "mixed",
            },
        )
    elif product_type == "supplement":
        common.insert(
            2,
            {
                "shot": "routine_and_label_safe",
                "time_range": "5-8s",
                "prompt": "Calm routine scene with product bottle and texture; keep label visible and avoid medical cure, disease, or guaranteed effect claims.",
                "must_use_real_footage": "mixed",
            },
        )
    return common


def generation_prompts(product_type: str, product_name: str, product_family: str, logo_strategy: dict[str, str]) -> dict[str, Any]:
    return {
        "main_image_prompt": (
            f"Create an ecommerce main product image for {product_name}. "
            f"Product type: {product_type}. Pure white background, sharp product edges, realistic lighting, "
            f"commercial catalog style, no extra props, no exaggerated badges. Logo rule: {logo_strategy['main_image']}"
        ),
        "detail_image_prompt": (
            f"Create a detailed ecommerce secondary image for {product_name}. "
            f"Show key physical details, package/texture/material, readable composition, clean infographic spacing. "
            f"Use only compliant factual text placeholders."
        ),
        "model_lifestyle_prompt": (
            f"Create a realistic lifestyle/model product image for {product_family}. "
            f"Show target user context, natural light, product clearly visible, premium ecommerce style, no clutter."
        ),
        "short_video_prompt": (
            f"Use Seedance 2.0 to generate supporting shots for a 20-second ecommerce product video for {product_name}. "
            f"Keep real footage as the product proof. AI shots should cover scene, motion, transition, or lifestyle support only. "
            f"Structure: hook, real product proof, AI support shot, real detail/use shot, CTA. Keep logo subtle: {logo_strategy['video']}"
        ),
    }


def build_visual_creative_report(run_date: str, briefs: list[dict[str, Any]]) -> str:
    lines = [
        "# Visual Creative Director Report",
        "",
        f"Date: {run_date}",
        "",
        "## What This Produces",
        "",
        "- Main image direction, detail image direction, model/lifestyle image direction, logo placement, and short-video brief.",
        "- Short-video briefs and video scripts are generated only from TikTok-side signals: TikTok, TikTok Shop, FastMoss, or Kalodata.",
        "- It prepares generation prompts and creative tasks. It does not publish or upload assets automatically.",
        "",
    ]
    if not briefs:
        lines.append("No product records available yet. Add focused targets or run Amazon monitoring first.")
        return "\n".join(lines).rstrip() + "\n"
    for brief in briefs:
        lines.extend(
            [
                f"## {brief['product_name']}",
                "",
                f"- Product type: {brief['product_type']}",
                f"- Product family: {brief['product_family']}",
                f"- Marketplace: {brief['marketplace'] or 'Unknown'}",
                f"- Main image logo rule: {brief['logo_strategy']['main_image']}",
                "",
                "Image set:",
            ]
        )
        for image in brief["image_set"]:
            lines.append(f"- {image['type']}: {image['goal']}")
        if brief.get("video_allowed"):
            prompt_pack = brief.get("ai_video_prompt_training") if isinstance(brief.get("ai_video_prompt_training"), dict) else {}
            shot_prompt_count = len(prompt_pack.get("shot_prompts") or [])
            lines.extend(
                [
                    "",
                    "TikTok Video:",
                    f"- Store-owned: {brief['video_brief']['store_owned_script']}",
                    f"- Influencer: {brief['video_brief']['influencer_script']}",
                    f"- Shot order: {brief['video_brief']['shot_order']}",
                    f"- Preferred AI video tool: {brief['ai_video_workflow']['preferred_ai_video_tool']}",
                    f"- Mixed edit order: {' > '.join(brief['ai_video_workflow']['mixed_edit_order'])}",
                    f"- AI video prompt training: {prompt_pack.get('ai_video_tool', 'Seedance 2.0')} prompt pack, {shot_prompt_count} reusable shot prompts, real-shot + AI mixed-edit mode.",
                    f"- AI video guardrails: {'; '.join(brief['ai_video_workflow']['guardrails'])}",
                ]
            )
        else:
            lines.extend(
                [
                    "",
                    "TikTok Video:",
                    "- Skipped: video research, video scripts, creator scripts, and AI video prompts are TikTok-only. Use this source for images, listing, price, reviews, and ranking decisions only.",
                ]
            )
        lines.extend(
            [
                "",
                "Creative memory:",
                f"- Historical hooks: {', '.join(brief['creative_memory']['hooks']) or '-'}",
                f"- Historical titles: {', '.join(brief['creative_memory']['titles']) or '-'}",
                f"- Historical tags: {', '.join(brief['creative_memory']['tags']) or '-'}",
                f"- Historical pain points: {', '.join(brief['creative_memory']['pain_points']) or '-'}",
                "",
                "Original material ideas:",
            ]
        )
        for idea in brief.get("original_material_ideas", []):
            lines.extend(
                [
                    f"- {idea['creative_angle']}",
                    f"  Hook: {idea['hook']}",
                    f"  Shot plan: {idea['shot_plan']}",
                    f"  Prompt: {idea['creative_prompt']}",
                    f"  Boundary: {idea['reuse_boundaries']}",
                ]
            )
        prompt_lines = [
            "",
            "Generation prompts:",
            f"- Main: {brief['generation_prompts']['main_image_prompt']}",
            f"- Detail: {brief['generation_prompts']['detail_image_prompt']}",
            f"- Lifestyle/model: {brief['generation_prompts']['model_lifestyle_prompt']}",
        ]
        if brief.get("video_allowed"):
            prompt_lines.append(f"- TikTok video: {brief['generation_prompts']['short_video_prompt']}")
            prompt_pack = brief.get("ai_video_prompt_training") if isinstance(brief.get("ai_video_prompt_training"), dict) else {}
            prompt_lines.append(f"- Seedance training base: {prompt_pack.get('base_prompt', '')}")
            prompt_lines.append(f"- Seedance negative: {prompt_pack.get('negative_prompt', '')}")
        else:
            prompt_lines.append("- TikTok video: skipped for non-TikTok marketplace source.")
        prompt_lines.append("")
        lines.extend(prompt_lines)
    return "\n".join(lines).rstrip() + "\n"


def write_visual_creative_report(root: Path, run_date: str, content: str) -> Path:
    output_dir = root / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{VISUAL_CREATIVE_REPORT_PREFIX}_{run_date}.md"
    path.write_text(content, encoding="utf-8")
    return path


def write_visual_creative_briefs(root: Path, run_date: str, briefs: list[dict[str, Any]]) -> Path:
    output_dir = root / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{VISUAL_CREATIVE_BRIEFS_PREFIX}_{run_date}.json"
    path.write_text(json.dumps(briefs, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def latest_visual_creative_briefs(root: Path) -> tuple[list[dict[str, Any]], Path | None]:
    output_dir = root / "outputs"
    if not output_dir.exists():
        return [], None
    paths = sorted(output_dir.glob(f"{VISUAL_CREATIVE_BRIEFS_PREFIX}_*.json"), reverse=True)
    if not paths:
        return [], None
    try:
        payload = json.loads(paths[0].read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return [], paths[0]
    if not isinstance(payload, list):
        return [], paths[0]
    return [item for item in payload if isinstance(item, dict)], paths[0]
