from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ai_ecommerce_director.server import run_server


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("port", nargs="?", type=int, default=8765)
    parser.add_argument("--root", default=os.environ.get("TEELAB_AGENT_ROOT", str(ROOT)))
    args = parser.parse_args()
    run_server(Path(args.root).resolve(), host="127.0.0.1", port=args.port)
