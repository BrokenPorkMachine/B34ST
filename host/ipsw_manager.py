#!/usr/bin/env python3
"""Targeted IPSW discovery, download, verification, and restore orchestration."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import plistlib
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import zipfile
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = "https://api.ipsw.me/v4/device/{product}?type=ipsw"
MAX_CATALOG_SIZE = 8 * 1024 * 1024
MAX_ADAPTER_OUTPUT = 1024 * 1024
OWNER_ACK = "I OWN OR AM AUTHORIZED TO RESTORE THIS DEVICE"
UPGRADE_ACK = "START SIGNED IPSW RESTORE"
DOWNGRADE_ACK = "START TETHERED DOWNGRADE"


class IPSWError(RuntimeError):
    pass


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json_source(source: str, *, timeout: float) -> Any:
    path = pathlib.Path(source).expanduser()
    if path.is_file():
        data = path.read_bytes()
    else:
        parsed = urllib.parse.urlparse(source)
        if parsed.scheme not in {"http", "https"}:
            raise IPSWError(f"firmware catalog file does not exist: {path}")
        request = urllib.request.Request(
            source,
            headers={"User-Agent": "B34ST/0.3.0 IPSW catalog client"},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = response.read(MAX_CATALOG_SIZE + 1)
        except OSError as exc:
            raise IPSWError(f"unable to read firmware catalog: {exc}") from exc
    if len(data) > MAX_CATALOG_SIZE:
        raise IPSWError("firmware catalog exceeds size limit")
    try:
        return json.loads(data)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise IPSWError(f"invalid firmware catalog JSON: {exc}") from exc


def _apple_firmware_url(value: str) -> str:
    parsed = urllib.parse.urlparse(value)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https":
        raise IPSWError("IPSW URL must use HTTPS")
    if not (
        host == "apple.com"
        or host.endswith(".apple.com")
        or host == "cdn-apple.com"
        or host.endswith(".cdn-apple.com")
    ):
        raise IPSWError(f"IPSW URL is not hosted on an Apple domain: {host}")
    if not parsed.path.lower().endswith(".ipsw"):
        raise IPSWError("firmware URL does not point to an IPSW archive")
    return value


def normalize_catalog(value: Any, product: str) -> dict[str, Any]:
    records = value.get("firmwares") if isinstance(value, dict) else value
    if not isinstance(records, list):
        raise IPSWError("firmware catalog does not contain a firmware list")
    normalized = []
    for record in records:
        if not isinstance(record, dict):
            continue
        identifier = str(record.get("identifier") or product)
        if identifier != product:
            continue
        version = record.get("version")
        build = record.get("buildid") or record.get("build")
        url = record.get("url")
        signed = record.get("signed")
        if (
            not isinstance(version, str)
            or not version
            or not isinstance(build, str)
            or not build
            or not isinstance(url, str)
            or not isinstance(signed, bool)
        ):
            continue
        normalized.append({
            "product": product,
            "version": version,
            "build": build,
            "signed": signed,
            "url": _apple_firmware_url(url),
            "sha1": record.get("sha1sum") or record.get("sha1"),
            "released": record.get("releasedate") or record.get("date"),
            "filename": pathlib.PurePosixPath(urllib.parse.urlparse(url).path).name,
        })
    if not normalized:
        raise IPSWError(f"catalog contains no usable IPSWs for {product}")
    return {
        "schema_version": 1,
        "product": product,
        "firmwares": normalized,
    }


def fetch_catalog(product: str, source: str, timeout: float) -> dict[str, Any]:
    resolved = source.format(product=urllib.parse.quote(product, safe=","))
    return normalize_catalog(_read_json_source(resolved, timeout=timeout), product)


def select_firmware(
    catalog: dict[str, Any],
    *,
    version: str | None,
    build: str | None,
    signed_only: bool,
) -> dict[str, Any]:
    matches = []
    for record in catalog["firmwares"]:
        if version and record["version"] != version:
            continue
        if build and record["build"] != build:
            continue
        if signed_only and not record["signed"]:
            continue
        matches.append(record)
    if not matches:
        qualifier = version or build or "requested criteria"
        raise IPSWError(f"no firmware matches {qualifier}")
    if len(matches) > 1:
        raise IPSWError("firmware selection is ambiguous; specify --version or --build")
    return dict(matches[0])


def download_firmware(record: dict[str, Any], output_dir: pathlib.Path) -> pathlib.Path:
    curl = shutil.which("curl")
    if curl is None:
        raise IPSWError("curl is required for resumable IPSW downloads")
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / record["filename"]
    command = [
        curl,
        "--fail",
        "--location",
        "--continue-at",
        "-",
        "--retry",
        "4",
        "--retry-all-errors",
        "--output",
        str(output),
        record["url"],
    ]
    result = subprocess.run(command, cwd=ROOT, check=False)
    if result.returncode != 0:
        raise IPSWError(f"IPSW download failed with exit code {result.returncode}")
    return output


def inspect_ipsw(path: pathlib.Path) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size <= 0:
        raise IPSWError(f"invalid IPSW path: {path}")
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            restore = (
                plistlib.loads(archive.read("Restore.plist"))
                if "Restore.plist" in names else {}
            )
            manifest = (
                plistlib.loads(archive.read("BuildManifest.plist"))
                if "BuildManifest.plist" in names else {}
            )
    except (zipfile.BadZipFile, KeyError, plistlib.InvalidFileException) as exc:
        raise IPSWError(f"invalid IPSW archive: {exc}") from exc
    products = manifest.get("SupportedProductTypes") or restore.get("SupportedProductTypes") or []
    if not isinstance(products, list):
        products = []
    version = restore.get("ProductVersion") or manifest.get("ProductVersion")
    build = restore.get("ProductBuildVersion") or manifest.get("ProductBuildVersion")
    return {
        "path": str(path.resolve()),
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
        "product_version": str(version) if version else None,
        "product_build": str(build) if build else None,
        "supported_products": sorted(str(item) for item in products),
        "has_build_manifest": bool(manifest),
        "has_restore_plist": bool(restore),
    }


def verify_target(info: dict[str, Any], product: str) -> None:
    products = info["supported_products"]
    if products and product not in products:
        raise IPSWError(f"IPSW does not support target product {product}")
    if not info["has_build_manifest"]:
        raise IPSWError("IPSW does not contain BuildManifest.plist")


def _write_json(path: pathlib.Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def catalog_command(args: argparse.Namespace) -> int:
    value = fetch_catalog(args.product, args.catalog, args.timeout)
    if args.signed_only:
        value["firmwares"] = [item for item in value["firmwares"] if item["signed"]]
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


def download_command(args: argparse.Namespace) -> int:
    catalog = fetch_catalog(args.product, args.catalog, args.timeout)
    record = select_firmware(
        catalog,
        version=args.version,
        build=args.build,
        signed_only=args.signed_only,
    )
    output = download_firmware(record, args.output_dir)
    info = inspect_ipsw(output)
    verify_target(info, args.product)
    result = {"firmware": record, "ipsw": info}
    if args.manifest:
        _write_json(args.manifest, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def inspect_command(args: argparse.Namespace) -> int:
    info = inspect_ipsw(args.ipsw)
    if args.product:
        verify_target(info, args.product)
    print(json.dumps(info, indent=2, sort_keys=True))
    return 0


def upgrade_command(args: argparse.Namespace) -> int:
    info = inspect_ipsw(args.ipsw)
    verify_target(info, args.product)
    catalog = fetch_catalog(args.product, args.catalog, args.timeout)
    record = select_firmware(
        catalog,
        version=info["product_version"],
        build=info["product_build"],
        signed_only=True,
    )
    tool = shutil.which(args.idevicerestore) or (
        args.idevicerestore if pathlib.Path(args.idevicerestore).is_file() else None
    )
    if not tool:
        raise IPSWError("idevicerestore is required")
    command = [tool]
    if args.ecid:
        command += ["--ecid", args.ecid]
    if args.erase:
        command.append("--erase")
    if args.cache_path:
        command += ["--cache-path", str(args.cache_path)]
    if not args.execute:
        command.append("--no-action")
    command.append(str(args.ipsw.resolve()))
    evidence = {
        "schema_version": 1,
        "operation": "signed-ipsw-upgrade" if not args.erase else "signed-ipsw-erase-restore",
        "product": args.product,
        "firmware": record,
        "ipsw": info,
        "execute": args.execute,
        "erase": args.erase,
        "command": command,
        "security_boundary": "Only a catalog-signed firmware record is accepted. Apple TSS and idevicerestore remain authoritative.",
    }
    if args.execute:
        if args.owner_authorization != OWNER_ACK:
            raise IPSWError("owner authorization acknowledgement was not accepted")
        if args.confirm != UPGRADE_ACK:
            raise IPSWError("restore execution confirmation was not accepted")
    result = subprocess.run(command, cwd=ROOT, text=True, check=False)
    evidence["exit_code"] = result.returncode
    if args.evidence:
        _write_json(args.evidence, evidence)
    return result.returncode


def downgrade_command(args: argparse.Namespace) -> int:
    info = inspect_ipsw(args.ipsw)
    verify_target(info, args.product)
    catalog = fetch_catalog(args.product, args.catalog, args.timeout)
    record = select_firmware(
        catalog,
        version=info["product_version"],
        build=info["product_build"],
        signed_only=False,
    )
    if record["signed"]:
        raise IPSWError("target firmware is signed; use the signed upgrade/restore workflow")
    plan = {
        "schema_version": 1,
        "operation": "tethered-downgrade",
        "product": args.product,
        "firmware": record,
        "ipsw": info,
        "tethered": True,
        "persistent": False,
        "requires_external_first_stage": True,
        "requires_boot_on_every_restart": True,
        "security_boundary": "B34ST does not bypass Apple signing. An operator-supplied authorized tether adapter must implement the boot chain.",
    }
    if not args.execute:
        if args.evidence:
            _write_json(args.evidence, plan)
        print(json.dumps(plan, indent=2, sort_keys=True))
        return 0
    if args.owner_authorization != OWNER_ACK:
        raise IPSWError("owner authorization acknowledgement was not accepted")
    if args.confirm != DOWNGRADE_ACK:
        raise IPSWError("tethered downgrade confirmation was not accepted")
    if not args.adapter_command:
        raise IPSWError("--adapter-command is required for tethered downgrade execution")
    request = {
        "schema_version": 1,
        "operation": "tethered-downgrade",
        "arguments": {
            "product": args.product,
            "ipsw_path": str(args.ipsw.resolve()),
            "ipsw_sha256": info["sha256"],
            "version": info["product_version"],
            "build": info["product_build"],
            "ecid": args.ecid,
            "tethered": True,
        },
    }
    try:
        result = subprocess.run(
            shlex.split(args.adapter_command),
            cwd=ROOT,
            input=json.dumps(request),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=args.timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise IPSWError(f"tether adapter failed: {exc}") from exc
    if len(result.stdout.encode("utf-8")) > MAX_ADAPTER_OUTPUT:
        raise IPSWError("tether adapter response exceeds size limit")
    try:
        response = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise IPSWError("tether adapter returned invalid JSON") from exc
    plan["adapter_response"] = response
    plan["exit_code"] = result.returncode
    if args.evidence:
        _write_json(args.evidence, plan)
    if result.returncode != 0 or not isinstance(response, dict) or response.get("ok") is not True:
        detail = response.get("error") if isinstance(response, dict) else result.stderr
        raise IPSWError(f"tether adapter rejected the operation: {detail}")
    print(json.dumps(plan, indent=2, sort_keys=True))
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("--catalog", default=DEFAULT_CATALOG,
                      help="catalog URL template or local JSON file")
    root.add_argument("--timeout", type=float, default=60.0)
    sub = root.add_subparsers(dest="command", required=True)

    catalog = sub.add_parser("catalog")
    catalog.add_argument("--product", required=True)
    catalog.add_argument("--signed-only", action="store_true")

    download = sub.add_parser("download")
    download.add_argument("--product", required=True)
    download.add_argument("--version")
    download.add_argument("--build")
    download.add_argument("--signed-only", action="store_true")
    download.add_argument("--output-dir", type=pathlib.Path, default=pathlib.Path("downloads/ipsw"))
    download.add_argument("--manifest", type=pathlib.Path)

    inspect = sub.add_parser("inspect")
    inspect.add_argument("ipsw", type=pathlib.Path)
    inspect.add_argument("--product")

    upgrade = sub.add_parser("upgrade")
    upgrade.add_argument("--product", required=True)
    upgrade.add_argument("--ipsw", type=pathlib.Path, required=True)
    upgrade.add_argument("--idevicerestore", default="idevicerestore")
    upgrade.add_argument("--ecid")
    upgrade.add_argument("--cache-path", type=pathlib.Path)
    upgrade.add_argument("--erase", action="store_true")
    upgrade.add_argument("--execute", action="store_true")
    upgrade.add_argument("--owner-authorization")
    upgrade.add_argument("--confirm")
    upgrade.add_argument("--evidence", type=pathlib.Path)

    downgrade = sub.add_parser("tethered-downgrade")
    downgrade.add_argument("--product", required=True)
    downgrade.add_argument("--ipsw", type=pathlib.Path, required=True)
    downgrade.add_argument("--ecid")
    downgrade.add_argument("--adapter-command")
    downgrade.add_argument("--execute", action="store_true")
    downgrade.add_argument("--owner-authorization")
    downgrade.add_argument("--confirm")
    downgrade.add_argument("--evidence", type=pathlib.Path)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.timeout <= 0 or args.timeout > 3600:
            raise IPSWError("timeout must be in the range 0..3600 seconds")
        if args.command == "catalog":
            return catalog_command(args)
        if args.command == "download":
            return download_command(args)
        if args.command == "inspect":
            return inspect_command(args)
        if args.command == "upgrade":
            return upgrade_command(args)
        return downgrade_command(args)
    except (IPSWError, OSError, ValueError) as exc:
        print(f"ipsw error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
