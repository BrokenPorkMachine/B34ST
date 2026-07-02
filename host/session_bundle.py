#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Deterministic physical-integration evidence bundle helpers."""

from __future__ import annotations

import hashlib
import json
import pathlib
import zipfile
from typing import Any

MAX_BUNDLE_FILE = 4 * 1024 * 1024
MAX_BUNDLE_SIZE = 16 * 1024 * 1024
TIMESTAMP = (1980, 1, 1, 0, 0, 0)
STANDARD_FILES = (
    "session.json",
    "summary.json",
    "device.json",
    "profile.json",
    "image-manifest.json",
    "transfer.log",
    "console.log",
    "boot-evidence.json",
    "trace.json",
    "crash-report.json",
)


class SessionBundleError(RuntimeError):
    pass


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _encode(value: Any) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("utf-8")
    return canonical_json(value)


def build_checksums(files: dict[str, bytes]) -> bytes:
    lines = [
        f"{hashlib.sha256(data).hexdigest()}  {name}"
        for name, data in sorted(files.items())
    ]
    return ("\n".join(lines) + "\n").encode("ascii")


def write_session_bundle(path: pathlib.Path, values: dict[str, Any]) -> None:
    files = {
        name: _encode(values.get(name, {} if name.endswith(".json") else ""))
        for name in STANDARD_FILES
    }
    for name, data in files.items():
        if len(data) > MAX_BUNDLE_FILE:
            raise SessionBundleError(f"evidence member exceeds size limit: {name}")
    files["checksums.sha256"] = build_checksums(files)
    total = sum(len(value) for value in files.values())
    if total > MAX_BUNDLE_SIZE:
        raise SessionBundleError("evidence bundle exceeds size limit")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with zipfile.ZipFile(
        temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=9
    ) as bundle:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, TIMESTAMP)
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            bundle.writestr(
                info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9
            )
    temporary.replace(path)


def read_session_bundle(path: pathlib.Path) -> dict[str, bytes]:
    if not path.is_file() or path.stat().st_size > MAX_BUNDLE_SIZE:
        raise SessionBundleError("invalid evidence bundle")
    with zipfile.ZipFile(path) as bundle:
        if bundle.testzip() is not None:
            raise SessionBundleError("evidence bundle CRC failure")
        files: dict[str, bytes] = {}
        for info in bundle.infolist():
            pure = pathlib.PurePosixPath(info.filename)
            if pure.is_absolute() or ".." in pure.parts or len(pure.parts) != 1:
                raise SessionBundleError("unsafe evidence member")
            if info.file_size > MAX_BUNDLE_FILE:
                raise SessionBundleError("evidence member exceeds size limit")
            if info.filename in files:
                raise SessionBundleError("duplicate evidence member")
            files[info.filename] = bundle.read(info)
    return files


def verify_session_bundle(path: pathlib.Path) -> dict[str, object]:
    files = read_session_bundle(path)
    missing = sorted((set(STANDARD_FILES) | {"checksums.sha256"}) - set(files))
    failures: list[str] = []
    expected: dict[str, str] = {}
    for line in (
        files.get("checksums.sha256", b"").decode("ascii", "strict").splitlines()
    ):
        digest, sep, name = line.partition("  ")
        if not sep or len(digest) != 64:
            failures.append("invalid checksum line")
            continue
        expected[name] = digest
    for name in STANDARD_FILES:
        if (
            name in files
            and expected.get(name) != hashlib.sha256(files[name]).hexdigest()
        ):
            failures.append(name)
    return {
        "valid": not missing and not failures,
        "missing": missing,
        "checksum_failures": failures,
        "members": sorted(files),
    }
