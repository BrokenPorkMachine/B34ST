#!/usr/bin/env python3
"""Create deterministic FBR34KER artifact and checksum manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib


def hash_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_role(path: pathlib.Path) -> str:
    name = path.name
    if "physical-integration-simulation" in path.parts:
        if name == "simulation-summary.json":
            return "physical-integration-simulation-report"
        if name.endswith("session.zip"):
            return "physical-integration-session-bundle"
        return "physical-integration-simulation-artifact"
    if "bringup-simulation" in path.parts:
        if name == "simulation-summary.json":
            return "hardware-bringup-simulation-report"
        if name.endswith("evidence.zip"):
            return "hardware-bringup-evidence-bundle"
        return "hardware-bringup-simulation-artifact"
    if "build-apple" in path.parts:
        if name == "boot.img":
            return "apple-recovery-boot-bundle"
        if name == "boot.raw":
            return "apple-recovery-raw-payload"
        if name.endswith(".json"):
            return "apple-recovery-image-metadata"
        return "apple-recovery-artifact"
    if "deployment-simulation" in path.parts:
        if name == "simulation-summary.json":
            return "deployment-simulation-report"
        if name == "evidence.zip":
            return "deployment-evidence-bundle"
        return "deployment-simulation-artifact"
    if "loader-simulation" in path.parts:
        if name == "handoff-v4.fbhb":
            return "binary-handoff-container"
        if name == "sdk-conformance.json":
            return "sdk-conformance-report"
        if name == "handoff-v4.bin":
            return "packed-handoff-structure"
        if name == "loader-conformance.json":
            return "loader-conformance-report"
        if name == "normalized-handoff.json":
            return "normalized-handoff-design"
        if name == "sparse-memory.json":
            return "sparse-memory-plan"
        return "loader-simulation-artifact"
    if name.endswith(".bin"):
        return "raw-monitor-image"
    if name.endswith(".elf"):
        return "debug-elf"
    if name.endswith(".map"):
        return "linker-map"
    if name.endswith(".fmod"):
        return "fmod-module"
    if name.endswith(".a"):
        return "loader-sdk-static-library"
    if name.endswith(".zip"):
        return "release-archive"
    return "artifact"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--release-name", required=True)
    parser.add_argument("--channel", required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--checksums", type=pathlib.Path, required=True)
    parser.add_argument("artifacts", nargs="+", type=pathlib.Path)
    arguments = parser.parse_args(argv)

    root = pathlib.Path.cwd().resolve()
    records: list[dict[str, object]] = []
    seen: set[str] = set()
    for raw_path in arguments.artifacts:
        path = raw_path.resolve()
        if not path.is_file():
            parser.error(f"artifact does not exist: {raw_path}")
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError:
            parser.error(f"artifact is outside project root: {raw_path}")
        if relative in seen:
            parser.error(f"duplicate artifact: {relative}")
        seen.add(relative)
        records.append({
            "path": relative,
            "role": artifact_role(path),
            "size": path.stat().st_size,
            "sha256": hash_file(path),
        })
    records.sort(key=lambda item: str(item["path"]))

    manifest = {
        "schema_version": 2,
        "project": "FBR34KER",
        "version": arguments.version,
        "channel": arguments.channel,
        "release_name": arguments.release_name,
        "source_id": arguments.source_id,
        "artifacts": records,
    }
    arguments.output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest_record = {
        "path": arguments.output.resolve().relative_to(root).as_posix(),
        "sha256": hash_file(arguments.output),
    }
    checksum_rows = [
        f"{record['sha256']}  {record['path']}" for record in records
    ]
    checksum_rows.append(f"{manifest_record['sha256']}  {manifest_record['path']}")
    arguments.checksums.write_text("\n".join(checksum_rows) + "\n", encoding="utf-8")
    print(arguments.output)
    print(arguments.checksums)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
