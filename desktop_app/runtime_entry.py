from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="T One bundled local runtime")
    subparsers = parser.add_subparsers(dest="mode", required=True)

    server_parser = subparsers.add_parser("server")
    server_parser.add_argument("--root", required=True)
    server_parser.add_argument("--port", type=int, default=8767)

    bridge_parser = subparsers.add_parser("bridge")
    bridge_parser.add_argument("--root", required=True)

    harness_parser = subparsers.add_parser("harness-mcp")
    harness_parser.add_argument("--root", required=True)

    cli_parser = subparsers.add_parser("cli")
    cli_parser.add_argument("--root", required=True)
    cli_parser.add_argument("cli_args", nargs=argparse.REMAINDER)

    args = parser.parse_args()
    root = Path(args.root).resolve()
    root.mkdir(parents=True, exist_ok=True)

    if args.mode == "server":
        from ai_ecommerce_director.server import run_server

        run_server(root, host="127.0.0.1", port=int(args.port))
        return 0

    if args.mode == "cli":
        from ai_ecommerce_director.tone_cli import main as cli_main

        cli_arguments = list(args.cli_args)
        if cli_arguments and cli_arguments[0] == "--":
            cli_arguments = cli_arguments[1:]
        return cli_main(["--root", str(root), *cli_arguments])

    if args.mode == "harness-mcp":
        from ai_ecommerce_director.deepseek_harness_runtime import main_mcp

        return main_mcp(["--root", str(root)])

    from desktop_app.bridge import run

    return run(root)


if __name__ == "__main__":
    raise SystemExit(main())
