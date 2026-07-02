#!/usr/bin/env python3

"""Targeted IPSW discovery, download, verification, and restore orchestration."""
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import plistlib
import shlex
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
import zipfile
from typing import Any

try:
    from .tls_support import TLSConfigurationError, tls_client_context
    from .project_version import RELEASE_VERSION
except ImportError:
    from tls_support import TLSConfigurationError, tls_client_context
    from project_version import RELEASE_VERSION

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = "https://api.ipsw.me/v4/device/{product}?type=ipsw"
MAX_CATALOG_SIZE = 8 * 1024 * 1024
MAX_ADAPTER_OUTPUT = 1024 * 1024
OWNER_ACK = "I OWN OR AM AUTHORIZED TO RESTORE THIS DEVICE"
UPGRADE_ACK = "START SIGNED IPSW RESTORE"
DOWNGRADE_ACK = "START TETHERED DOWNGRADE"
TETHER_ADAPTER_ENV = "B34ST_TETHER_ADAPTER"
TETHER_ADAPTER_DEFINITION = (
    "A tether adapter is a separately installed, target-specific executable "
    "(a program, script, or reviewed wrapper around lab boot tooling) that "
    "communicates with the device in DFU/recovery mode and performs the "
    "external boot sequence B34ST cannot perform itself."
)
PUBLIC_ADAPTER_GUIDANCE = (
    "Public compatibility note: Semaphorin and checkm8-based projects target "
    "A11 and earlier devices; palera1n is a jailbreak rather than a downgrade "
    "adapter; futurerestore is an SHSH/SEP/baseband restore workflow; and "
    "libirecovery/idevicerestore are components, not complete tether adapters. "
    "None is a verified drop-in adapter for B34ST's current A12+ profiles."
)


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
            headers={"User-Agent": f"B34ST/{RELEASE_VERSION} IPSW catalog client"},
        )
        try:
            context = tls_client_context()
            with urllib.request.urlopen(
                request, timeout=timeout, context=context
            ) as response:
                data = response.read(MAX_CATALOG_SIZE + 1)
        except TLSConfigurationError as exc:
            raise IPSWError(f"TLS trust configuration error: {exc}") from exc
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
        normalized.append(
            {
                "product": product,
                "version": version,
                "build": build,
                "signed": signed,
                "url": _apple_firmware_url(url),
                "sha1": record.get("sha1sum") or record.get("sha1"),
                "released": record.get("releasedate") or record.get("date"),
                "filename": pathlib.PurePosixPath(urllib.parse.urlparse(url).path).name,
            }
        )
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
                if "Restore.plist" in names
                else {}
            )
            manifest = (
                plistlib.loads(archive.read("BuildManifest.plist"))
                if "BuildManifest.plist" in names
                else {}
            )
    except (zipfile.BadZipFile, KeyError, plistlib.InvalidFileException) as exc:
        raise IPSWError(f"invalid IPSW archive: {exc}") from exc
    products = (
        manifest.get("SupportedProductTypes")
        or restore.get("SupportedProductTypes")
        or []
    )
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
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def catalog_command(args: argparse.Namespace) -> int:
    value = fetch_catalog(args.product, args.catalog, args.timeout)
    if args.signed_only:
        value["firmwares"] = [item for item in value["firmwares"] if item["signed"]]
    elif args.unsigned_only:
        value["firmwares"] = [item for item in value["firmwares"] if not item["signed"]]
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
        "operation": "signed-ipsw-upgrade"
        if not args.erase
        else "signed-ipsw-erase-restore",
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


def _adapter_configuration(
    command: str | None,
) -> tuple[list[str] | None, str | None, str | None]:
    raw = command or os.environ.get(TETHER_ADAPTER_ENV)
    source = "--adapter-command" if command else TETHER_ADAPTER_ENV if raw else None
    if not raw:
        return (
            None,
            None,
            (
                "No external tether adapter is configured. B34ST does not bundle "
                "a target-specific boot adapter. Supply --adapter-command or set "
                f"{TETHER_ADAPTER_ENV}."
            ),
        )
    if any(c in raw for c in ";|&$`\n\r()"):
        return None, source, "External adapter command contains shell metacharacters."
    try:
        tokens = shlex.split(raw)
    except ValueError as exc:
        return None, source, f"Unable to parse external adapter command: {exc}"
    if not tokens:
        return None, source, "External adapter command is empty."
    executable = shutil.which(tokens[0])
    if executable is None:
        candidate = pathlib.Path(tokens[0]).expanduser()
        if candidate.is_file() and os.access(candidate, os.X_OK):
            executable = str(candidate.resolve())
    if executable is None:
        return (
            None,
            source,
            (
                f"External adapter executable was not found or is not executable: "
                f"{tokens[0]}"
            ),
        )
    tokens[0] = executable
    return tokens, source, None


