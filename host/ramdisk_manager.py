#!/usr/bin/env python3
"""Build, inspect, plan, and externally load bounded FBR34KER ramdisk bundles."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import shlex
import shutil
import subprocess
import sys
import zipfile
from typing import Any, Iterable

try:
    from .boot_image import BootImageError, load_profile
except ImportError:
    from boot_image import BootImageError, load_profile


ROOT = pathlib.Path(__file__).resolve().parents[1]
PROFILES = ROOT / "profiles"
FORMAT = "fbrd-v1"
SCHEMA_VERSION = 1
VERSION_RE = re.compile(r'^#define FBR34KER_MONITOR_VERSION "([^"]+)"$', re.M)
RELEASE_VERSION = VERSION_RE.search(
    (ROOT / "include/fbr34ker/version.h").read_text(encoding="utf-8")
).group(1)
OWNER_AUTHORIZATION = "I OWN OR AM AUTHORIZED TO LOAD THIS RAMDISK"
EXECUTION_CONFIRMATION = "LOAD AUTHORIZED RAMDISK"
MAX_COMPONENTS = 16
MAX_COMPONENT_SIZE = 8 * 1024 * 1024 * 1024
MAX_BUNDLE_SIZE = 16 * 1024 * 1024 * 1024
MAX_ADAPTER_OUTPUT = 1024 * 1024
ROLE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,31}$")
HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
VERSION_PATTERN = re.compile(r"^[0-9][0-9A-Za-z._+-]{0,31}$")
PRODUCT_PATTERN = re.compile(r"^([A-Za-z]+)([0-9]+),([0-9]+)$")
CORE_ROLES = ("ramdisk", "kernelcache", "devicetree")
OPTIONAL_ROLES = (
    "trustcache",
    "ibss",
    "ibec",
    "iboot",
    "bootlogo",
    "restore-device-tree",
)


class RamdiskError(ValueError):
    pass


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: pathlib.Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def device_class(product: str) -> str:
    if product.startswith("iPhone"):
        return "iphone"
    if product.startswith("iPad"):
        return "ipad"
    if product.startswith(("Mac", "iMac")):
        return "mac"
    raise RamdiskError(
        f"{product!r} is not an iPhone, iPad, or Apple silicon Mac product identifier"
    )


def operating_system(kind: str) -> str:
    return {"iphone": "iOS", "ipad": "iPadOS", "mac": "macOS"}[kind]


def product_sort_key(item: dict[str, Any]) -> tuple[int, str, int, int]:
    product = item["product"]
    match = PRODUCT_PATTERN.fullmatch(product)
    prefix, major, minor = (
        (match.group(1), int(match.group(2)), int(match.group(3)))
        if match
        else (product, 0, 0)
    )
    return (
        {"iphone": 0, "ipad": 1, "mac": 2}[item["device_class"]],
        prefix,
        major,
        minor,
    )


def portable_path(path: pathlib.Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def profile_paths() -> list[pathlib.Path]:
    paths: list[pathlib.Path] = []
    for path in sorted(PROFILES.glob("apple-*-recovery.json")):
        try:
            profile = load_profile(path)
        except BootImageError:
            continue
        products = profile.get("product_types", [])
        if profile.get("requires_exact_product") and products and all(
            str(product).startswith(("iPhone", "iPad", "Mac", "iMac"))
            for product in products
        ):
            paths.append(path)
    return paths


def target_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in profile_paths():
        profile = load_profile(path)
        for product_value in profile["product_types"]:
            product = str(product_value)
            kind = device_class(product)
            records.append(
                {
                    "product": product,
                    "device_class": kind,
                    "operating_system": operating_system(kind),
                    "profile_id": profile["profile_id"],
                    "profile": str(path.relative_to(ROOT)),
                    "family": profile["family"],
                    "cpids": profile["cpids"],
                    "maturity": profile.get("maturity", "unverified"),
                    "physical_execution_verified": profile.get(
                        "physical_execution_verified", False
                    ),
                    "execution_contract": profile.get("execution_contract"),
                    "compatibility": "profiled-unverified",
                }
            )
    return sorted(records, key=product_sort_key)


def resolve_profile(
    product: str, profile_path: pathlib.Path | None
) -> tuple[pathlib.Path, dict[str, Any], dict[str, Any]]:
    matches = [item for item in target_records() if item["product"] == product]
    if not matches:
        raise RamdiskError(
            f"no exact ramdisk profile exists for {product}; run "
            "'fbr34ker ramdisk list-targets'"
        )
    if profile_path is None:
        if len(matches) != 1:
            raise RamdiskError(
                f"multiple profiles match {product}; specify --profile explicitly"
            )
        profile_path = ROOT / matches[0]["profile"]
    elif not profile_path.is_absolute():
        profile_path = ROOT / profile_path
    try:
        profile = load_profile(profile_path)
    except BootImageError as exc:
        raise RamdiskError(str(exc)) from exc
    products = profile.get("product_types", [])
    if product not in products:
        raise RamdiskError(
            f"profile {profile.get('profile_id')} does not include product {product}"
        )
    kind = device_class(product)
    record = {
        "product": product,
        "device_class": kind,
        "operating_system": operating_system(kind),
        "profile_id": profile["profile_id"],
        "profile": portable_path(profile_path),
        "family": profile["family"],
        "cpids": profile["cpids"],
        "maturity": profile.get("maturity", "unverified"),
        "physical_execution_verified": profile.get(
            "physical_execution_verified", False
        ),
        "execution_contract": profile.get("execution_contract"),
        "compatibility": "profiled-unverified",
    }
    return profile_path, profile, record


def validate_version(value: str, field: str) -> str:
    if not VERSION_PATTERN.fullmatch(value):
        raise RamdiskError(f"{field} contains unsupported characters")
    return value


def make_plan(
    *,
    product: str,
    os_version: str,
    build: str | None,
    profile_path: pathlib.Path | None,
) -> dict[str, Any]:
    resolved_path, profile, target = resolve_profile(product, profile_path)
    validate_version(os_version, "OS version")
    if build:
        validate_version(build, "build")
    readiness: list[dict[str, str]] = [
        {
            "check": "exact-product-profile",
            "status": "pass",
            "detail": f"{profile['profile_id']} includes {product}",
        },
        {
            "check": "profile-maturity",
            "status": (
                "pass"
                if profile.get("physical_execution_verified", False)
                else "unverified"
            ),
            "detail": (
                "physical execution is verified"
                if profile.get("physical_execution_verified", False)
                else "profile is simulation-validated only; adapter evidence is required"
            ),
        },
        {
            "check": "os-build-support",
            "status": "adapter-required",
            "detail": (
                f"{operating_system(target['device_class'])} {os_version}"
                f"{f' ({build})' if build else ''} must be supported by the selected adapter"
            ),
        },
        {
            "check": "stock-boot-compatibility",
            "status": "external-loader-required",
            "detail": "the bundle is not directly compatible with stock iBoot",
        },
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "operation": "ramdisk-plan",
        "project": "FBR34KER",
        "release_version": RELEASE_VERSION,
        "target": target,
        "profile_sha256": sha256_file(resolved_path),
        "os_version": os_version,
        "build": build,
        "core_components": list(CORE_ROLES),
        "optional_components": list(OPTIONAL_ROLES),
        "execution_contract": "external-authorized-ramdisk-loader",
        "direct_stock_iboot_compatible": False,
        "physical_execution_verified": bool(
            profile.get("physical_execution_verified", False)
        ),
        "readiness": readiness,
        "next_steps": [
            "Prepare a target- and build-specific ramdisk, kernelcache, and DeviceTree.",
            "Build and inspect an FBRD bundle.",
            "Configure a reviewed adapter and run load without --execute first.",
            "Place the exact device in the adapter-required DFU/recovery state.",
            "Authorize execution and preserve the adapter response as evidence.",
        ],
    }


def component_values(args: argparse.Namespace) -> dict[str, pathlib.Path]:
    result: dict[str, pathlib.Path] = {}
    for role in CORE_ROLES + OPTIONAL_ROLES:
        value = getattr(args, role.replace("-", "_"), None)
        if value:
            result[role] = value
    for item in args.component or []:
        if "=" not in item:
            raise RamdiskError("--component must use ROLE=PATH")
        role, value = item.split("=", 1)
        if not ROLE_PATTERN.fullmatch(role):
            raise RamdiskError(f"invalid component role: {role}")
        if role in result:
            raise RamdiskError(f"duplicate component role: {role}")
        result[role] = pathlib.Path(value)
    missing = [role for role in CORE_ROLES if role not in result]
    if missing:
        raise RamdiskError(
            "missing required component(s): " + ", ".join(missing)
        )
    if len(result) > MAX_COMPONENTS:
        raise RamdiskError(f"at most {MAX_COMPONENTS} components are supported")
    return result


def validate_component(role: str, path: pathlib.Path) -> dict[str, Any]:
    if not ROLE_PATTERN.fullmatch(role):
        raise RamdiskError(f"invalid component role: {role}")
    if not path.is_file() or path.is_symlink():
        raise RamdiskError(f"{role} component is not a regular file: {path}")
    size = path.stat().st_size
    if size <= 0:
        raise RamdiskError(f"{role} component is empty")
    if size > MAX_COMPONENT_SIZE:
        raise RamdiskError(f"{role} component exceeds the 8 GiB limit")
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", path.name).strip(".-")
    if not safe_name:
        safe_name = role
    return {
        "role": role,
        "name": path.name,
        "archive_path": f"components/{role}/{safe_name}",
        "size": size,
        "sha256": sha256_file(path),
        "source": path,
    }


def zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    info.create_system = 3
    return info


def stream_into_zip(
    bundle: zipfile.ZipFile, info: zipfile.ZipInfo, source: pathlib.Path
) -> None:
    with source.open("rb") as input_stream, bundle.open(info, "w") as output_stream:
        for chunk in iter(lambda: input_stream.read(1024 * 1024), b""):
            output_stream.write(chunk)


def build_bundle(args: argparse.Namespace) -> dict[str, Any]:
    plan = make_plan(
        product=args.product,
        os_version=args.os_version,
        build=args.build,
        profile_path=args.profile,
    )
    components = [
        validate_component(role, path)
        for role, path in sorted(component_values(args).items())
    ]
    total_size = sum(item["size"] for item in components)
    if total_size > MAX_BUNDLE_SIZE:
        raise RamdiskError("component total exceeds the 16 GiB bundle limit")
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and not args.force:
        raise RamdiskError(f"output exists; pass --force to replace it: {output}")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "format": FORMAT,
        "project": "FBR34KER",
        "release_version": RELEASE_VERSION,
        "target": plan["target"],
        "profile_sha256": plan["profile_sha256"],
        "os_version": plan["os_version"],
        "build": plan["build"],
        "execution_contract": plan["execution_contract"],
        "direct_stock_iboot_compatible": False,
        "physical_execution_verified": plan["physical_execution_verified"],
        "components": [
            {key: value for key, value in item.items() if key != "source"}
            for item in components
        ],
    }
    manifest_bytes = (
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    temporary = output.with_name(output.name + ".tmp")
    try:
        with zipfile.ZipFile(
            temporary, "w", allowZip64=True, strict_timestamps=True
        ) as bundle:
            bundle.writestr(zip_info("manifest.json"), manifest_bytes)
            for item in components:
                stream_into_zip(
                    bundle, zip_info(item["archive_path"]), item["source"]
                )
        if temporary.stat().st_size > MAX_BUNDLE_SIZE:
            raise RamdiskError("resulting bundle exceeds the 16 GiB limit")
        temporary.replace(output)
    finally:
        if temporary.exists():
            temporary.unlink()
    return {
        "ok": True,
        "operation": "ramdisk-build",
        "path": str(output),
        "size": output.stat().st_size,
        "sha256": sha256_file(output),
        "component_count": len(components),
        "manifest": manifest,
    }


def load_manifest(bundle_path: pathlib.Path) -> tuple[dict[str, Any], zipfile.ZipFile]:
    if not bundle_path.is_file() or bundle_path.is_symlink():
        raise RamdiskError(f"bundle is not a regular file: {bundle_path}")
    if bundle_path.stat().st_size > MAX_BUNDLE_SIZE:
        raise RamdiskError("bundle exceeds the 16 GiB limit")
    try:
        bundle = zipfile.ZipFile(bundle_path, "r")
    except (OSError, zipfile.BadZipFile) as exc:
        raise RamdiskError(f"invalid FBRD ZIP: {exc}") from exc
    names = bundle.namelist()
    if len(names) != len(set(names)):
        bundle.close()
        raise RamdiskError("bundle contains duplicate paths")
    if "manifest.json" not in names:
        bundle.close()
        raise RamdiskError("bundle has no manifest.json")
    info = bundle.getinfo("manifest.json")
    if info.file_size > 1024 * 1024:
        bundle.close()
        raise RamdiskError("manifest exceeds the 1 MiB limit")
    try:
        manifest = json.loads(bundle.read(info))
    except (UnicodeError, json.JSONDecodeError, RuntimeError, NotImplementedError) as exc:
        bundle.close()
        raise RamdiskError(f"invalid manifest JSON: {exc}") from exc
    return manifest, bundle


def inspect_bundle(path: pathlib.Path) -> dict[str, Any]:
    manifest, bundle = load_manifest(path)
    try:
        if not isinstance(manifest, dict):
            raise RamdiskError("manifest must be an object")
        if manifest.get("schema_version") != SCHEMA_VERSION:
            raise RamdiskError("unsupported ramdisk manifest schema")
        if manifest.get("format") != FORMAT or manifest.get("project") != "FBR34KER":
            raise RamdiskError("not an FBR34KER FBRD v1 bundle")
        target = manifest.get("target")
        if not isinstance(target, dict):
            raise RamdiskError("manifest target is missing")
        resolve_profile(
            str(target.get("product")),
            pathlib.Path(str(target.get("profile"))),
        )
        components = manifest.get("components")
        if not isinstance(components, list) or not components:
            raise RamdiskError("manifest components are missing")
        if len(components) > MAX_COMPONENTS:
            raise RamdiskError("manifest contains too many components")
        roles: set[str] = set()
        expected_names = {"manifest.json"}
        total = 0
        for component in components:
            if not isinstance(component, dict):
                raise RamdiskError("invalid component record")
            role = component.get("role")
            archive_path = component.get("archive_path")
            size = component.get("size")
            expected_hash = component.get("sha256")
            if (
                not isinstance(role, str)
                or not ROLE_PATTERN.fullmatch(role)
                or role in roles
            ):
                raise RamdiskError("invalid or duplicate component role")
            if (
                not isinstance(archive_path, str)
                or not archive_path.startswith(f"components/{role}/")
                or ".." in pathlib.PurePosixPath(archive_path).parts
                or archive_path.startswith("/")
            ):
                raise RamdiskError(f"unsafe archive path for {role}")
            if not isinstance(size, int) or size <= 0 or size > MAX_COMPONENT_SIZE:
                raise RamdiskError(f"invalid size for {role}")
            if not isinstance(expected_hash, str) or not HASH_PATTERN.fullmatch(
                expected_hash
            ):
                raise RamdiskError(f"invalid SHA-256 for {role}")
            try:
                info = bundle.getinfo(archive_path)
            except KeyError as exc:
                raise RamdiskError(f"bundle is missing {archive_path}") from exc
            if info.is_dir() or info.file_size != size:
                raise RamdiskError(f"size mismatch for {role}")
            digest = hashlib.sha256()
            try:
                with bundle.open(info) as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
            except (RuntimeError, NotImplementedError, EOFError) as exc:
                raise RamdiskError(f"cannot read {role}: {exc}") from exc
            if digest.hexdigest() != expected_hash:
                raise RamdiskError(f"SHA-256 mismatch for {role}")
            roles.add(role)
            expected_names.add(archive_path)
            total += size
            if total > MAX_BUNDLE_SIZE:
                raise RamdiskError("uncompressed bundle exceeds the size limit")
        missing = set(CORE_ROLES) - roles
        if missing:
            raise RamdiskError(
                "bundle is missing core role(s): " + ", ".join(sorted(missing))
            )
        if set(bundle.namelist()) != expected_names:
            raise RamdiskError("bundle contains files not declared by its manifest")
    finally:
        bundle.close()
    return {
        "ok": True,
        "operation": "ramdisk-inspect",
        "path": str(path.resolve()),
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
        "component_count": len(manifest["components"]),
        "manifest": manifest,
    }


def adapter_command(value: str | None) -> list[str] | None:
    raw = value or os.environ.get("B34ST_RAMDISK_ADAPTER")
    if not raw:
        return None
    try:
        command = shlex.split(raw)
    except ValueError as exc:
        raise RamdiskError(f"invalid adapter command: {exc}") from exc
    if not command:
        raise RamdiskError("adapter command is empty")
    executable = pathlib.Path(command[0]).expanduser()
    if executable.is_absolute():
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise RamdiskError(f"adapter is not executable: {executable}")
        command[0] = str(executable)
    elif "/" in command[0]:
        candidate = (pathlib.Path.cwd() / executable).resolve()
        if not candidate.is_file() or not os.access(candidate, os.X_OK):
            raise RamdiskError(f"adapter is not executable: {candidate}")
        command[0] = str(candidate)
    else:
        resolved = shutil.which(command[0])
        if not resolved:
            raise RamdiskError(f"adapter executable is not on PATH: {command[0]}")
        command[0] = resolved
    return command


def load_request(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    inspection = inspect_bundle(args.bundle)
    manifest = inspection["manifest"]
    request = {
        "schema_version": SCHEMA_VERSION,
        "operation": "load-ramdisk",
        "project": "FBR34KER",
        "release_version": RELEASE_VERSION,
        "bundle": {
            "path": inspection["path"],
            "size": inspection["size"],
            "sha256": inspection["sha256"],
            "manifest": manifest,
        },
        "target": {
            **manifest["target"],
            "os_version": manifest["os_version"],
            "build": manifest.get("build"),
            "ecid": args.ecid,
        },
        "authorization": {
            "owner_authorized": bool(args.execute),
            "confirmation": bool(args.execute),
        },
        "constraints": {
            "direct_stock_iboot_compatible": False,
            "external_adapter_required": True,
            "persistent_after_restart": False,
        },
    }
    return inspection, request


def load_bundle(args: argparse.Namespace) -> dict[str, Any]:
    inspection, request = load_request(args)
    if not args.execute:
        command = adapter_command(args.adapter)
        result = {
            "ok": True,
            "executed": False,
            "operation": "ramdisk-load-plan",
            "bundle": inspection,
            "adapter_configured": command is not None,
            "adapter_command": command,
            "request": request,
            "next_step": (
                "review this request, then repeat with --execute and both "
                "authorization phrases"
            ),
        }
        if args.evidence:
            write_json(args.evidence, result)
        return result
    if args.owner_authorization != OWNER_AUTHORIZATION:
        raise RamdiskError(
            f'--owner-authorization must exactly equal "{OWNER_AUTHORIZATION}"'
        )
    if args.confirm != EXECUTION_CONFIRMATION:
        raise RamdiskError(f'--confirm must exactly equal "{EXECUTION_CONFIRMATION}"')
    command = adapter_command(args.adapter)
    if command is None:
        raise RamdiskError(
            "execution requires --adapter or B34ST_RAMDISK_ADAPTER"
        )
    request["authorization"] = {
        "owner_authorized": True,
        "confirmation": True,
        "owner_authorization_text": OWNER_AUTHORIZATION,
    }
    try:
        process = subprocess.run(
            command,
            input=json.dumps(request, sort_keys=True) + "\n",
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=args.timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RamdiskError(f"adapter execution failed: {exc}") from exc
    if len(process.stdout.encode("utf-8", errors="replace")) > MAX_ADAPTER_OUTPUT:
        raise RamdiskError("adapter stdout exceeds the 1 MiB contract limit")
    if process.returncode != 0:
        detail = process.stderr.strip()[:512] or process.stdout.strip()[:512]
        raise RamdiskError(
            f"adapter exited with {process.returncode}"
            + (f": {detail}" if detail else "")
        )
    try:
        response = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise RamdiskError("adapter stdout is not one JSON object") from exc
    if (
        not isinstance(response, dict)
        or response.get("schema_version") != SCHEMA_VERSION
        or response.get("ok") is not True
    ):
        raise RamdiskError(
            "adapter response must be schema_version 1 with ok=true"
        )
    result = {
        "ok": True,
        "executed": True,
        "operation": "ramdisk-load",
        "bundle": inspection,
        "adapter_command": command,
        "adapter_response": response,
    }
    if args.evidence:
        write_json(args.evidence, result)
    return result


def print_plan(plan: dict[str, Any]) -> None:
    target = plan["target"]
    build_suffix = f" / {plan['build']}" if plan["build"] else ""
    print("FBR34KER ramdisk compatibility plan")
    print(f"Product:       {target['product']} ({target['device_class']})")
    print(f"OS/build:      {plan['os_version']}{build_suffix}")
    print(f"Family/CPID:   {target['family']} / {', '.join(target['cpids'])}")
    print(f"Profile:       {target['profile_id']}")
    print("Compatibility: profiled, simulation-validated, physical adapter unverified")
    print("Boot contract: external authorized ramdisk loader; not stock iBoot")
    print("\nReadiness:")
    for check in plan["readiness"]:
        print(f"  [{check['status']}] {check['check']}: {check['detail']}")
    print("\nRequired: " + ", ".join(plan["core_components"]))
    print("Optional: " + ", ".join(plan["optional_components"]))


def list_targets(json_mode: bool) -> None:
    records = target_records()
    result = {
        "schema_version": SCHEMA_VERSION,
        "compatibility_scope": "exact-profiled-products",
        "physical_execution_verified": bool(records) and all(
            item["physical_execution_verified"] for item in records
        ),
        "os_version_policy": "exact adapter support and evidence required",
        "target_count": len(records),
        "targets": records,
    }
    if json_mode:
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    print("Profiled ramdisk targets")
    print("Status: simulation-validated; external adapter and exact OS/build support required")
    current = None
    for record in records:
        if record["device_class"] != current:
            current = record["device_class"]
            print(f"\n{current.upper()}:")
        print(
            f"  {record['product']:<18} {record['family']:<5} "
            f"{record['profile_id']}"
        )


def prompt(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        return input(f"{label}{suffix}: ").strip() or default
    except (EOFError, KeyboardInterrupt):
        raise RamdiskError("guided workflow cancelled")


def guide(args: argparse.Namespace) -> int:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise RamdiskError("ramdisk guide requires an interactive TTY")
    print("B34ST guided ramdisk maker / loader")
    print("This workflow packages prepared artifacts; it does not create Apple-signed files.")
    print("Physical loading requires a separately installed target-specific adapter.\n")
    product = args.product or prompt("Exact Apple product identifier", "iPhone12,1")
    os_version = args.os_version or prompt("Exact iOS/iPadOS/macOS version")
    if not os_version:
        raise RamdiskError("an exact OS version is required")
    build = args.build or prompt("Exact build identifier (recommended)")
    plan = make_plan(
        product=product,
        os_version=os_version,
        build=build or None,
        profile_path=args.profile,
    )
    print()
    print_plan(plan)
    if prompt("\nBuild a bundle now (y/N)", "N").lower() not in {"y", "yes"}:
        if args.evidence:
            write_json(args.evidence, plan)
        return 0
    namespace = argparse.Namespace(
        product=product,
        os_version=os_version,
        build=build or None,
        profile=args.profile,
        ramdisk=pathlib.Path(prompt("Prepared ramdisk path")),
        kernelcache=pathlib.Path(prompt("Prepared kernelcache path")),
        devicetree=pathlib.Path(prompt("Prepared DeviceTree path")),
        trustcache=None,
        ibss=None,
        ibec=None,
        iboot=None,
        bootlogo=None,
        restore_device_tree=None,
        component=[],
        output=pathlib.Path(
            prompt("Output bundle", f"build/ramdisk/{product}-{os_version}.fbrd")
        ),
        force=False,
    )
    for role in ("trustcache", "ibss", "ibec", "iboot", "bootlogo"):
        value = prompt(f"Optional {role} path (blank to skip)")
        if value:
            setattr(namespace, role, pathlib.Path(value))
    result = build_bundle(namespace)
    print(
        f"\nBuilt {result['path']} ({result['size']} bytes)\n"
        f"SHA-256: {result['sha256']}"
    )
    load_args = argparse.Namespace(
        bundle=pathlib.Path(result["path"]),
        adapter=args.adapter,
        ecid=args.ecid,
        execute=False,
        owner_authorization=None,
        confirm=None,
        timeout=args.timeout,
        evidence=args.evidence,
    )
    load_result = load_bundle(load_args)
    if args.evidence:
        write_json(args.evidence, load_result)
    print("\nLoad plan created. No device operation has run.")
    print(
        "To execute, run 'fbr34ker ramdisk load ... --execute' with the two "
        "authorization phrases shown by --help."
    )
    return 0


def add_target_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--product", required=True, help="exact Apple product identifier")
    parser.add_argument("--os-version", required=True, help="exact iOS/iPadOS/macOS version")
    parser.add_argument("--build", help="exact Apple build identifier")
    parser.add_argument("--profile", type=pathlib.Path, help="exact recovery profile")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            "Compatibility is exact-product/profile based. Physical bootability and "
            "OS/build support must be established by external-adapter evidence."
        ),
    )
    sub = root.add_subparsers(dest="command", required=True)
    targets = sub.add_parser("list-targets", help="list exact profiled products")
    targets.add_argument("--json", action="store_true")
    plan = sub.add_parser("plan", help="create a compatibility and readiness plan")
    add_target_arguments(plan)
    plan.add_argument("--json", action="store_true")
    plan.add_argument("--output", type=pathlib.Path)
    build = sub.add_parser("build", help="build a deterministic .fbrd bundle")
    add_target_arguments(build)
    build.add_argument("--ramdisk", type=pathlib.Path, required=True)
    build.add_argument("--kernelcache", type=pathlib.Path, required=True)
    build.add_argument("--devicetree", type=pathlib.Path, required=True)
    for role in OPTIONAL_ROLES:
        build.add_argument(f"--{role}", type=pathlib.Path)
    build.add_argument(
        "--component",
        action="append",
        help="additional adapter-specific ROLE=PATH component",
    )
    build.add_argument("--output", type=pathlib.Path, required=True)
    build.add_argument("--force", action="store_true")
    build.add_argument("--json", action="store_true")
    inspect = sub.add_parser("inspect", help="verify a bundle and every component")
    inspect.add_argument("bundle", type=pathlib.Path)
    inspect.add_argument("--json", action="store_true")
    load = sub.add_parser("load", help="plan or externally execute a ramdisk load")
    load.add_argument("bundle", type=pathlib.Path)
    load.add_argument("--adapter", help="external adapter command")
    load.add_argument("--ecid", help="bind the adapter request to one ECID")
    load.add_argument("--execute", action="store_true")
    load.add_argument("--owner-authorization")
    load.add_argument("--confirm")
    load.add_argument("--timeout", type=float, default=180.0)
    load.add_argument("--evidence", type=pathlib.Path)
    load.add_argument("--json", action="store_true")
    guided = sub.add_parser("guide", help="run the streamlined interactive workflow")
    guided.add_argument("--product")
    guided.add_argument("--os-version")
    guided.add_argument("--build")
    guided.add_argument("--profile", type=pathlib.Path)
    guided.add_argument("--adapter")
    guided.add_argument("--ecid")
    guided.add_argument("--timeout", type=float, default=180.0)
    guided.add_argument("--evidence", type=pathlib.Path)
    return root


def emit(value: dict[str, Any], json_mode: bool) -> None:
    if json_mode:
        print(json.dumps(value, indent=2, sort_keys=True))
    elif value["operation"] == "ramdisk-plan":
        print_plan(value)
    elif value["operation"] == "ramdisk-build":
        print(f"Built: {value['path']}")
        print(f"Components: {value['component_count']}")
        print(f"SHA-256: {value['sha256']}")
    elif value["operation"] == "ramdisk-inspect":
        print(f"FBRD verification: PASS")
        print(f"Target: {value['manifest']['target']['product']}")
        print(f"OS/build: {value['manifest']['os_version']} / {value['manifest'].get('build') or 'not recorded'}")
        print(f"Components: {value['component_count']}")
        print(f"SHA-256: {value['sha256']}")
    else:
        print(
            "Ramdisk load: "
            + ("adapter execution PASS" if value["executed"] else "PLAN ONLY")
        )
        print(f"Bundle SHA-256: {value['bundle']['sha256']}")
        if not value["executed"]:
            print("No data was sent to a device.")


def main(argv: Iterable[str] | None = None) -> int:
    args = parser().parse_args(list(argv) if argv is not None else None)
    try:
        if args.command == "list-targets":
            list_targets(args.json)
            return 0
        if args.command == "plan":
            value = make_plan(
                product=args.product,
                os_version=args.os_version,
                build=args.build,
                profile_path=args.profile,
            )
            if args.output:
                write_json(args.output, value)
            emit(value, args.json)
            return 0
        if args.command == "build":
            emit(build_bundle(args), args.json)
            return 0
        if args.command == "inspect":
            emit(inspect_bundle(args.bundle), args.json)
            return 0
        if args.command == "load":
            emit(load_bundle(args), args.json)
            return 0
        if args.command == "guide":
            return guide(args)
        raise RamdiskError(f"unknown command: {args.command}")
    except (RamdiskError, OSError) as exc:
        print(f"ramdisk error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
