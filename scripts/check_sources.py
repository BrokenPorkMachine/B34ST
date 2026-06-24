#!/usr/bin/env python3
"""Validate Python and POSIX-shell source syntax without creating caches."""

from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {
    "build", "build-generic", "build-integration", "build-apple", "runtime-artifacts",
    "__pycache__", ".git",
}


def main() -> int:
    failures: list[str] = []
    python_files = [
        path for path in ROOT.rglob("*.py")
        if not any(part in EXCLUDED_PARTS for part in path.relative_to(ROOT).parts)
        and not path.is_relative_to(ROOT / "sdk" / "templates")
    ]
    for path in sorted(python_files):
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except (OSError, SyntaxError, UnicodeError) as exc:
            failures.append(f"{path.relative_to(ROOT)}: {exc}")

    shell_files = [ROOT / "fbr34ker"]
    shell_files.extend(sorted((ROOT / "scripts").glob("*.sh")))
    shell_files.extend([ROOT / "host/fbr34kctl", ROOT / "host/forgectl",
                        ROOT / "host/fbr34kdeploy",
                        ROOT / "host/fbr34kdeploy-target",
                        ROOT / "host/fbr34kbootimg", ROOT / "host/fbr34kirecovery",
                        ROOT / "host/fbr34kbringup", ROOT / "host/fbr34kdevice",
                        ROOT / "host/fbr34kbridge", ROOT / "host/fbr34ksession",
                        ROOT / "host/fbr34khardware"])
    for path in shell_files:
        completed = subprocess.run(
            ["sh", "-n", str(path)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if completed.returncode != 0:
            failures.append(
                f"{path.relative_to(ROOT)}: {completed.stdout.strip()}"
            )

    if failures:
        print("source syntax validation failed", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(f"source syntax validation passed ({len(python_files)} Python files, "
          f"{len(shell_files)} shell files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