def _prepare_downgrade(
    args: argparse.Namespace,
) -> tuple[dict[str, Any], dict[str, Any], list[str] | None, str | None]:
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
        raise IPSWError(
            "target firmware is signed; use the signed upgrade/restore workflow"
        )
    adapter, adapter_source, adapter_error = _adapter_configuration(
        args.adapter_command
    )
    blockers = [] if adapter_error is None else [adapter_error]
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
        "execution_readiness": {
            "ready": not blockers,
            "adapter_configured": adapter is not None,
            "adapter_source": adapter_source,
            "adapter_executable": adapter[0] if adapter else None,
            "blockers": blockers,
        },
        "requirements": [
            "A device you own or are authorized to restore",
            "A matching unsigned IPSW with a valid BuildManifest",
            "A reviewed target-specific external tether adapter",
            "DFU/recovery mode, a stable USB connection, and host power",
            "A compatible boot chain that must run after every restart",
        ],
        "next_steps": [
            "Review the target product, version, build, and IPSW SHA-256.",
            "Configure and preflight the external tether adapter.",
            "Place the device in the mode required by that adapter.",
            "Authorize execution and preserve the structured adapter result.",
            "Repeat the external tethered boot after every device restart.",
        ],
        "adapter_contract": {
            "definition": TETHER_ADAPTER_DEFINITION,
            "b34st_role": (
                "Validate the target/IPSW, create evidence, send one bounded "
                "JSON request, and verify the structured result."
            ),
            "adapter_role": (
                "Perform target-specific device communication and the "
                "authorized external boot sequence, then report success or "
                "failure as JSON."
            ),
            "not_an_adapter": [
                "The IPSW file",
                "A USB cable by itself",
                "Apple idevicerestore",
                "A generic component bundled with B34ST",
            ],
            "public_compatibility": PUBLIC_ADAPTER_GUIDANCE,
            "input": "One JSON request on stdin matching schemas/tethered-downgrade-adapter-v1.json",
            "success_output": 'One JSON object on stdout containing {"ok": true}',
            "failure_output": 'One JSON object on stdout containing {"ok": false, "error": "..."}',
        },
    }
    return info, plan, adapter, adapter_error


def _render_downgrade_plan(plan: dict[str, Any]) -> str:
    firmware = plan["firmware"]
    ipsw = plan["ipsw"]
    readiness = plan["execution_readiness"]
    lines = [
        "",
        "Tethered downgrade plan",
        "=" * 64,
        f"Target:      {plan['product']}  iOS {firmware['version']} "
        f"({firmware['build']})",
        f"IPSW:        {ipsw['path']}",
        f"SHA-256:     {ipsw['sha256']}",
        "Persistence: no — the external boot stage is required after every restart",
        "Stock restore: unsupported for this unsigned target",
        f"Execution:   {'READY' if readiness['ready'] else 'PLAN ONLY'}",
    ]
    if readiness["adapter_configured"]:
        lines.append(
            f"Adapter:     {readiness['adapter_executable']} "
            f"(from {readiness['adapter_source']})"
        )
    for blocker in readiness["blockers"]:
        lines.append(f"Blocked by:  {blocker}")
    lines.extend(
        [
            "",
            "What the tether adapter is:",
            f"  {plan['adapter_contract']['definition']}",
            "  B34ST validates and orchestrates; the adapter performs the "
            "target-specific device-side boot work.",
            "  It is not the IPSW, a USB cable, idevicerestore, or a component "
            "bundled with B34ST.",
            f"  {plan['adapter_contract']['public_compatibility']}",
            "  Public-project details: docs/TETHERED_DOWNGRADE.md",
            "",
            "What happens next:",
        ]
    )
    lines.extend(
        f"  {index}. {step}" for index, step in enumerate(plan["next_steps"], 1)
    )
    lines.extend(
        [
            "",
            "Adapter contract:",
            f"  Input:  {plan['adapter_contract']['input']}",
            f"  Output: {plan['adapter_contract']['success_output']}",
            "=" * 64,
        ]
    )
    return "\n".join(lines)


