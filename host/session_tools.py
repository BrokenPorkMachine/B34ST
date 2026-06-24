#!/usr/bin/env python3
"""Inspect and replay deterministic FBR34KER hardware-integration sessions."""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from session_bundle import SessionBundleError, read_session_bundle, verify_session_bundle


def json_member(files: dict[str, bytes], name: str):
    try:
        return json.loads(files[name].decode("utf-8"))
    except (KeyError, UnicodeError, json.JSONDecodeError) as exc:
        raise SessionBundleError(f"invalid {name}") from exc


def inspect_session(path: pathlib.Path) -> int:
    files = read_session_bundle(path)
    result = verify_session_bundle(path)
    session = json_member(files, "session.json")
    result.update({"session": session})
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


def replay_session(path: pathlib.Path, *, console_only: bool = False) -> int:
    files = read_session_bundle(path)
    if not console_only:
        session = json_member(files, "session.json")
        print(f"FBR34KER session {session.get('session_id', 'unknown')}")
        print(f"profile={session.get('profile_id')} passed={session.get('passed')}")
        for stage in session.get("stages", []):
            if isinstance(stage, dict):
                print(f"[{stage.get('status', 'unknown')}] {stage.get('stage', 'unknown')}")
        print("--- console ---")
    sys.stdout.write(files.get("console.log", b"").decode("utf-8", "replace"))
    return 0


def crash_decode(path: pathlib.Path) -> int:
    files = read_session_bundle(path) if path.suffix == ".zip" else None
    value = json_member(files, "crash-report.json") if files is not None else json.loads(path.read_text())
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


def trace_timeline(path: pathlib.Path) -> int:
    files = read_session_bundle(path) if path.suffix == ".zip" else None
    value = json_member(files, "trace.json") if files is not None else json.loads(path.read_text())
    records = value.get("records", value if isinstance(value, list) else [])
    for index, record in enumerate(records):
        if isinstance(record, dict):
            print(f"{index:04d} {record.get('operation', record.get('event', 'unknown'))}: {record.get('status', '')} {record.get('detail', '')}".rstrip())
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser("inspect"); inspect.add_argument("bundle", type=pathlib.Path)
    replay = sub.add_parser("replay"); replay.add_argument("bundle", type=pathlib.Path); replay.add_argument("--console-only", action="store_true")
    crash = sub.add_parser("crash-decode"); crash.add_argument("input", type=pathlib.Path)
    trace = sub.add_parser("trace-timeline"); trace.add_argument("input", type=pathlib.Path)
    return root


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "inspect": return inspect_session(args.bundle)
        if args.command == "replay": return replay_session(args.bundle, console_only=args.console_only)
        if args.command == "crash-decode": return crash_decode(args.input)
        return trace_timeline(args.input)
    except (OSError, ValueError, json.JSONDecodeError, SessionBundleError) as exc:
        print(f"session error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
