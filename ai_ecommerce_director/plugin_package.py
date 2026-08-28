from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile, ZipInfo


EXTENSION_DIR = Path("browser_extension") / "ai_ecommerce_director_capture"
PACKAGE_NAME = "AI_Ecommerce_Director_Capture_Extension.zip"
PACKAGE_MANIFEST_NAME = "PACKAGE_MANIFEST.json"
INSTALL_GUIDE_NAME = "INSTALL_GUIDE.txt"
PACKAGE_SCHEMA_VERSION = 1
FIXED_ZIP_TIMESTAMP = (2020, 1, 1, 0, 0, 0)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()


def _source_files(extension_dir: Path) -> list[tuple[str, bytes]]:
    output: list[tuple[str, bytes]] = []
    for path in sorted(extension_dir.rglob("*")):
        if path.is_dir():
            continue
        if path.is_symlink():
            raise ValueError(f"Browser extension package does not accept symlinks: {path}")
        relative = path.relative_to(extension_dir).as_posix()
        if relative.startswith("/") or ".." in Path(relative).parts:
            raise ValueError(f"Unsafe extension package path: {relative}")
        output.append((relative, path.read_bytes()))
    return output


def _source_digest(files: list[tuple[str, bytes]]) -> str:
    digest = hashlib.sha256()
    for relative, content in files:
        encoded = relative.encode("utf-8")
        digest.update(len(encoded).to_bytes(4, "big"))
        digest.update(encoded)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest().upper()


