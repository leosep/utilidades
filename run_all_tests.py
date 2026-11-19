"""Run the tests of the five projects on Windows, macOS or Linux.

    python run_all_tests.py

On Linux without a display, the GUI tests are wrapped with xvfb-run when it is installed.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYTHON_PROJECTS = ("01-billcutter", "02-vault", "04-finance", "05-branchchat")


def main() -> int:
    command = [sys.executable, "-m", "unittest", "discover", "-s", "tests"]
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY") and shutil.which("xvfb-run"):
        command = ["xvfb-run", "-a", *command]

    for project in PYTHON_PROJECTS:
        print(f"== {project}")
        result = subprocess.run(command, cwd=ROOT / project)
        if result.returncode:
            return result.returncode

    print("== 03-photo-cleaner")
    return subprocess.run(["node", "tests/exif.test.js"], cwd=ROOT / "03-photo-cleaner").returncode


if __name__ == "__main__":
    raise SystemExit(main())
