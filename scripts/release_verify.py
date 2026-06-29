#!/usr/bin/env python3
"""Verify a FBR34KER release manifest, artifact hashes, and optional signature."""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys

MAX_MANIFEST = 2 * 1024 * 1024


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_relative(value: object) -> pathlib.PurePosixPath:
    if not isinstance(value, str):
        raise ValueError("artifact path must be a string")
    path = pathlib.PurePosixPath(value)
    if (
        path.is_absolute()
        or not path.parts
        or ".." in path.parts
        or "\\" in value
    ):
        raise ValueError(f"unsafe artifact path: {value}")
    return path


def verify_signature(
    manifest: pathlib.Path,
    signature: pathlib.Path,
    public_key: pathlib.Path,
) -> bool:
    try:
        minisign_signature = signature.read_bytes().startswith(b"untrusted comment:")
    except OSError:
        return False
    if minisign_signature:
        minisign = shutil.which("minisign")
        if minisign is None:
            return False
        command = [
            minisign,
            "-V",
            "-p", str(public_key),
            "-m", str(manifest),
            "-x", str(signature),
        ]
    else:
        openssl = shutil.which("openssl")
        if openssl is None:
            return False
        # Keep this exactly aligned with scripts/sign_manifest.sh.
        command = [
            openssl,
            "dgst",
            "-sha256",
            "-verify", str(public_key),
            "-signature", str(signature),
            str(manifest),
        ]
    return subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    ).returncode == 0

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=pathlib.Path)
    parser.add_argument("--root", type=pathlib.Path)
    parser.add_argument("--signature", type=pathlib.Path)
    parser.add_argument("--public-key", type=pathlib.Path)
    parser.add_argument("--json", action="store_true")
    arguments = parser.parse_args(argv)
    errors: list[str] = []
    try:
        if arguments.manifest.stat().st_size > MAX_MANIFEST:
            raise ValueError("manifest exceeds 2 MiB")
        data = json.loads(arguments.manifest.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("release manifest must be a JSON object")
        if data.get("schema_version") not in {1, 2}:
            raise ValueError("unsupported release manifest schema")
        root = (arguments.root or arguments.manifest.parent).resolve()
        artifacts = data.get("artifacts")
        if not isinstance(artifacts, list) or len(artifacts) > 512:
            raise ValueError("invalid artifact list")
        seen: set[str] = set()
        for record in artifacts:
            if not isinstance(record, dict):
                errors.append("artifact record is not an object")
                continue
            try:
                relative = safe_relative(record.get("path")).as_posix()
            except ValueError as exc:
                errors.append(str(exc))
                continue
            if relative in seen:
                errors.append(f"duplicate artifact: {relative}")
                continue
            seen.add(relative)
            path = (root / relative).resolve()
            try:
                path.relative_to(root)
            except ValueError:
                errors.append(f"artifact escapes root: {relative}")
                continue
            if not path.is_file():
                errors.append(f"missing artifact: {relative}")
                continue
            if path.stat().st_size != record.get("size"):
                errors.append(f"size mismatch: {relative}")
            if sha256(path) != record.get("sha256"):
                errors.append(f"hash mismatch: {relative}")
        if bool(arguments.signature) != bool(arguments.public_key):
            errors.append("signature and public key must be supplied together")
        elif arguments.signature and not verify_signature(
            arguments.manifest, arguments.signature, arguments.public_key
        ):
            errors.append("signature verification failed")
        result = {
            "passed": not errors,
            "version": data.get("version"),
            "artifacts_checked": len(artifacts),
            "signature_checked": bool(arguments.signature),
            "errors": errors,
        }
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result = {
            "passed": False,
            "artifacts_checked": 0,
            "signature_checked": False,
            "errors": [str(exc)],
        }
    if arguments.json:
        print(json.dumps(result, sort_keys=True))
    elif result["passed"]:
        print(
            f"release verification passed ({result['artifacts_checked']} artifacts)"
        )
    else:
        for error in result["errors"]:
            print(f"VERIFY ERROR: {error}", file=sys.stderr)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