def _write_or_print_downgrade_plan(
    args: argparse.Namespace,
    plan: dict[str, Any],
) -> None:
    if args.evidence:
        _write_json(args.evidence, plan)
    if getattr(args, "human", False):
        print(_render_downgrade_plan(plan))
        if args.evidence:
            print(f"\nSaved plan: {args.evidence.resolve()}")
    else:
        print(json.dumps(plan, indent=2, sort_keys=True))


def _execute_tether_adapter(
    args: argparse.Namespace,
    info: dict[str, Any],
    plan: dict[str, Any],
    adapter: list[str],
) -> int:
    if args.owner_authorization != OWNER_ACK:
        raise IPSWError("owner authorization acknowledgement was not accepted")
    if args.confirm != DOWNGRADE_ACK:
        raise IPSWError("tethered downgrade confirmation was not accepted")
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
            adapter,
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
        diagnostic = result.stderr.strip()
        detail = f"; adapter stderr: {diagnostic[:500]}" if diagnostic else ""
        raise IPSWError(
            "tether adapter returned invalid JSON on stdout; emit diagnostics "
            f"on stderr and one JSON response on stdout{detail}"
        ) from exc
    plan["adapter_response"] = response
    plan["exit_code"] = result.returncode
    if args.evidence:
        _write_json(args.evidence, plan)
    if (
        result.returncode != 0
        or not isinstance(response, dict)
        or response.get("ok") is not True
    ):
        detail = (
            (response.get("error") if isinstance(response, dict) else None)
            or result.stderr.strip()
            or f"adapter exit code {result.returncode}"
        )
        raise IPSWError(f"tether adapter rejected the operation: {detail}")
    if getattr(args, "human", False):
        print(_render_downgrade_plan(plan))
        print("\nExternal tether adapter completed successfully.")
        print("Reminder: rerun the tethered boot after every device restart.")
    else:
        print(json.dumps(plan, indent=2, sort_keys=True))
    return 0


def downgrade_command(args: argparse.Namespace) -> int:
    info, plan, adapter, adapter_error = _prepare_downgrade(args)
    if not args.execute:
        _write_or_print_downgrade_plan(args, plan)
        return 0
    if adapter_error is not None or adapter is None:
        raise IPSWError(adapter_error or "external tether adapter is unavailable")
    return _execute_tether_adapter(args, info, plan, adapter)


