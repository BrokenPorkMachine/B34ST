"""Acquisition evidence bundle reporting.

# SPDX-License-Identifier: BSD-2-Clause
Generates deterministic ZIP-based evidence bundles from acquisition
results, with SHA-256 checksums and chain-of-custody logs.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import zipfile
from typing import Any

from host.forensics.acquisition import AcquisitionSession


class ReportError(RuntimeError):
    pass


MAX_BUNDLE_FILE = 4 * 1024 * 1024
MAX_BUNDLE_SIZE = 32 * 1024 * 1024
TIMESTAMP = (1980, 1, 1, 0, 0, 0)
STANDARD_FILES = (
    "acquisition-summary.json",
    "chain-of-custody.json",
    "session.json",
    "target.json",
)


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def build_checksums(files: dict[str, bytes]) -> bytes:
    lines = [
        f"{hashlib.sha256(data).hexdigest()}  {name}"
        for name, data in sorted(files.items())
    ]
    return ("\n".join(lines) + "\n").encode("ascii")


class AcquisitionReport:
    """Generates evidence bundles from acquisition sessions."""

    def __init__(self, session: AcquisitionSession):
        self.session = session

    def build_bundle(self, output_path: pathlib.Path) -> dict[str, Any]:
        if not self.session._finalized:
            raise ReportError(
                "acquisition session must be finalized before building report"
            )

        files: dict[str, bytes] = {
            "acquisition-summary.json": canonical_json(self.session.summary()),
            "chain-of-custody.json": self.session.custody.export_json().encode("utf-8"),
            "session.json": canonical_json({
                "started_at": self.session.started_at,
                "operator": self.session.target.operator,
                "device_id": self.session.target.device_id,
                "profile": self.session.profile.name,
                "result_count": len(self.session.results),
            }),
            "target.json": canonical_json({
                "device_id": self.session.target.device_id,
                "product": self.session.target.product,
                "model": self.session.target.model,
                "ios_version": self.session.target.ios_version,
                "ecid": self.session.target.ecid,
                "chipset": self.session.target.chipset,
                "mode": self.session.target.mode,
            }),
        }

        for name, data in list(files.items()):
            if len(data) > MAX_BUNDLE_FILE:
                raise ReportError(
                    f"report member exceeds size limit: {name} ({len(data)} bytes)"
                )

        files["checksums.sha256"] = build_checksums(files)

        total = sum(len(v) for v in files.values())
        if total > MAX_BUNDLE_SIZE:
            raise ReportError(
                f"report bundle exceeds size limit: {total} bytes"
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = output_path.with_suffix(output_path.suffix + ".tmp")

        with zipfile.ZipFile(
            temp_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9
        ) as bundle:
            for name, data in sorted(files.items()):
                info = zipfile.ZipInfo(name, TIMESTAMP)
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                bundle.writestr(
                    info, data,
                    compress_type=zipfile.ZIP_DEFLATED,
                    compresslevel=9,
                )

        temp_path.replace(output_path)

        bundle_hash = hashlib.sha256(output_path.read_bytes()).hexdigest()

        return {
            "report_path": str(output_path),
            "bundle_sha256": bundle_hash,
            "member_count": len(files),
            "total_bytes": total,
        }

    @staticmethod
    def verify_bundle(path: pathlib.Path) -> dict[str, Any]:
        if not path.is_file() or path.stat().st_size > MAX_BUNDLE_SIZE:
            raise ReportError("invalid report bundle")

        with zipfile.ZipFile(path) as bundle:
            if bundle.testzip() is not None:
                raise ReportError("report bundle CRC failure")

            files: dict[str, bytes] = {}
            for info in bundle.infolist():
                pure = pathlib.PurePosixPath(info.filename)
                if pure.is_absolute() or ".." in pure.parts or len(pure.parts) != 1:
                    raise ReportError(f"unsafe member: {info.filename}")
                if info.file_size > MAX_BUNDLE_FILE:
                    raise ReportError(
                        f"member exceeds size limit: {info.filename}"
                    )
                if info.filename in files:
                    raise ReportError(f"duplicate member: {info.filename}")
                files[info.filename] = bundle.read(info)

        missing = sorted(set(STANDARD_FILES) - set(files))
        failures: list[str] = []
        expected: dict[str, str] = {}

        for line in files.get("checksums.sha256", b"").decode(
            "ascii", "strict"
        ).splitlines():
            digest, sep, name = line.partition("  ")
            if not sep or len(digest) != 64:
                failures.append("invalid checksum line")
                continue
            expected[name] = digest

        for name in STANDARD_FILES:
            if name in files and expected.get(name) != hashlib.sha256(
                files[name]
            ).hexdigest():
                failures.append(name)

        return {
            "valid": not missing and not failures,
            "missing": missing,
            "checksum_failures": failures,
            "members": sorted(files),
            "bundle_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
