from __future__ import annotations

import hashlib
from pathlib import Path


DESKTOP_RUNTIME_VERSION = 4
BACKEND_SOURCE_FILES = (
    "ai_ecommerce_director/company_workspace.py",
    "ai_ecommerce_director/desktop_workspace.py",
    "ai_ecommerce_director/floating_ai_widget.py",
    "ai_ecommerce_director/server.py",
)


def backend_source_signature(root: Path) -> str:
    digest = hashlib.sha256()
    for relative_path in sorted(BACKEND_SOURCE_FILES):
        normalized_path = relative_path.replace("\\", "/")
        digest.update(normalized_path.encode("utf-8"))
        digest.update(b"\0")
        try:
            digest.update((root / Path(relative_path)).read_bytes())
        except OSError:
            digest.update(b"<missing>")
        digest.update(b"\0")
    return digest.hexdigest()[:24]
