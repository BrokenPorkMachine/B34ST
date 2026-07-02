#!/usr/bin/env python3

"""Board-profile validation and FBR34KER hardware compatibility reporting."""
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

import json
import pathlib
import re
from dataclasses import dataclass
from typing import Any

PROFILE_SCHEMA_VERSION = 1
ALLOWED_CONSOLES = {
    "any",
    "callback",
    "pl011",
    "memory-ring",
    "framebuffer",
    "semihosting",
    "none",
}
ALLOWED_INTERRUPTS = {"any", "gicv2", "gicv3", "callback", "polling", "none"}
ALLOWED_TIMERS = {"arm-generic", "callback", "any", "none"}
ALLOWED_SERVICES = {
    "console_write",
    "console_read",
    "console_flush",
    "monotonic_time",
    "power",
    "framebuffer",
    "framebuffer_flush",
    "interrupt_controller",
    "watchdog_configure",
    "watchdog_kick",
    "device_tree",
    "memory_map",
}
VALID_STATES = {"PASS", "PARTIAL", "UNSUPPORTED", "NOT TESTED", "LOCKED", "FAIL"}


class HardwareProfileError(ValueError):
    pass


@dataclass(frozen=True)
class MatrixEntry:
    feature: str
    state: str
    detail: str


def template_profile() -> dict[str, Any]:
    return {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "name": "example-arm64-board",
        "architecture": "arm64",
        "expected_el": 1,
        "console": "callback",
        "interrupt_controller": "gicv3",
        "timer": "arm-generic",
        "framebuffer": None,
        "required_services": ["console_write", "monotonic_time", "memory_map"],
        "notes": "Replace example values with the authorized target's documented contract.",
    }


def _require_string(document: dict[str, Any], key: str, *, max_length: int = 96) -> str:
    value = document.get(key)
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        raise HardwareProfileError(
            f"{key} must be a non-empty string of at most {max_length} characters"
        )
    return value.strip()