def _zip_info(name: str) -> ZipInfo:
    info = ZipInfo(name, date_time=FIXED_ZIP_TIMESTAMP)
    info.compress_type = ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def _package_manifest(files: list[tuple[str, bytes]], guide_bytes: bytes) -> bytes:
    payload = {
        "schema_version": PACKAGE_SCHEMA_VERSION,
        "package_format": "chrome_unpacked_extension_zip",
        "extension_root": "ai_ecommerce_director_capture",
        "source_sha256": _source_digest(files),
        "source_file_count": len(files),
        "files": [
            {"path": relative, "size": len(content), "sha256": _sha256_bytes(content)}
            for relative, content in files
        ],
        "install_guide_sha256": _sha256_bytes(guide_bytes),
        "reproducible_build": {
            "fixed_zip_timestamp": "2020-01-01T00:00:00Z",
            "sorted_entries": True,
            "normalized_file_mode": "0644",
        },
        "installation_performed": False,
        "browser_launched": False,
        "external_action_count": 0,
    }
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def build_extension_package(root: Path) -> Path:
    extension_dir = root / EXTENSION_DIR
    if not extension_dir.exists():
        raise FileNotFoundError(f"Browser extension folder not found: {extension_dir}")

    output_dir = root / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    package_path = output_dir / PACKAGE_NAME

    files = _source_files(extension_dir)
    guide_bytes = build_install_guide().encode("utf-8")
    manifest_bytes = _package_manifest(files, guide_bytes)
    temporary = package_path.with_suffix(package_path.suffix + ".tmp")
    with ZipFile(temporary, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for relative, content in files:
            archive.writestr(_zip_info(f"ai_ecommerce_director_capture/{relative}"), content)
        archive.writestr(_zip_info(INSTALL_GUIDE_NAME), guide_bytes)
        archive.writestr(_zip_info(PACKAGE_MANIFEST_NAME), manifest_bytes)
    os.replace(temporary, package_path)
    return package_path


def verify_extension_package(extension_dir: Path, package_path: Path) -> dict[str, Any]:
    files = _source_files(extension_dir) if extension_dir.is_dir() else []
    source_sha256 = _source_digest(files) if files else ""
    expected_entries = {
        f"ai_ecommerce_director_capture/{relative}" for relative, _ in files
    } | {INSTALL_GUIDE_NAME, PACKAGE_MANIFEST_NAME}
    result: dict[str, Any] = {
        "package_exists": package_path.is_file(),
        "verified": False,
        "source_sha256": source_sha256,
        "source_file_count": len(files),
        "package_source_sha256": "",
        "package_schema_version": 0,
        "manifest_valid": False,
        "content_matches_source": False,
        "missing_entries": [],
        "unexpected_entries": [],
        "unsafe_entries": [],
    }
    if not package_path.is_file() or not files:
        return result
    try:
        with ZipFile(package_path) as archive:
            names = archive.namelist()
            name_set = set(names)
            result["unsafe_entries"] = sorted(
                name for name in names if name.startswith("/") or ".." in Path(name).parts
            )
            result["missing_entries"] = sorted(expected_entries - name_set)
            result["unexpected_entries"] = sorted(name_set - expected_entries)
            if PACKAGE_MANIFEST_NAME not in name_set:
                return result
            try:
                manifest = json.loads(archive.read(PACKAGE_MANIFEST_NAME).decode("utf-8"))
            except (KeyError, UnicodeDecodeError, ValueError):
                return result
            result["package_schema_version"] = int(manifest.get("schema_version") or 0)
            result["package_source_sha256"] = str(manifest.get("source_sha256") or "")
            manifest_files = manifest.get("files") if isinstance(manifest.get("files"), list) else []
            expected_manifest_files = [
                {"path": relative, "size": len(content), "sha256": _sha256_bytes(content)}
                for relative, content in files
            ]
            guide_bytes = build_install_guide().encode("utf-8")
            result["manifest_valid"] = bool(
                result["package_schema_version"] == PACKAGE_SCHEMA_VERSION
                and result["package_source_sha256"] == source_sha256
                and manifest.get("source_file_count") == len(files)
                and manifest_files == expected_manifest_files
                and manifest.get("install_guide_sha256") == _sha256_bytes(guide_bytes)
                and manifest.get("installation_performed") is False
                and manifest.get("browser_launched") is False
                and manifest.get("external_action_count") == 0
            )
            content_matches = True
            for relative, content in files:
                entry = f"ai_ecommerce_director_capture/{relative}"
                if entry not in name_set or archive.read(entry) != content:
                    content_matches = False
                    break
            if INSTALL_GUIDE_NAME not in name_set or archive.read(INSTALL_GUIDE_NAME) != guide_bytes:
                content_matches = False
            result["content_matches_source"] = content_matches
            result["verified"] = bool(
                result["manifest_valid"]
                and content_matches
                and not result["missing_entries"]
                and not result["unexpected_entries"]
                and not result["unsafe_entries"]
            )
            return result
    except (BadZipFile, OSError):
        return result


def build_install_guide() -> str:
    return """AI Ecommerce Director Capture Extension

Purpose:
Capture visible page data from FastMoss, Kalodata, EchoTik, TikTok Shop, Amazon, Etsy, store backends, and POD admin pages into AI Ecommerce Director.

Install in Chrome:
1. Unzip this package.
2. Open Chrome and go to chrome://extensions/.
3. Enable Developer mode.
4. Click Load unpacked.
5. Select the extracted ai_ecommerce_director_capture folder.

Install in Bit Browser:
1. Open the Bit Browser window for the target store.
2. Open the extensions management page.
3. Enable Developer mode.
4. Load the extracted ai_ecommerce_director_capture folder.
5. Use a different Store ID for each store profile, for example TK-HAT-US-01.
6. Fill Country / Site with a concrete site, for example US, SG, MY, TH, VN, PH, or ID. Do not use SEA or Latin America as an executable store.
7. Fill Store Mode and Ownership so every capture carries platform + country/site + store mode + ownership.
8. Fill Bit Window with the Bit Browser profile name or ID, and IP Region with the profile's IP country/region.
9. Click Check Local Connection before capturing. It should say the extension is connected to http://127.0.0.1:8765 or to your configured host.
10. Click Send Local Test Capture once after installation. It writes a local-only Amazon BitBrowser profile test record so you can verify the extension-to-AI pipeline before touching Seller Central.
11. Click Pull Store Task Package to read the latest task package or pending preflight gate for the current route. If only a pending approval exists, the extension turns it into a capture-only checklist; if nothing appears, open the approval queue first. It will not bypass confirmation.
12. The popup renders the pulled package or pending gate as an onsite checklist: allowed steps, missing prerequisites, required evidence, and buttons/actions that must not be clicked. Amazon pending gates become surface-specific checklists: listing preflight, Seller Central template download, store operations capture, or ads capture. The next Capture Current Page attaches that task package to the evidence record and adds page checks for visible blockers or prohibited action buttons.
13. Keep Auto-scroll page before capture enabled for Seller Central pages. It scrolls the page read-only and records page_scroll_coverage_percent, page_reached_bottom, and page_scroll_positions_sampled so the AI can reject one-screen evidence.

Amazon new store default:
- When the current tab is Amazon Seller Central or Amazon Advertising, the popup pre-fills Amazon / US / marketplace_seller / self_store.
- For the current BitBrowser profile Amazon test store, use Store ID amazon-us-new-store unless you assign a more specific store ID.
- Capture store status with Store health / suspension / violation first, then capture listing, coupon, campaign, or ad pages as Backend operation path.
- On Amazon Product Identity, Add a product, Brand Registry, UPC/GTIN, or Product ID exemption pages, use Amazon listing / Product Identity preflight. The plugin records blockers and prepares a preflight package; it does not save the listing, publish, submit approvals, or launch ads.
- On Amazon Add Products / Spreadsheet / Add products via upload / inventory template pages, use Pull Store Task Package to pull the listing_template task. The popup will guide the operator to download the blank Amazon US Clothing/T-shirt template into Downloads, then return to AI Director for local header mapping. It must not upload the final file, submit a feed, save, publish, change prices, or change inventory.
- The Open Amazon Upload Products button only opens the Seller Central upload entry candidate. If Amazon redirects, use Catalog > Add Products via Upload > Spreadsheet manually. It does not click download, upload, submit, save, publish, or change any listing data.
- The Check Full Chain Workbench button shows one connected Amazon 10001 operating view: listing, images, pricing, inventory, fulfillment, orders, ads, promotions, settlement, compliance, API/MCP readiness, final upload gates, blockers, and blocked external actions.
- The Build Next Action Pack button converts that workbench into ordered local-only packages: template candidate, image upload plan, public image fetch check, identity/PTD gate, FBM inventory draft, ads draft, promotion/profit check, and settlement/cashflow draft.
- The Export Execution Draft Files button writes local CSV drafts for FBM inventory, Sponsored Products keywords, promotion/profit checks, settlement/cashflow, and the cost input sheet. These are review files only and must not be uploaded or applied without confirmation.
- The Check Draft File QA button validates those CSV drafts for SKU coverage, launch guards, conservative ad budget/bid values, open promotion cost inputs, and settlement formula coverage.
- The Check Profit & ACOS button reads the local cost input sheet and calculates single/4-pack profit, break-even ACOS, and test ad spend limits. It does not change prices, create promotions, or launch campaigns.
- Ads and promotion draft CSVs reflect the cost state: they show blocked_by_missing_costs before costs are filled, and add profit/ACOS guardrails after cost inputs are present.
- The Check Amazon Store Readiness button asks the local AI Director whether 10001 is actually usable for store execution. It shows safe internal actions, current blockers, and blocked external actions before the operator touches upload, price, inventory, shipment, promotion, or ads controls.
- The Check Final Upload Gates button shows the final truth table for the 10001 upload candidate: Seller Central template, HTTPS images, Product Identity, PTD schema, inventory visibility, and owner confirmation. It still does not authorize Seller Central submit.
- The Check Amazon Image URLs button validates the Amazon asset base URL and generates the 13 image locators needed by the 10001 single-color and 4-pack upload mapping. It only checks readiness; it does not upload files or prove Amazon fetched the images.
- The Build Image Upload Plan button prepares the local S3/R2-style upload command plan for those 13 images. It reports missing provider environment variables and command previews, but it does not run commands, upload files, or reveal secrets.
- The Verify Uploaded Images button performs a lightweight public fetch check for the 13 image URLs after the files are uploaded to the asset host. It reports HTTP status and content type; it does not upload files, submit feeds, or prove Amazon accepted the images.
- On Amazon listing drafts that already show Ready to submit, the plugin still records submit_allowed=false when the category route is undefined, per-color variant images are incomplete, or owner confirmation is missing. It also flags visible Submit, Publish, Save, Launch campaign, OTP, payment, shipment, refund, or authorization controls. Ready does not mean the agent should submit.
- On Amazon Manage All Inventory / Manage Your Inventory pages, use Backend operation path. The plugin classifies amazon_inventory_inspection, records all listings, complete drafts, active listings, missing-information rows, FBM/FBA signals, old SKU noise such as pet backpack or underwear, and whether a 10001 / T-shirt row is visible.
- On Amazon Manage Orders / orders-v3 / MFN pending pages, use Backend operation path. The plugin classifies amazon_mfn_order_inspection and records pending, unshipped, shipped, cancelled, and zero-order signals; it does not ship, refund, cancel, message buyers, or buy shipping.
- On Amazon FBA dashboard pages, use Backend operation path. The plugin classifies amazon_fba_inventory_inspection and treats FBA as reference-only for the current 10001 plan because the user route is FBM / self-warehouse first.
- On Amazon Ads pages, use Backend operation path to capture Campaign Manager, Sponsored Products form fields, budget fields, targeting fields, and launch boundaries. The plugin captures the form state; it does not save drafts or launch campaigns.
- Store backend captures should auto-scroll to bottom. If page_reached_bottom is false, the AI keeps the task in repair/capture mode instead of assuming the page was fully checked.
- When a pending Amazon store operations gate is pulled, the popup checklist tells the operator to capture Manage All Inventory, Add a Product / Product Identity, Manage Orders / MFN pending, and FBA dashboard before any store action.
- When a pending Amazon Ads gate is pulled, the popup checklist tells the operator to capture Campaign Manager / Sponsored Products fields and Launch campaign visibility, while keeping ad launch blocked.
- When a pending Amazon template download gate is pulled, the popup checklist tells the operator to open Add Products > Spreadsheet / Add products via upload, choose Amazon US Clothing/T-shirt, download the blank template, capture evidence, and let the local watcher generate the mapped 58-row candidate.
- This plugin captures visible page data. It is not Amazon SP-API authorization and it does not submit anything to Seller Central.

Amazon BitBrowser profile practical preflight:
1. Open BitBrowser window 22 named Amazon. If Amazon asks for Two-Step Verification, the owner must pass OTP/WhatsApp/phone verification manually.
2. After Seller Central opens, go to Add a Product / Product Identity / Brand Registry / UPC, GTIN, or Product ID exemption related pages.
3. In the extension choose Amazon listing / Product Identity preflight.
4. Use Store ID amazon-us-new-store, Platform Amazon, Country / Site US, Store Mode marketplace_seller, Ownership self_store, Bit Window BitBrowser-22, IP Region US / Los Angeles, Product 10001 washed T-shirt.
5. Click Capture Current Page, then review the result in /chat?intent=store_data&source=amazon-seller-central&product=10001.
6. Click Pull Store Task Package when the owner has confirmed the matching preflight draft. The task package should be listing_preflight for amazon:US:marketplace_seller and should show the onsite checklist before the next capture.
7. Stop before Save, Publish, Submit approval, Launch campaign, Send OTP, Account Recovery, payment, shipment, refund, or account security changes.
8. If Amazon is still blocked by 2FA, use Send Local Test Capture first. This proves local capture is wired without sending anything to Amazon.
9. If the draft says Ready to submit, still check that itemType/recommendedBrowseNodeId/displayPath are not undefined and that every color variant has images before any owner-approved submit.

Default local server:
http://127.0.0.1:8765

Multi-device usage:
- If every computer runs its own local console, keep the default server URL.
- If multiple devices should send data to one host, change the server URL to that host, for example http://192.168.1.10:8765.
- When using one host, make sure the firewall allows access to port 8765.

Safety:
- The extension only captures visible data, tables, links, buttons, inputs, and optional screenshots.
- It does not log in, submit forms, list products, change prices, join campaigns, launch ads, or delist products.
- Store backend captures include route metadata for ERP isolation. Real publishing, discount creation, campaign signup, ad launch, budget changes, authorization changes, refunds, and shipments still need owner confirmation.
- Do not put plain-text passwords, SMS codes, API secrets, or private credentials in notes."""
