from __future__ import annotations

import argparse
import os
import signal
import sys
from pathlib import Path


def _application_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the bundled local T-one business service.")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--desktop-token", default="")
    args = parser.parse_args()

    if not 1024 <= args.port <= 65535:
        raise ValueError("Local service port must be between 1024 and 65535.")
    runtime_root = args.root.expanduser().resolve()
    runtime_root.mkdir(parents=True, exist_ok=True)
    if args.desktop_token:
        os.environ["TEELAB_DESKTOP_AUTH_TOKEN"] = args.desktop_token

    source_root = _application_root()
    if str(source_root) not in sys.path:
        sys.path.insert(0, str(source_root))

    from ai_ecommerce_director.server import run_server

    # Windows terminates the child process when Electron exits. On platforms
    # where SIGTERM is delivered, keep the default termination semantics.
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
    run_server(runtime_root, host="127.0.0.1", port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
