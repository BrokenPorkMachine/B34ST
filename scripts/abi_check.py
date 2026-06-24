#!/usr/bin/env python3
"""Validate FBR34KER public interface versions and compatibility manifests."""
from __future__ import annotations
import argparse, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
HEADER = ROOT / "include/fbr34ker/abi.h"
DEFAULT_MANIFEST = ROOT / "abi/public-interfaces.json"
MACROS = {
    "fbdp": "FBR34KER_FBDP_PROTOCOL_VERSION",
    "handoff": "FBR34KER_HANDOFF_ABI_VERSION",
    "module_abi": "FBR34KER_MODULE_ABI_VERSION",
    "module_container": "FBR34KER_MODULE_FORMAT_ABI_VERSION",
    "fmbc": "FBR34KER_FMBC_BYTECODE_VERSION",
    "board_description": "FBR34KER_BOARD_DESCRIPTION_ABI_VERSION",
    "service_registry": "FBR34KER_SERVICE_REGISTRY_ABI_VERSION",
    "driver_manager": "FBR34KER_DRIVER_MANAGER_ABI_VERSION",
    "boot_evidence": "FBR34KER_BOOT_EVIDENCE_ABI_VERSION",
    "release_manifest": "FBR34KER_RELEASE_MANIFEST_SCHEMA_VERSION",
    "boot_image": "FBR34KER_BOOT_IMAGE_ABI_VERSION",
    "recovery_profile": "FBR34KER_RECOVERY_PROFILE_SCHEMA_VERSION",
    "first_stage_adapter": "FBR34KER_FIRST_STAGE_ADAPTER_ABI_VERSION",
    "bridge_protocol": "FBR34KER_BRIDGE_PROTOCOL_VERSION",
    "physical_session": "FBR34KER_PHYSICAL_SESSION_SCHEMA_VERSION",
    "physical_validation": "FBR34KER_PHYSICAL_VALIDATION_SCHEMA_VERSION",
}

class AbiError(ValueError): pass

def header_versions(path: pathlib.Path = HEADER) -> dict[str, int]:
    text = path.read_text(encoding="utf-8")
    result = {}
    for name, macro in MACROS.items():
        match = re.search(rf"^#define\s+{re.escape(macro)}\s+(\d+)U?\s*$", text, re.M)
        if not match: raise AbiError(f"missing ABI macro {macro}")
        result[name] = int(match.group(1))
    return result

def load_manifest(path: pathlib.Path) -> dict[str, object]:
    if path.stat().st_size > 64 * 1024: raise AbiError("ABI manifest exceeds 64 KiB")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise AbiError("unsupported ABI manifest schema")
    interfaces = value.get("interfaces")
    if not isinstance(interfaces, dict) or set(interfaces) != set(MACROS):
        raise AbiError("ABI manifest has missing or unknown interfaces")
    if not all(type(v) is int and 1 <= v <= 65535 for v in interfaces.values()):
        raise AbiError("interface versions must be integers in 1..65535")
    return value

def compare(expected: dict[str, int], actual: dict[str, int], exact: bool) -> list[str]:
    errors=[]
    for name in sorted(expected):
        if exact and actual[name] != expected[name]:
            errors.append(f"{name}: expected {expected[name]}, got {actual[name]}")
        elif not exact and actual[name] < expected[name]:
            errors.append(f"{name}: requires >= {expected[name]}, got {actual[name]}")
    return errors

def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", nargs="?", type=pathlib.Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--against", type=pathlib.Path)
    parser.add_argument("--json", action="store_true")
    args=parser.parse_args(argv)
    try:
        declared=load_manifest(args.manifest)["interfaces"]
        compiled=header_versions()
        errors=compare(declared, compiled, True)
        if args.against:
            required=load_manifest(args.against)["interfaces"]
            errors += compare(required, declared, False)
        payload={"passed": not errors, "interfaces": declared, "compiled": compiled, "errors": errors}
        if args.json: print(json.dumps(payload, sort_keys=True))
        elif errors:
            for error in errors: print(f"ABI ERROR: {error}", file=sys.stderr)
        else: print("public ABI compatibility check passed")
        return 0 if not errors else 1
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        if args.json: print(json.dumps({"passed":False,"errors":[str(exc)]}, sort_keys=True))
        else: print(f"ABI ERROR: {exc}", file=sys.stderr)
        return 2
if __name__ == "__main__": raise SystemExit(main())