def validate_profile(document: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise HardwareProfileError("profile root must be a JSON object")
    unknown = set(document) - {
        "schema_version",
        "name",
        "architecture",
        "expected_el",
        "console",
        "interrupt_controller",
        "timer",
        "framebuffer",
        "required_services",
        "notes",
        "review",
    }
    if unknown:
        raise HardwareProfileError(
            f"unknown profile field(s): {', '.join(sorted(unknown))}"
        )
    schema = document.get("schema_version", PROFILE_SCHEMA_VERSION)
    if schema != PROFILE_SCHEMA_VERSION:
        raise HardwareProfileError(f"unsupported profile schema_version {schema!r}")
    name = _require_string(document, "name")
    architecture = _require_string(document, "architecture", max_length=16).lower()
    if architecture != "arm64":
        raise HardwareProfileError("architecture must be 'arm64'")
    expected_el = document.get("expected_el")
    if (
        not isinstance(expected_el, int)
        or isinstance(expected_el, bool)
        or expected_el not in range(4)
    ):
        raise HardwareProfileError("expected_el must be an integer from 0 through 3")
    console = _require_string(document, "console", max_length=32).lower()
    if console not in ALLOWED_CONSOLES:
        raise HardwareProfileError(f"unsupported console value {console!r}")
    interrupts = _require_string(
        document, "interrupt_controller", max_length=32
    ).lower()
    if interrupts not in ALLOWED_INTERRUPTS:
        raise HardwareProfileError(
            f"unsupported interrupt_controller value {interrupts!r}"
        )
    timer = _require_string(document, "timer", max_length=32).lower()
    if timer not in ALLOWED_TIMERS:
        raise HardwareProfileError(f"unsupported timer value {timer!r}")
    framebuffer = document.get("framebuffer")
    if framebuffer is not None:
        if not isinstance(framebuffer, dict):
            raise HardwareProfileError("framebuffer must be null or an object")
        unknown_fb = set(framebuffer) - {
            "required",
            "pixel_formats",
            "minimum_width",
            "minimum_height",
        }
        if unknown_fb:
            raise HardwareProfileError(
                f"unknown framebuffer field(s): {', '.join(sorted(unknown_fb))}"
            )
        required = framebuffer.get("required", False)
        if not isinstance(required, bool):
            raise HardwareProfileError("framebuffer.required must be boolean")
        pixel_formats = framebuffer.get("pixel_formats", [])
        if not isinstance(pixel_formats, list) or not all(
            isinstance(item, str) for item in pixel_formats
        ):
            raise HardwareProfileError(
                "framebuffer.pixel_formats must be a string list"
            )
        minimum_width = framebuffer.get("minimum_width", 0)
        minimum_height = framebuffer.get("minimum_height", 0)
        if (
            not isinstance(minimum_width, int)
            or minimum_width < 0
            or minimum_width > 65535
        ):
            raise HardwareProfileError("framebuffer.minimum_width must be 0..65535")
        if (
            not isinstance(minimum_height, int)
            or minimum_height < 0
            or minimum_height > 65535
        ):
            raise HardwareProfileError("framebuffer.minimum_height must be 0..65535")
        framebuffer = {
            "required": required,
            "pixel_formats": sorted(set(item.upper() for item in pixel_formats)),
            "minimum_width": minimum_width,
            "minimum_height": minimum_height,
        }
    services = document.get("required_services", [])
    if not isinstance(services, list) or not all(
        isinstance(item, str) for item in services
    ):
        raise HardwareProfileError("required_services must be a string list")
    normalized_services = sorted(set(item.strip().lower() for item in services))
    unknown_services = set(normalized_services) - ALLOWED_SERVICES
    if unknown_services:
        raise HardwareProfileError(
            f"unknown required service(s): {', '.join(sorted(unknown_services))}"
        )
    notes = document.get("notes", "")
    if not isinstance(notes, str) or len(notes) > 1024:
        raise HardwareProfileError("notes must be a string of at most 1024 characters")
    review = document.get("review")
    if review is not None:
        if not isinstance(review, dict):
            raise HardwareProfileError("review must be null or an object")
        allowed_review = {
            "source",
            "compatibility_result",
            "observed",
            "supported_services",
            "untested_services",
        }
        unknown_review = set(review) - allowed_review
        if unknown_review:
            raise HardwareProfileError(
                f"unknown review field(s): {', '.join(sorted(unknown_review))}"
            )
        observed = review.get("observed", {})
        if not isinstance(observed, dict) or not all(
            isinstance(k, str) and isinstance(v, str) and v in VALID_STATES
            for k, v in observed.items()
        ):
            raise HardwareProfileError(
                "review.observed must map feature names to valid states"
            )
        for key in ("supported_services", "untested_services"):
            values = review.get(key, [])
            if not isinstance(values, list) or not all(
                isinstance(item, str) for item in values
            ):
                raise HardwareProfileError(f"review.{key} must be a string list")
        review = {
            "source": str(review.get("source", "unknown"))[:128],
            "compatibility_result": str(
                review.get("compatibility_result", "partial")
            ).lower(),
            "observed": dict(sorted(observed.items())),
            "supported_services": sorted(set(review.get("supported_services", []))),
            "untested_services": sorted(set(review.get("untested_services", []))),
        }
    return {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "name": name,
        "architecture": architecture,
        "expected_el": expected_el,
        "console": console,
        "interrupt_controller": interrupts,
        "timer": timer,
        "framebuffer": framebuffer,
        "required_services": normalized_services,
        "notes": notes,
        "review": review,
    }


def load_profile(path: pathlib.Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HardwareProfileError(f"unable to read profile {path}: {exc}") from exc
    return validate_profile(document)


def write_profile_template(path: pathlib.Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(template_profile(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _diagnostic_directory(path: pathlib.Path) -> pathlib.Path:
    if path.is_dir():
        return path
    if path.name == "summary.json":
        return path.parent
    raise HardwareProfileError("diagnostics must be a directory or its summary.json")


def _read(directory: pathlib.Path, name: str) -> str:
    path = directory / f"{name}.txt"
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _entry(feature: str, state: str, detail: str) -> MatrixEntry:
    if state not in VALID_STATES:
        raise HardwareProfileError(f"invalid matrix state {state}")
    return MatrixEntry(feature=feature, state=state, detail=detail)


def _detect_console(text: str) -> str:
    lower = text.lower()
    if "callback" in lower:
        return "callback"
    if "pl011" in lower:
        return "pl011"
    if "framebuffer" in lower and "enabled" in lower:
        return "framebuffer"
    if "semihosting" in lower and "mirrored" in lower:
        return "semihosting"
    if "memory diagnostic ring only" in lower or "memory ring" in lower:
        return "memory-ring"
    return "none"


def _detect_interrupt(text: str) -> str:
    lower = text.lower()
    if "gicv3" in lower:
        return "gicv3"
    if "gicv2" in lower:
        return "gicv2"
    if "loader callbacks" in lower:
        return "callback"
    if "polling-only" in lower:
        return "polling"
    return "none"


def _service_supported(service: str, texts: dict[str, str]) -> bool:
    services = texts.get("services", "").lower()
    probes = {
        "console_write": "console output: yes",
        "console_read": "console input: yes",
        "console_flush": "console flush: yes",
        "monotonic_time": "timer: yes",
        "power": "power actions: yes",
        "framebuffer": "framebuffer: yes",
        "framebuffer_flush": "framebuffer flush: yes",
        "interrupt_controller": "interrupt controller: yes",
        "watchdog_configure": "watchdog configure: yes",
        "watchdog_kick": "watchdog kick: yes",
        "device_tree": "fdt:" if texts.get("device-tree-summary") else "",
        "memory_map": "memory map: ok" if texts.get("memory-check") else "",
    }
    needle = probes.get(service, "")
    if service == "device_tree":
        return "fdt:" in texts.get("device-tree-summary", "").lower()
    if service == "memory_map":
        return "memory map: ok" in texts.get("memory-check", "").lower()
    return bool(needle and needle in services)


def check_profile(profile: dict[str, Any], diagnostics: pathlib.Path) -> dict[str, Any]:
    profile = validate_profile(profile)
    directory = _diagnostic_directory(diagnostics)
    names = [
        "platform-info",
        "exception-level",
        "system-registers",
        "handoff-info",
        "services",
        "console-services",
        "memory-check",
        "device-tree-summary",
        "timer-test",
        "irq-controller",
        "watchdog-services",
        "framebuffer-info",
        "probe-status",
        "compatibility",
        "boot-modules",
    ]
    texts = {name: _read(directory, name) for name in names}
    entries: list[MatrixEntry] = []

    handoff = texts["handoff-info"]
    entries.append(
        _entry(
            "Boot handoff",
            "PASS" if "Version:" in handoff else "FAIL",
            "validated handoff metadata present"
            if "Version:" in handoff
            else "no active handoff",
        )
    )

    el_match = re.search(
        r"EL([0-3])", texts["exception-level"] or texts["platform-info"]
    )
    if el_match:
        observed_el = int(el_match.group(1))
        entries.append(
            _entry(
                "Exception level",
                "PASS" if observed_el == profile["expected_el"] else "FAIL",
                f"expected EL{profile['expected_el']}, observed EL{observed_el}",
            )
        )
    else:
        entries.append(
            _entry(
                "Exception level", "NOT TESTED", "no parseable exception-level record"
            )
        )

    detected_console = _detect_console(texts["console-services"])
    expected_console = profile["console"]
    console_ok = expected_console == "any" or detected_console == expected_console
    if expected_console == "none":
        console_state = "PASS" if detected_console == "none" else "PARTIAL"
    elif detected_console == "none" or not console_ok:
        console_state = "FAIL"
    else:
        console_state = "PASS"
    entries.append(
        _entry(
            "Console output",
            console_state,
            f"expected {expected_console}, observed {detected_console}",
        )
    )

    console_input = "console input: yes" in texts["services"].lower()
    input_required = "console_read" in profile["required_services"]
    entries.append(
        _entry(
            "Console input",
            "PASS" if console_input else ("FAIL" if input_required else "UNSUPPORTED"),
            "loader/platform input service"
            if console_input
            else "no input service reported",
        )
    )

    timer_text = texts["timer-test"].lower()
    if profile["timer"] == "none":
        timer_state = "PASS" if not timer_text else "PARTIAL"
    else:
        timer_state = "PASS" if "timer-test: frequency=" in timer_text else "FAIL"
    entries.append(_entry("Monotonic timer", timer_state, profile["timer"]))

    memory_ok = all(
        token in texts["memory-check"].lower()
        for token in (
            "memory map: ok",
            "handoff:    ok",
            "heap:       ok",
            "stack:      ok",
        )
    )
    entries.append(
        _entry(
            "Memory ownership",
            "PASS" if memory_ok else "FAIL",
            "sorted non-overlapping map and runtime guards",
        )
    )

    device_tree_active = "fdt:" in texts["device-tree-summary"].lower()
    device_tree_required = "device_tree" in profile["required_services"]
    entries.append(
        _entry(
            "Device tree",
            "PASS"
            if device_tree_active
            else ("FAIL" if device_tree_required else "PARTIAL"),
            "validated FDT active" if device_tree_active else "no validated FDT",
        )
    )

    detected_irq = _detect_interrupt(texts["irq-controller"])
    expected_irq = profile["interrupt_controller"]
    if expected_irq == "none":
        irq_state = "PASS" if detected_irq in {"none", "polling"} else "PARTIAL"
    elif detected_irq == "none":
        irq_state = "UNSUPPORTED"
    elif expected_irq == "any" or detected_irq == expected_irq:
        irq_state = (
            "NOT TESTED"
            if "delivery: masked" in texts["irq-controller"].lower()
            else "PASS"
        )
    else:
        irq_state = "FAIL"
    entries.append(
        _entry(
            "Interrupt controller",
            irq_state,
            f"expected {expected_irq}, observed {detected_irq}",
        )
    )

    watchdog_text = texts["watchdog-services"].lower()
    watchdog_available = (
        "configure: available" in watchdog_text and "kick: available" in watchdog_text
    )
    entries.append(
        _entry(
            "Watchdog",
            "NOT TESTED" if watchdog_available else "UNSUPPORTED",
            "services present but unchanged"
            if watchdog_available
            else "callbacks unavailable",
        )
    )

    framebuffer_text = texts["framebuffer-info"]
    framebuffer_available = bool(
        re.search(r"^Framebuffer:\s+0x", framebuffer_text, re.MULTILINE)
    )
    framebuffer_spec = profile["framebuffer"]
    framebuffer_detail = "not provided"
    framebuffer_matches = True
    if framebuffer_available:
        geometry = re.search(r"Geometry:\s+(\d+)x(\d+)", framebuffer_text)
        pixel = re.search(r"Format:\s+([A-Z0-9]+)", framebuffer_text)
        framebuffer_detail = "metadata present; writes remain locked"
        if framebuffer_spec is not None:
            if geometry is None:
                framebuffer_matches = False
            else:
                width, height = int(geometry.group(1)), int(geometry.group(2))
                framebuffer_matches &= width >= framebuffer_spec["minimum_width"]
                framebuffer_matches &= height >= framebuffer_spec["minimum_height"]
            allowed_formats = framebuffer_spec["pixel_formats"]
            if allowed_formats:
                framebuffer_matches &= (
                    pixel is not None and pixel.group(1) in allowed_formats
                )
    if framebuffer_spec is None:
        fb_state = "LOCKED" if framebuffer_available else "UNSUPPORTED"
    elif not framebuffer_available:
        fb_state = "FAIL" if framebuffer_spec["required"] else "UNSUPPORTED"
    elif not framebuffer_matches:
        fb_state = "FAIL"
        framebuffer_detail = "metadata does not satisfy the board profile"
    else:
        fb_state = "LOCKED"
    entries.append(_entry("Framebuffer", fb_state, framebuffer_detail))

    modules_locked = (
        "Modules:         LOCKED" in texts["probe-status"]
        or "Modules" in texts["compatibility"]
        and "LOCKED" in texts["compatibility"]
    )
    entries.append(
        _entry(
            "Modules",
            "LOCKED" if modules_locked else "PARTIAL",
            "defensive mode" if modules_locked else "lock state not confirmed",
        )
    )

    for service in profile["required_services"]:
        entries.append(
            _entry(
                f"Service: {service}",
                "PASS" if _service_supported(service, texts) else "FAIL",
                "required by board profile",
            )
        )

    states = [entry.state for entry in entries]
    result = (
        "fail"
        if "FAIL" in states
        else (
            "partial"
            if any(
                state in {"PARTIAL", "NOT TESTED", "LOCKED", "UNSUPPORTED"}
                for state in states
            )
            else "pass"
        )
    )
    return {
        "schema_version": 1,
        "profile": profile["name"],
        "result": result,
        "diagnostics": directory.name,
        "matrix": [entry.__dict__ for entry in entries],
    }


def import_probe_results(
    profile: dict[str, Any], diagnostics: pathlib.Path
) -> dict[str, Any]:
    """Attach conservative observations without promoting untested features."""
    normalized = validate_profile(profile)
    report = check_profile(normalized, diagnostics)
    observed = {item["feature"]: item["state"] for item in report.get("matrix", [])}
    supported_services = []
    untested_services = []
    for item in report.get("matrix", []):
        feature = item.get("feature", "")
        if not feature.startswith("Service: "):
            continue
        service = feature.split(":", 1)[1].strip()
        if item.get("state") == "PASS":
            supported_services.append(service)
        else:
            untested_services.append(service)
    normalized["review"] = {
        "source": _diagnostic_directory(diagnostics).name,
        "compatibility_result": report.get("result", "partial"),
        "observed": dict(sorted(observed.items())),
        "supported_services": sorted(supported_services),
        "untested_services": sorted(untested_services),
    }
    return validate_profile(normalized)


def format_matrix(report: dict[str, Any]) -> str:
    lines = [
        f"Profile: {report.get('profile', 'unknown')}",
        f"Result:  {report.get('result', 'unknown').upper()}",
        "",
    ]
    for item in report.get("matrix", []):
        lines.append(f"{item['feature']:<30} {item['state']:<12} {item['detail']}")
    return "\n".join(lines) + "\n"
