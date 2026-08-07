from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WindowsOneClickTest(unittest.TestCase):
    def test_public_demo_uses_an_inline_favicon(self) -> None:
        html = (ROOT / "demo" / "chat-first-workspace.html").read_text(encoding="utf-8")
        self.assertIn('rel="icon"', html)
        self.assertIn("data:image/svg+xml", html)

    def test_clean_copy_can_verify_public_demo_without_installing_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            clean_root = Path(temp_dir) / "T-one"
            shutil.copytree(
                ROOT,
                clean_root,
                ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", "*.pyc"),
            )
            launcher = clean_root / "START.cmd"
            self.assertTrue(launcher.is_file(), "public release is missing START.cmd")

            before = sorted(
                path.relative_to(clean_root).as_posix()
                for path in clean_root.rglob("*")
                if path.is_file()
            )
            result = subprocess.run(
                ["cmd.exe", "/d", "/c", str(launcher), "--verify-only"],
                cwd=clean_root,
                text=True,
                capture_output=True,
                timeout=15,
                check=False,
            )
            after = sorted(
                path.relative_to(clean_root).as_posix()
                for path in clean_root.rglob("*")
                if path.is_file()
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("PUBLIC_DEMO_READY", result.stdout)
            self.assertIn("offline demo", result.stdout.lower())
            self.assertIn("no live store connections", result.stdout.lower())
            self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
