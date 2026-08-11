"""Run the same lint, format, and test checks used by continuous integration."""

from __future__ import annotations

import subprocess
import sys


def run(*arguments: str) -> None:
    command = [sys.executable, "-m", *arguments]
    print(f"\n> {' '.join(command)}", flush=True)
    subprocess.run(command, check=True)


def main() -> None:
    run("ruff", "check", "app", "tests", "scripts")
    run("ruff", "format", "app", "tests", "scripts", "--check")
    run("pytest", "--cov=app", "--cov-report=term-missing")


if __name__ == "__main__":
    main()
