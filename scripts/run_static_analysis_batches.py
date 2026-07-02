#!/usr/bin/env python3

"""Run Clang analysis in small fresh-process batches for host reliability."""
# SPDX-License-Identifier: BSD-2-Clause
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", default="clang")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--source-id", default="analysis")
    parser.add_argument("--include-dir", action="append", default=[])
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("sources", nargs="+")
    args = parser.parse_args()
    if args.batch_size <= 0:
        parser.error("--batch-size must be positive")
    batches = [args.sources[i:i + args.batch_size]
               for i in range(0, len(args.sources), args.batch_size)]
    for index, batch in enumerate(batches, 1):
        print(f"[analysis-batch {index:02d}/{len(batches):02d}]", flush=True)
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_static_analysis.py"),
            "--clang", args.clang,
            "--timeout", str(args.timeout),
            "--source-id", args.source_id,
        ]
        for include in args.include_dir:
            command.extend(("--include-dir", include))
        command.extend(batch)
        completed = subprocess.run(command, cwd=ROOT, check=False)
        if completed.returncode != 0:
            return completed.returncode
    print(f"batched static analysis passed ({len(args.sources)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
