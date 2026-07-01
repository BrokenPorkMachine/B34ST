#!/usr/bin/env python3
"""Build, inspect, plan, and externally load bounded FBR34KER ramdisk bundles."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import plistlib
import re
import shlex
import shutil
import subprocess
import sys
import zipfile
from typing import Any, Iterable

try:
    from .boot_image import BootImageError, load_profile
    from .ipsw_manager import (
        DEFAULT_CATALOG,
        IPSWError,
        download_firmware,
        fetch_catalog,
        inspect_ipsw as ipsw_inspect_ipsw,
        select_firmware,
    )
except ImportError:
    from boot_image import BootImageError, load_profile
    from ipsw_manager import (
        DEFAULT_CATALOG,
        IPSWError,
        download_firmware,
        fetch_catalog,
        inspect_ipsw as ipsw_inspect_ipsw,
        select_firmware,
    )

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
IPSW_ROLE_MAP: dict[str, str] = {
    "RestoreRamDisk": "ramdisk",
    "KernelCache": "kernelcache",
    "DeviceTree": "devicetree",
    "TrustCache": "trustcache",
    "iBSS": "ibss",
    "iBEC": "ibec",
    "iBoot": "iboot",
    "AppleLogo": "bootlogo",
    "RestoreDeviceTree": "restore-device-tree",
}
IPSW_MANDATORY_KEYS = {"RestoreRamDisk", "KernelCache", "DeviceTree"}


class RamdiskError(ValueError):
    pass


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ipsw_suggest_product(filename: str) -> str | None:
    match = re.search(
        r"((?:iPhone|iPad|Mac|iMac)[A-Za-z]*\d+[_,]\d+)",
        filename.replace("-", "_"),
    )
    if match:
        return match.group(1).replace("_", ",")
    return None


def _human_size(bytes_value: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(bytes_value) < 1024:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024
    return f"{bytes_value:.1f} TB"


def _read_build_manifest(
    ipsw_path: pathlib.Path,
) -> tuple[dict[str, Any], str, str]:
    try:
        with zipfile.ZipFile(ipsw_path, "r") as archive:
            names = set(archive.namelist())
            if "BuildManifest.plist" not in names:
                raise RamdiskError("IPSW does not contain BuildManifest.plist")
            try:
                manifest = plistlib.loads(archive.read("BuildManifest.plist"))
            except (plistlib.InvalidFileException, KeyError) as exc:
                raise RamdiskError(f"invalid BuildManifest.plist: {exc}") from exc
            if not isinstance(manifest, dict):
                raise RamdiskError("BuildManifest.plist is not a dictionary")
            version = manifest.get("ProductVersion")
            build = manifest.get("ProductBuildVersion")
            if (
                not isinstance(version, str)
                or not version
                or not isinstance(build, str)
                or not build
            ):
                raise RamdiskError(
                    "BuildManifest.plist missing ProductVersion or ProductBuildVersion"
                )
            return manifest, version, build
    except (OSError, zipfile.BadZipFile) as exc:
        raise RamdiskError(f"cannot open IPSW: {exc}") from exc


def _resolve_build_identity(manifest: dict[str, Any], product: str) -> dict[str, Any]:
    identities = manifest.get("BuildIdentities")
    if not isinstance(identities, list) or not identities:
        raise RamdiskError("BuildManifest.plist has no BuildIdentities")
    for identity in identities:
        if not isinstance(identity, dict):
            continue
        products = identity.get("Info", {}).get(
            "SupportedProductTypes"
        ) or identity.get("Info", {}).get("ProductType")
        if isinstance(products, list) and product in products:
            return identity
        if products == product:
            return identity
    raise RamdiskError(f"no BuildIdentity in IPSW matches product {product}")


def _extract_ipsw_component(
    archive: zipfile.ZipFile,
    build_identity: dict[str, Any],
    manifest_key: str,
    output_dir: pathlib.Path,
) -> pathlib.Path | None:
    entry = build_identity.get("Manifest", {}).get(manifest_key)
    if not isinstance(entry, dict):
        return None
    info = entry.get("Info")
    if not isinstance(info, dict):
        return None
    path_str = info.get("Path")
    if not isinstance(path_str, str) or not path_str:
        return None
    clean = pathlib.PurePosixPath(path_str)
    if ".." in clean.parts:
        raise RamdiskError(f"unsafe path in BuildIdentity manifest: {path_str}")
    try:
        info_zip = archive.getinfo(path_str)
    except KeyError:
        return None
    if info_zip.is_dir():
        raise RamdiskError(f"component path is a directory: {path_str}")
    output_path = output_dir / clean.name
    with archive.open(info_zip) as src, output_path.open("wb") as dst:
        for chunk in iter(lambda: src.read(1024 * 1024), b""):
            dst.write(chunk)
    return output_path


def extract_ipsw_components(
    ipsw_path: pathlib.Path,
    product: str,
    output_dir: pathlib.Path,
) -> dict[str, pathlib.Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest, version, build = _read_build_manifest(ipsw_path)
    identity = _resolve_build_identity(manifest, product)
    extracted: dict[str, pathlib.Path] = {}
    with zipfile.ZipFile(ipsw_path, "r") as archive:
        for manifest_key, role in IPSW_ROLE_MAP.items():
            _path = _extract_ipsw_component(archive, identity, manifest_key, output_dir)
            if _path is not None:
                size = _human_size(_path.stat().st_size)
                print(f"  [{role:<12}] {_path.name}  ({size})")
                extracted[role] = _path
    missing = IPSW_MANDATORY_KEYS - set(
        key for key in IPSW_ROLE_MAP if extracted.get(IPSW_ROLE_MAP[key])
    )
    if missing:
        raise RamdiskError(
            f"IPSW missing mandatory component(s): {', '.join(sorted(missing))}"
        )
    return extracted


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
        if (
            profile.get("requires_exact_product")
            and products
            and all(
                str(product).startswith(("iPhone", "iPad", "Mac", "iMac"))
                for product in products
            )
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
        raise RamdiskError("missing required component(s): " + ", ".join(missing))
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
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    temporary = output.with_name(output.name + ".tmp")
    try:
        with zipfile.ZipFile(
            temporary, "w", allowZip64=True, strict_timestamps=True
        ) as bundle:
            bundle.writestr(zip_info("manifest.json"), manifest_bytes)
            for item in components:
                stream_into_zip(bundle, zip_info(item["archive_path"]), item["source"])
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
    except (
        UnicodeError,
        json.JSONDecodeError,
        RuntimeError,
        NotImplementedError,
    ) as exc:
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
    if any(c in raw for c in ";|&$`\n\r()"):
        raise RamdiskError("adapter command contains shell metacharacters")
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
        raise RamdiskError("execution requires --adapter or B34ST_RAMDISK_ADAPTER")
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
        raise RamdiskError("adapter response must be schema_version 1 with ok=true")
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
        "physical_execution_verified": bool(records)
        and all(item["physical_execution_verified"] for item in records),
        "os_version_policy": "exact adapter support and evidence required",
        "target_count": len(records),
        "targets": records,
    }
    if json_mode:
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    print("Profiled ramdisk targets")
    print(
        "Status: simulation-validated; external adapter and exact OS/build support required"
    )
    current = None
    for record in records:
        if record["device_class"] != current:
            current = record["device_class"]
            print(f"\n{current.upper()}:")
        print(f"  {record['product']:<18} {record['family']:<5} {record['profile_id']}")


def _ipsw_lookup(args: argparse.Namespace) -> dict[str, Any]:
    catalog = fetch_catalog(args.product, args.catalog, args.timeout)
    version = getattr(args, "version", None) or getattr(args, "os_version", None)
    return select_firmware(
        catalog,
        version=version,
        build=args.build,
        signed_only=args.signed_only,
    )


def ipsw_catalog_command(args: argparse.Namespace) -> dict[str, Any]:
    catalog = fetch_catalog(args.product, args.catalog, args.timeout)
    if args.signed_only:
        catalog["firmwares"] = [f for f in catalog["firmwares"] if f["signed"]]
    elif args.unsigned_only:
        catalog["firmwares"] = [f for f in catalog["firmwares"] if not f["signed"]]
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "operation": "ramdisk-ipsw-catalog",
        "product": args.product,
        "firmware_count": len(catalog["firmwares"]),
        "firmwares": catalog["firmwares"],
    }
    return result


def ipsw_download_command(args: argparse.Namespace) -> dict[str, Any]:
    record = _ipsw_lookup(args)
    args.output_dir = args.output_dir.expanduser()
    hsize = _human_size(record["size"])
    print(f"Downloading {record['version']} ({record['build']}) — {hsize}...")
    output = download_firmware(record, args.output_dir)
    info = ipsw_inspect_ipsw(output)
    print(f"Saved to {output}")
    return {
        "schema_version": SCHEMA_VERSION,
        "operation": "ramdisk-ipsw-download",
        "product": args.product,
        "version": record["version"],
        "build": record["build"],
        "path": str(output),
        "size": info["size"],
        "sha256": info["sha256"],
        "signed": record["signed"],
    }


def ipsw_extract_command(args: argparse.Namespace) -> dict[str, Any]:
    args.ipsw = args.ipsw.expanduser()
    info = ipsw_inspect_ipsw(args.ipsw)
    products = [p for p in info.get("supported_products", []) if isinstance(p, str)]
    product = args.product or (products[0] if len(products) == 1 else None)
    if not product:
        suggested = _ipsw_suggest_product(args.ipsw.name)
        hint = f" try --product {suggested}" if suggested else ""
        raise RamdiskError(
            f"could not determine product from IPSW; specify --product.{hint}"
        )
    if products and product not in products:
        raise RamdiskError(f"product {product} is not in IPSW supported products")
    if args.output_dir is None:
        default_dir = args.ipsw.with_suffix("")
        # always resolve to absolute to avoid confusion
        output_dir = pathlib.Path(default_dir).resolve()
    else:
        output_dir = args.output_dir.resolve()
    print(f"Extracting {product} components from {args.ipsw.name}...")
    extracted = extract_ipsw_components(args.ipsw, product, output_dir)
    print(f"Done — {len(extracted)} components extracted to {output_dir}")
    return {
        "schema_version": SCHEMA_VERSION,
        "operation": "ramdisk-ipsw-extract",
        "product": product,
        "version": info.get("product_version"),
        "build": info.get("product_build"),
        "output_dir": str(output_dir),
        "components": {role: str(path) for role, path in sorted(extracted.items())},
    }


def ipsw_build_command(args: argparse.Namespace) -> dict[str, Any]:
    record = _ipsw_lookup(args)
    download_dir = args.download_dir.expanduser().resolve()
    output = download_firmware(record, download_dir)
    info = ipsw_inspect_ipsw(output)
    extract_dir = output.with_suffix("")
    extracted = extract_ipsw_components(output, args.product, extract_dir)
    for role, path in extracted.items():
        attr = role.replace("-", "_")
        if not getattr(args, attr, None):
            setattr(args, attr, path)
    os_version = args.os_version or info.get("product_version") or record["version"]
    build = args.build or info.get("product_build") or record["build"]
    build_args = argparse.Namespace(
        product=args.product,
        os_version=os_version,
        build=build,
        profile=args.profile,
        ramdisk=args.ramdisk or extracted.get("ramdisk"),
        kernelcache=args.kernelcache or extracted.get("kernelcache"),
        devicetree=args.devicetree or extracted.get("devicetree"),
        trustcache=args.trustcache or extracted.get("trustcache"),
        ibss=args.ibss or extracted.get("ibss"),
        ibec=args.ibec or extracted.get("ibec"),
        iboot=args.iboot or extracted.get("iboot"),
        bootlogo=args.bootlogo or extracted.get("bootlogo"),
        restore_device_tree=args.restore_device_tree
        or extracted.get("restore-device-tree"),
        component=getattr(args, "component", []) or [],
        output=args.output.resolve(),
        force=args.force,
    )
    bundle = build_bundle(build_args)
    return {
        "schema_version": SCHEMA_VERSION,
        "operation": "ramdisk-ipsw-build",
        "product": args.product,
        "version": os_version,
        "build": build,
        "ipsw": {
            "path": str(output),
            "size": info["size"],
            "sha256": info["sha256"],
        },
        "extracted_components": {
            role: str(path) for role, path in sorted(extracted.items())
        },
        "bundle": bundle,
    }


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
    print(
        "This workflow packages prepared artifacts; it does not create Apple-signed files."
    )
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
    source = prompt(
        "Component source: local files (L) or extract from IPSW (I)", "L"
    ).lower()
    namespace = argparse.Namespace(
        product=product,
        os_version=os_version,
        build=build or None,
        profile=args.profile,
        ramdisk=None,
        kernelcache=None,
        devicetree=None,
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
    if source in {"i", "ipsw"}:
        ipsw_path_str = prompt("Local IPSW path")
        if not ipsw_path_str:
            raise RamdiskError("an IPSW path is required for IPSW extraction")
        ipsw_path = pathlib.Path(ipsw_path_str).expanduser()
        print(f"\nExtracting components from IPSW for {product}...")
        extracted = extract_ipsw_components(
            ipsw_path, product, ipsw_path.with_suffix("")
        )
        namespace.ramdisk = extracted["ramdisk"]
        namespace.kernelcache = extracted["kernelcache"]
        namespace.devicetree = extracted["devicetree"]
        for role in ("trustcache", "ibss", "ibec", "iboot", "bootlogo"):
            if role in extracted:
                setattr(namespace, role, extracted[role])
        print(f"Extracted {len(extracted)} components to {ipsw_path.with_suffix('')}")
    else:
        namespace.ramdisk = pathlib.Path(prompt("Prepared ramdisk path"))
        namespace.kernelcache = pathlib.Path(prompt("Prepared kernelcache path"))
        namespace.devicetree = pathlib.Path(prompt("Prepared DeviceTree path"))
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
    parser.add_argument(
        "--product", required=True, help="exact Apple product identifier"
    )
    parser.add_argument(
        "--os-version", required=True, help="exact iOS/iPadOS/macOS version"
    )
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
    ipsw_group = sub.add_parser(
        "ipsw",
        help="IPSW catalog, download, extract, and bundle build",
        description="End-to-end IPSW workflow: list firmwares, download, extract components, and build an FBRD ramdisk bundle from extracted files.",
    )
    ipsw_sub = ipsw_group.add_subparsers(dest="ipsw_command", required=True)
    catalog = ipsw_sub.add_parser(
        "catalog", help="list available firmwares for a product"
    )
    catalog.add_argument("--product", required=True)
    catalog_filter = catalog.add_mutually_exclusive_group()
    catalog_filter.add_argument("--signed-only", action="store_true")
    catalog_filter.add_argument("--unsigned-only", action="store_true")
    catalog.add_argument("--catalog", default=DEFAULT_CATALOG)
    catalog.add_argument("--timeout", type=float, default=60.0)
    catalog.add_argument("--json", action="store_true")
    download = ipsw_sub.add_parser("download", help="download an IPSW for a product")
    download.add_argument("--product", required=True)
    download.add_argument("--version")
    download.add_argument("--build")
    download.add_argument("--signed-only", action="store_true")
    download.add_argument(
        "--output-dir", type=pathlib.Path, default=pathlib.Path("downloads/ipsw")
    )
    download.add_argument("--catalog", default=DEFAULT_CATALOG)
    download.add_argument("--timeout", type=float, default=60.0)
    download.add_argument("--json", action="store_true")
    extract = ipsw_sub.add_parser(
        "extract", help="extract components from a local IPSW"
    )
    extract.add_argument("ipsw", type=pathlib.Path)
    extract.add_argument(
        "--product", help="product identifier (auto-detected when unambiguous)"
    )
    extract.add_argument(
        "--output-dir",
        type=pathlib.Path,
        default=None,
        help="output directory (default: IPSW filename stem)",
    )
    extract.add_argument("--json", action="store_true")
    ipsw_build = ipsw_sub.add_parser(
        "build", help="download IPSW, extract components, and build FBRD bundle"
    )
    ipsw_build.add_argument(
        "--product", required=True, help="exact Apple product identifier"
    )
    ipsw_build.add_argument(
        "--os-version",
        "--version",
        dest="os_version",
        help="exact OS version (auto-detected from IPSW when omitted)",
    )
    ipsw_build.add_argument(
        "--build",
        help="exact Apple build identifier (auto-detected from IPSW when omitted)",
    )
    ipsw_build.add_argument(
        "--profile", type=pathlib.Path, help="exact recovery profile"
    )
    ipsw_build.add_argument("--signed-only", action="store_true")
    ipsw_build.add_argument(
        "--timeout",
        type=float,
        default=180.0,
        help="catalog fetch and download timeout",
    )
    ipsw_build.add_argument("--catalog", default=DEFAULT_CATALOG)
    ipsw_build.add_argument(
        "--download-dir", type=pathlib.Path, default=pathlib.Path("downloads/ipsw")
    )
    ipsw_build.add_argument("--output", type=pathlib.Path, required=True)
    ipsw_build.add_argument("--force", action="store_true")
    ipsw_build.add_argument("--json", action="store_true")
    for role in CORE_ROLES + OPTIONAL_ROLES:
        ipsw_build.add_argument(f"--{role}", type=pathlib.Path)
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
        print("FBRD verification: PASS")
        print(f"Target: {value['manifest']['target']['product']}")
        print(
            f"OS/build: {value['manifest']['os_version']} / {value['manifest'].get('build') or 'not recorded'}"
        )
        print(f"Components: {value['component_count']}")
        print(f"SHA-256: {value['sha256']}")
    elif value["operation"] == "ramdisk-ipsw-catalog":
        signed_count = sum(1 for fw in value["firmwares"] if fw["signed"])
        unsigned_count = len(value["firmwares"]) - signed_count
        print(
            f"Firmware catalog for {value['product']}: {len(value['firmwares'])} entries"
        )
        if unsigned_count:
            print(f"  {signed_count} signed, {unsigned_count} unsigned")
        for fw in value["firmwares"]:
            status = "SIGNED" if fw["signed"] else "unsigned"
            print(f"  [{status}] iOS {fw['version']} ({fw['build']})")
    elif value["operation"] == "ramdisk-ipsw-download":
        print(
            f"Downloaded IPSW for {value['product']} iOS {value['version']} ({value['build']})"
        )
        print(f"Path: {value['path']}  ({_human_size(value['size'])})")
        print(f"SHA-256: {value['sha256']}")
    elif value["operation"] == "ramdisk-ipsw-extract":
        print(
            f"Extracted {len(value['components'])} components from IPSW for {value['product']}"
        )
        print(f"Output: {value['output_dir']}")
        for role, path_str in sorted(value["components"].items()):
            p = pathlib.Path(path_str)
            sz = _human_size(p.stat().st_size) if p.is_file() else "?"
            print(f"  [{role:<12}] {p.name}  ({sz})")
    elif value["operation"] == "ramdisk-ipsw-build":
        print(
            f"IPSW build for {value['product']} iOS {value['version']} ({value['build']})"
        )
        print(f"IPSW: {value['ipsw']['path']}  ({_human_size(value['ipsw']['size'])})")
        print(f"Bundle: {value['bundle']['path']}")
        print(f"Bundle SHA-256: {value['bundle']['sha256']}")
        for role, path in sorted(value["extracted_components"].items()):
            p = pathlib.Path(path)
            sz = _human_size(p.stat().st_size) if p.is_file() else "?"
            print(f"  [{role:<12}] {p.name}  ({sz})")
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
        if args.command == "ipsw":
            return main_ipsw(args)
        raise RamdiskError(f"unknown command: {args.command}")
    except (RamdiskError, OSError, IPSWError) as exc:
        kind = "ipsw error" if isinstance(exc, IPSWError) else "ramdisk error"
        print(f"{kind}: {exc}", file=sys.stderr)
        return 2


def main_ipsw(args: argparse.Namespace) -> int:
    try:
        if args.ipsw_command == "catalog":
            emit(ipsw_catalog_command(args), args.json)
            return 0
        if args.ipsw_command == "download":
            emit(ipsw_download_command(args), args.json)
            return 0
        if args.ipsw_command == "extract":
            emit(ipsw_extract_command(args), args.json)
            return 0
        if args.ipsw_command == "build":
            emit(ipsw_build_command(args), args.json)
            return 0
        raise RamdiskError(f"unknown ipsw command: {args.ipsw_command}")
    except (RamdiskError, IPSWError, OSError) as exc:
        kind = "ipsw error" if isinstance(exc, IPSWError) else "ramdisk error"
        print(f"{kind}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
