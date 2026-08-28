"""Compressed, content-addressed storage for optional T One Skill packages."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
import threading
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen


CATALOG_PATH = Path("config") / "skill_package_catalog.json"
STATE_PATH = Path("data") / "skill_package_store.json"
CACHE_PATH = Path("data") / "skill_package_cache" / "sha256"
MAX_PACKAGE_BYTES = 64 * 1024 * 1024
SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,119}$")
SHA256 = re.compile(r"^[a-f0-9]{64}$")
_LOCK = threading.RLock()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        raise ValueError(f"Skill package metadata is not readable: {path.name}") from exc
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _catalog(root: Path) -> dict[str, dict[str, Any]]:
    raw = _read_json(root / CATALOG_PATH)
    result: dict[str, dict[str, Any]] = {}
    for item in raw.get("packages", []):
        if not isinstance(item, dict):
            continue
        skill_id = str(item.get("id") or "").strip().lower()
        digest = str(item.get("sha256") or "").strip().lower()
        if not SAFE_ID.fullmatch(skill_id) or not SHA256.fullmatch(digest):
            continue
        if not str(item.get("license") or "").strip() or not str(
            item.get("pinned_ref") or ""
        ).strip():
            continue
        result[skill_id] = {
            "id": skill_id,
            "name": str(item.get("name") or skill_id).strip(),
            "version": str(item.get("version") or "").strip(),
            "download_url": str(item.get("download_url") or "").strip(),
            "sha256": digest,
            "size_bytes": max(0, int(item.get("size_bytes") or 0)),
            "license": str(item.get("license") or "").strip(),
            "pinned_ref": str(item.get("pinned_ref") or "").strip(),
            "auto_download_allowed": item.get("auto_download_allowed") is True,
            "archive_type": "zip",
        }
    return result


def _state(root: Path) -> dict[str, Any]:
    payload = _read_json(root / STATE_PATH)
    references = payload.get("project_references")
    return {
        "schema_version": 1,
        "project_references": references if isinstance(references, dict) else {},
    }


def _cached_path(root: Path, digest: str) -> Path:
    return root / CACHE_PATH / f"{digest}.zip"


def _verified_cached_package(root: Path, record: dict[str, Any]) -> Path | None:
    path = _cached_path(root, str(record["sha256"]))
    if not path.is_file():
        return None
    if path.stat().st_size > MAX_PACKAGE_BYTES:
        return None
    if sha256(path.read_bytes()).hexdigest() != record["sha256"]:
        return None
    return path


def skill_package_store_snapshot(root: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    catalog = _catalog(root)
    state = _state(root)
    packages = []
    cached_bytes = 0
    referenced_ids = {
        str(skill_id)
        for values in state["project_references"].values()
        if isinstance(values, list)
        for skill_id in values
    }
    for skill_id, record in sorted(catalog.items()):
        cached = _verified_cached_package(root, record)
        cached_bytes += cached.stat().st_size if cached else 0
        packages.append(
            {
                **record,
                "cached": cached is not None,
                "installed_project_count": sum(
                    1
                    for values in state["project_references"].values()
                    if isinstance(values, list) and skill_id in values
                ),
            }
        )
    manifest_paths = [
        root / CATALOG_PATH,
        root / "config" / "commerce_skill_registry.json",
    ]
    package_catalog_bytes = (
        (root / CATALOG_PATH).stat().st_size if (root / CATALOG_PATH).is_file() else 0
    )
    catalog_bytes = sum(path.stat().st_size for path in manifest_paths if path.is_file())
    return {
        "ok": True,
        "storage_mode": "manifest_only_until_selected_then_shared_compressed_cas",
        "packages": packages,
        "catalog_bytes": catalog_bytes,
        "package_catalog_bytes": package_catalog_bytes,
        "cached_bytes": cached_bytes,
        "cached_package_count": sum(1 for item in packages if item["cached"]),
        "referenced_package_count": len(referenced_ids),
        "project_copy_count": 0,
        "cache_path": str((root / CACHE_PATH).resolve()),
        "truth": {
            "uninstalled_package_bytes": 0,
            "automatic_download_requires_verified_manifest": True,
            "license_and_pinned_ref_required": True,
            "external_download_performed": False,
        },
    }


def _download_verified(record: dict[str, Any], destination: Path) -> None:
    parsed = urlparse(str(record.get("download_url") or ""))
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("Skill automatic download requires a pinned HTTPS package URL.")
    request = Request(
        str(record["download_url"]),
        headers={"User-Agent": "T-One-Skill-Package/1.0"},
    )
    digest = sha256()
    written = 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(request, timeout=30) as response, destination.open("wb") as handle:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            written += len(chunk)
            if written > MAX_PACKAGE_BYTES:
                raise ValueError("Skill package exceeds the 64 MiB download limit.")
            digest.update(chunk)
            handle.write(chunk)
    if digest.hexdigest() != record["sha256"]:
        raise ValueError("Skill package checksum does not match the pinned manifest.")


def install_project_skill_package(
    root: Path, project_id: str, skill_id: str, *, allow_download: bool
) -> dict[str, Any]:
    """Reference one compressed package from a project, downloading once if allowed."""

    root = Path(root).resolve()
    project_id = str(project_id or "").strip().lower()
    skill_id = str(skill_id or "").strip().lower()
    if not SAFE_ID.fullmatch(project_id) or not SAFE_ID.fullmatch(skill_id):
        raise ValueError("Project or Skill identifier is invalid.")
    catalog = _catalog(root)
    record = catalog.get(skill_id)
    if record is None:
        return {
            "ok": True,
            "skill_id": skill_id,
            "state": "builtin_manifest_no_download_required",
            "downloaded": False,
            "project_copy_count": 0,
        }
    cached = _verified_cached_package(root, record)
    downloaded = False
    if cached is None:
        if not allow_download or not record["auto_download_allowed"]:
            return {
                "ok": True,
                "skill_id": skill_id,
                "state": "download_required",
                "downloaded": False,
                "project_copy_count": 0,
            }
        temporary = _cached_path(root, record["sha256"]).with_suffix(".zip.download")
        try:
            _download_verified(record, temporary)
            destination = _cached_path(root, record["sha256"])
            temporary.replace(destination)
            cached = destination
            downloaded = True
        finally:
            if temporary.exists():
                temporary.unlink()
    with _LOCK:
        state = _state(root)
        references = state["project_references"]
        current = [
            str(item)
            for item in references.get(project_id, [])
            if SAFE_ID.fullmatch(str(item))
        ]
        if skill_id not in current:
            current.append(skill_id)
        references[project_id] = current
        _write_json(root / STATE_PATH, state)
    return {
        "ok": True,
        "skill_id": skill_id,
        "state": "installed_shared_compressed_reference",
        "downloaded": downloaded,
        "cache_path": str(cached or ""),
        "project_copy_count": 0,
    }
