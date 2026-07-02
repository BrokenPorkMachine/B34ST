#!/usr/bin/env python3

"""Contract-only B34ST tether-adapter example.
# SPDX-License-Identifier: BSD-2-Clause

This program validates and demonstrates the JSON boundary. It deliberately
does not communicate with a device or report a successful downgrade.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


def _error(message: str, *, request: dict[str, Any] | None = None) -> int:
    response: dict[str, Any] = {
        "ok": False,
        "adapter_kind": "contract-example",
        "performs_device_io": False,
        "execution_supported": False,
        "error": message,
    }
    if request is not None:
        arguments = request.get("arguments")
        if isinstance(arguments, dict):
            response["validated_target"] = {
                key: arguments.get(key)
                for key in ("product", "version", "build", "ecid")
            }
    print(json.dumps(response, sort_keys=True))
    return 2


def _validate_request(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("request must be a JSON object")
    if set(value) != {"schema_version", "operation", "arguments"}:
        raise ValueError("request fields do not match adapter schema v1")
    if value.get("schema_version") != 1:
        raise ValueError("schema_version must be 1")
    if value.get("operation") != "tethered-downgrade":
        raise ValueError("operation must be tethered-downgrade")
    arguments = value.get("arguments")
    if not isinstance(arguments, dict):
        raise ValueError("arguments must be a JSON object")
    required = {
        "product",
        "ipsw_path",
        "ipsw_sha256",
        "version",
        "build",
        "tethered",
    }
    allowed = required | {"ecid"}
    if missing := sorted(required - set(arguments)):
        raise ValueError(f"missing required arguments: {', '.join(missing)}")
    if unknown := sorted(set(arguments) - allowed):
        raise ValueError(f"unknown arguments: {', '.join(unknown)}")
    for name in ("product", "ipsw_path", "version", "build"):
        if not isinstance(arguments[name], str) or not arguments[name]:
            raise ValueError(f"{name} must be a non-empty string")
    digest = arguments["ipsw_sha256"]
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ValueError("ipsw_sha256 must be 64 lowercase hexadecimal characters")
    ecid = arguments.get("ecid")
    if ecid is not None and (not isinstance(ecid, str) or not ecid):
        raise ValueError("ecid must be null or a non-empty string")
    if arguments["tethered"] is not True:
        raise ValueError("tethered must be true")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--describe",
        action="store_true",
        help="describe the example without reading a request",
    )
    arguments = parser.parse_args(argv)
    if arguments.describe:
        print(
            json.dumps(
                {
                    "adapter_kind": "contract-example",
                    "device_support": [],
                    "performs_device_io": False,
                    "execution_supported": False,
                    "purpose": (
                        "Demonstrate request validation and response formatting; "
                        "replace with a reviewed target-specific backend."
                    ),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    try:
        request = _validate_request(json.load(sys.stdin))
    except (json.JSONDecodeError, ValueError) as exc:
        return _error(f"invalid B34ST adapter request: {exc}")
    return _error(
        "contract example only; no device-side backend is implemented",
        request=request,
    )


if __name__ == "__main__":
    raise SystemExit(main())