def _guide_prompt(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        return input(f"{label}{suffix}: ").strip() or default
    except (EOFError, KeyboardInterrupt):
        return ""


def _guide_confirm(label: str) -> bool:
    return _guide_prompt(f"{label} (y/N)").lower() in {"y", "yes"}


def _default_guide_evidence() -> pathlib.Path:
    stamp = dt.datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    return (
        ROOT
        / "runtime-artifacts"
        / "b34st"
        / "tethered-downgrade"
        / stamp
        / "plan.json"
    )


def _select_unsigned_firmware(args: argparse.Namespace) -> dict[str, Any]:
    catalog = fetch_catalog(args.product, args.catalog, args.timeout)
    unsigned = [item for item in catalog["firmwares"] if not item["signed"]]
    if not unsigned:
        raise IPSWError(f"the catalog contains no unsigned IPSWs for {args.product}")
    version = args.version or _guide_prompt(
        "Exact target iOS version (blank to browse the newest 20)", ""
    )
    build = args.build
    matches = [
        record
        for record in unsigned
        if (not version or record["version"] == version)
        and (not build or record["build"] == build)
    ]
    if not matches:
        qualifier = build or version or "requested criteria"
        raise IPSWError(f"the catalog contains no unsigned target matching {qualifier}")
    if len(matches) == 1:
        selected = matches[0]
        print(
            f"\nSelected unsigned target: iOS {selected['version']} "
            f"({selected['build']})"
        )
        return selected

    displayed = matches[:20]
    print("\nUnsigned firmware available from the configured catalog:")
    for index, record in enumerate(displayed, 1):
        released = f", released {record['released']}" if record["released"] else ""
        print(f"  {index:2d}. iOS {record['version']} ({record['build']}){released}")
    if len(matches) > len(displayed):
        print(
            f"  ... {len(matches) - len(displayed)} older targets hidden; "
            "rerun and enter an exact version to select one."
        )
    choice = _guide_prompt("Select target", "1")
    if not choice.isdigit() or not 1 <= int(choice) <= len(displayed):
        raise IPSWError("invalid unsigned firmware selection")
    return displayed[int(choice) - 1]


def downgrade_guide_command(args: argparse.Namespace) -> int:
    print(
        "\nB34ST guided tethered downgrade\n"
        "--------------------------------\n"
        "Outcome: a temporary, externally booted unsigned runtime.\n"
        "After every restart, the external tethered boot must run again.\n"
        "B34ST validates the IPSW and records evidence; it does not bundle\n"
        "a target-specific boot adapter or send unsigned firmware through\n"
        "Apple's stock restore path.\n"
        "\n"
        "What is the tether adapter?\n"
        "It is a separately installed, target-specific executable (a program,\n"
        "script, or reviewed wrapper around lab boot tooling). It communicates\n"
        "with the device in DFU/recovery mode and performs the external boot\n"
        "sequence B34ST cannot perform itself. It is not the IPSW, the USB\n"
        "cable, idevicerestore, or a generic component included with B34ST.\n"
        "\n"
        "Public-tool compatibility\n"
        "Semaphorin/Legacy iOS Kit/checkm8-era tools apply to older hardware;\n"
        "palera1n is not a downgrade adapter; futurerestore requires its own\n"
        "blob/SEP/baseband workflow. None is a verified drop-in adapter for\n"
        "B34ST's current A12+ profiles. See docs/TETHERED_DOWNGRADE.md.\n"
    )
    if not args.product:
        args.product = _guide_prompt("Apple product identifier", "iPhone12,1")
    if not args.product:
        raise IPSWError("a product identifier is required")

    if args.ipsw is None:
        source = _guide_prompt(
            "IPSW source: local file (L) or Apple catalog download (D)", "L"
        ).lower()
        if source in {"d", "download"}:
            record = _select_unsigned_firmware(args)
            print(
                "\nIPSW downloads are commonly several gigabytes and are saved "
                "for reuse."
            )
            if not _guide_confirm(
                f"Download iOS {record['version']} ({record['build']})"
            ):
                print("Cancelled before download.")
                return 0
            args.ipsw = download_firmware(record, args.download_dir)
            print(f"\nDownloaded and selected: {args.ipsw.resolve()}")
        elif source in {"l", "local"}:
            path = _guide_prompt("Verified local IPSW path")
            if not path:
                raise IPSWError(
                    "a local IPSW path is required; rerun the guide and choose "
                    "D to download one"
                )
            args.ipsw = pathlib.Path(path).expanduser()
        else:
            raise IPSWError("choose L for a local IPSW or D to download")

    configured_adapter = args.adapter_command or os.environ.get(TETHER_ADAPTER_ENV)
    if not args.plan_only and not configured_adapter:
        print(
            "\nExternal adapter setup\n"
            "The adapter is the separately installed, target-specific program,\n"
            "script, or reviewed wrapper that communicates with the device and\n"
            "performs the external boot sequence. It is not the IPSW, cable, or\n"
            "idevicerestore. B34ST does not include this component. The command\n"
            "must read one request JSON object from stdin and write one response\n"
            'JSON object such as {"ok": true} to stdout.\n'
            "\nNo verified public drop-in adapter currently covers B34ST's A12+\n"
            "profiles. Older public checkm8 tools are not interchangeable with\n"
            "an A12+ adapter. See docs/TETHERED_DOWNGRADE.md for the compatibility\n"
            "table and contract-only example.\n"
        )
        args.adapter_command = (
            _guide_prompt("Adapter command (blank to save a plan only)") or None
        )

    args.evidence = args.evidence or _default_guide_evidence()
    args.human = True
    args.execute = False
    print(
        "\nValidating the IPSW manifest, product, catalog status, and SHA-256. "
        "Large IPSWs may take several minutes..."
    )
    info, plan, adapter, adapter_error = _prepare_downgrade(args)
    _write_or_print_downgrade_plan(args, plan)

    if args.plan_only:
        print(
            "\nStopped after planning; no device-changing command was run.\n"
            f"To continue later, set {TETHER_ADAPTER_ENV} to the reviewed "
            "adapter command and rerun this guide with the same IPSW."
        )
        return 0
    if configured_adapter and adapter_error is not None:
        raise IPSWError(adapter_error)
    if adapter is None:
        print(
            "\nStopped after planning; no device-changing command was run.\n"
            f"To continue later, set {TETHER_ADAPTER_ENV} to the reviewed "
            "adapter command and rerun this guide with the same IPSW."
        )
        return 0
    if not _guide_confirm(
        "Adapter preflight passed. Start the external tethered downgrade now"
    ):
        print("Stopped after planning; no device-changing command was run.")
        return 0

    args.owner_authorization = _guide_prompt(f'Type "{OWNER_ACK}"')
    args.confirm = _guide_prompt(f'Type "{DOWNGRADE_ACK}"')
    args.execute = True
    return _execute_tether_adapter(args, info, plan, adapter)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="fbr34ker ipsw",
        description=__doc__,
    )
    root.add_argument(
        "--catalog",
        default=DEFAULT_CATALOG,
        help="catalog URL template or local JSON file",
    )
    root.add_argument("--timeout", type=float, default=60.0)
    sub = root.add_subparsers(dest="command", required=True)

    catalog = sub.add_parser("catalog")
    catalog.add_argument("--product", required=True)
    catalog_filter = catalog.add_mutually_exclusive_group()
    catalog_filter.add_argument("--signed-only", action="store_true")
    catalog_filter.add_argument("--unsigned-only", action="store_true")

    download = sub.add_parser("download")
    download.add_argument("--product", required=True)
    download.add_argument("--version")
    download.add_argument("--build")
    download.add_argument("--signed-only", action="store_true")
    download.add_argument(
        "--output-dir", type=pathlib.Path, default=pathlib.Path("downloads/ipsw")
    )
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

    downgrade = sub.add_parser(
        "tethered-downgrade",
        help="advanced plan/execute interface; use tethered-downgrade-guide interactively",
    )
    downgrade.add_argument("--product", required=True)
    downgrade.add_argument("--ipsw", type=pathlib.Path, required=True)
    downgrade.add_argument("--ecid")
    downgrade.add_argument(
        "--adapter-command",
        help=(
            "reviewed external adapter executable and arguments; defaults to "
            f"${TETHER_ADAPTER_ENV}"
        ),
    )
    downgrade.add_argument("--execute", action="store_true")
    downgrade.add_argument("--owner-authorization")
    downgrade.add_argument("--confirm")
    downgrade.add_argument("--evidence", type=pathlib.Path)
    downgrade.add_argument(
        "--human", action="store_true", help="print an operator-oriented plan"
    )

    guide = sub.add_parser(
        "tethered-downgrade-guide",
        help="guided target selection, adapter preflight, plan, and optional execution",
        description=(
            "Validate or download an unsigned IPSW, save a readable plan, "
            "preflight an external tether adapter, and optionally execute it. "
            "B34ST does not bundle the target-specific adapter."
        ),
    )
    guide.add_argument(
        "--product", help="Apple product identifier; prompted when omitted"
    )
    guide.add_argument(
        "--ipsw",
        type=pathlib.Path,
        help="local unsigned IPSW; the guide offers local/download selection when omitted",
    )
    guide.add_argument(
        "--version",
        help="exact unsigned iOS version to select when downloading",
    )
    guide.add_argument(
        "--build",
        help="exact unsigned build to select when downloading",
    )
    guide.add_argument(
        "--ecid", help="optional exact device ECID passed to the adapter"
    )
    guide.add_argument(
        "--adapter-command",
        help=(
            "reviewed external adapter executable and arguments; defaults to "
            f"${TETHER_ADAPTER_ENV}"
        ),
    )
    guide.add_argument(
        "--evidence",
        type=pathlib.Path,
        help="plan/result JSON path; defaults under runtime-artifacts",
    )
    guide.add_argument(
        "--download-dir",
        type=pathlib.Path,
        default=pathlib.Path("downloads/ipsw"),
    )
    guide.add_argument(
        "--plan-only",
        action="store_true",
        help="validate and save the plan without prompting for execution",
    )
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
        if args.command == "tethered-downgrade-guide":
            return downgrade_guide_command(args)
        return downgrade_command(args)
    except (IPSWError, OSError, ValueError) as exc:
        print(f"ipsw error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
