#!/usr/bin/env python3

"""Deployment transport adapters for SEP research & fuzzing modules.
# SPDX-License-Identifier: BSD-2-Clause

Bridges the abstract ``api_fn`` (``Callable[[str], str]``) and ``submit``
(``Callable[[bytes, dict], dict]``) interfaces used by the SEP research
pipeline and key fuzzer to the real FBR34KER deployment transport.

Transport backends
------------------
- **USBConsole** – live USB CDC ACM connection to the FBR34KER monitor (``usb_serial.py``).
- **Serial** – raw POSIX serial port via the FBDP ``FramedStreamTransport``.
- **TCP** – TCP socket via the FBDP ``FramedStreamTransport``.
- **Simulator** – in-memory simulated target for testing (no device required).
- **FBDP deploy** – full FBR34KER Bounded Deployment Protocol for deploying
  artifacts (Swift harness, monitor modules) before running tests.

Usage::

    from host.forensics.sep_deploy import make_research_api, make_fuzzer_submit

    # Research pipeline via USB console
    api = make_research_api("usb", vid=0x05AC, pid=0x1234)
    pipeline = SEPResearchPipeline(device_model="iPhone14,2", api_fn=api)

    # Key fuzzer via serial
    submit = make_fuzzer_submit("serial", port="/dev/ttyUSB0")
    campaign = run_campaign(submit, output_dir)
"""

from __future__ import annotations

import json
import pathlib
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Transport type registry
# ---------------------------------------------------------------------------

TRANSPORT_BACKENDS: dict[str, str] = {
    "usb": "USB CDC ACM console (requires pyusb)",
    "serial": "POSIX serial port (FBDP framed)",
    "tcp": "TCP socket (FBDP framed)",
    "simulator": "In-memory simulated SEP service (no device)",
    "fbdp": "FBR34KER Bounded Deployment Protocol (full deploy pipeline)",
}

# ---------------------------------------------------------------------------
# Research Pipeline API adapters — Callable[[str], str]
# ---------------------------------------------------------------------------


def _simulated_api(call: str) -> str:
    """Default simulation — returns canned responses."""
    if "error" in call.lower():
        raise RuntimeError(f"simulated error: {call}")
    if "crash" in call.lower() or "panic" in call.lower():
        raise RuntimeError(f"simulated SEP panic: {call}")
    if "reset" in call.lower():
        raise RuntimeError("simulated SEP reset: watchdog timeout")
    return f"ok: sim response to '{call[:60]}...'"


def _make_usb_api(
    vid: int = 0x05AC,
    pid: int = 0x1234,
    serial: str | None = None,
    timeout: float = 10.0,
) -> Callable[[str], str]:
    """Wrap USBConsole.run_command into a Callable[[str], str].

    Requires pyusb and a connected FBR34KER monitor.
    """
    try:
        from host.usb_serial import USBConsole, TransportError
    except ImportError:
        raise ImportError("pyusb is required for USB transport")

    console = USBConsole(vid=vid, pid=pid, serial=serial)
    console.open()

    def _api(call: str) -> str:
        try:
            return console.run_command(call, timeout=timeout)
        except TransportError as exc:
            raise RuntimeError(f"USB transport error: {exc}")
        except (OSError, RuntimeError) as exc:
            raise RuntimeError(f"USB command failed: {exc}")

    return _api


def _make_serial_api(
    port: str = "/dev/ttyUSB0",
    baud: int = 115200,
    timeout: float = 10.0,
) -> Callable[[str], str]:
    """Wrap a POSIX serial port into a Callable[[str], str].

    Uses the FBDP FramedStreamTransport over PosixSerialEndpoint.
    Send the call string as a frame payload, read the response frame.
    """
    try:
        from host.deployment_transport import (
            FramedStreamTransport,
            PosixSerialEndpoint,
            TransportError,
        )
        from host.wire_protocol import Frame, MessageType
    except ImportError:
        raise ImportError("FBDP transport modules required for serial transport")

    endpoint = PosixSerialEndpoint(port=port, baud=baud)
    transport = FramedStreamTransport(endpoint)

    def _api(call: str) -> str:
        try:
            req = Frame(
                message_type=MessageType.DATA,
                payload=call.encode("utf-8"),
                sequence=0,
            )
            resp = transport.exchange(req, timeout=timeout)
            return resp.payload.decode("utf-8", errors="replace")
        except TransportError as exc:
            raise RuntimeError(f"Serial transport error: {exc}")

    return _api


def _make_tcp_api(
    host: str = "127.0.0.1",
    port: int = 9999,
    timeout: float = 10.0,
) -> Callable[[str], str]:
    """Wrap a TCP socket into a Callable[[str], str].

    Uses the FBDP FramedStreamTransport over SocketEndpoint.
    """
    try:
        from host.deployment_transport import (
            FramedStreamTransport,
            SocketEndpoint,
            TransportError,
        )
        from host.wire_protocol import Frame, MessageType
    except ImportError:
        raise ImportError("FBDP transport modules required for TCP transport")

    endpoint = SocketEndpoint.tcp(host, port)
    transport = FramedStreamTransport(endpoint)

    def _api(call: str) -> str:
        try:
            req = Frame(
                message_type=MessageType.DATA,
                payload=call.encode("utf-8"),
                sequence=0,
            )
            resp = transport.exchange(req, timeout=timeout)
            return resp.payload.decode("utf-8", errors="replace")
        except TransportError as exc:
            raise RuntimeError(f"TCP transport error: {exc}")

    return _api


def make_research_api(
    backend: str = "simulator",
    **kwargs: Any,
) -> Callable[[str], str]:
    """Create a research pipeline ``api_fn`` for the given transport backend.

    Args:
        backend: One of ``"simulator"``, ``"usb"``, ``"serial"``, ``"tcp"``.
        **kwargs: Backend-specific arguments:
            - ``usb``: ``vid``, ``pid``, ``serial``, ``timeout``
            - ``serial``: ``port``, ``baud``, ``timeout``
            - ``tcp``: ``host``, ``port``, ``timeout``

    Returns:
        A callable suitable as ``api_fn`` for ``SEPResearchPipeline``.

    Usage::

        api = make_research_api("usb")
        pipeline = SEPResearchPipeline(device_model="iPhone14,2", api_fn=api)

        api = make_research_api("serial", port="/dev/ttyUSB0")
        pipeline = SEPResearchPipeline(device_model="iPhone14,2", api_fn=api)

        api = make_research_api("tcp", host="192.168.1.100", port=9999)
        pipeline = SEPResearchPipeline(device_model="iPhone14,2", api_fn=api)
    """
    _backends: dict[str, Callable[..., Callable[[str], str]]] = {
        "simulator": lambda **_kw: _simulated_api,
        "usb": _make_usb_api,
        "serial": _make_serial_api,
        "tcp": _make_tcp_api,
    }

    maker = _backends.get(backend)
    if maker is None:
        raise ValueError(
            f"Unknown backend: {backend}. Choose from: {', '.join(sorted(_backends))}"
        )
    return maker(**kwargs)


# ---------------------------------------------------------------------------
# Key Fuzzer Submit adapters — Callable[[bytes, dict], dict]
# ---------------------------------------------------------------------------


def _simulated_submit(mutated: bytes, metadata: dict[str, Any]) -> dict[str, Any]:
    """Simulated submit — returns a plausible response for testing."""
    name = metadata.get("variation", "unknown")
    if "flip" in name or "oversize" in name:
        return {"accepted": False, "error": "simulated: integrity check failed"}
    if name in ("after_biometry_remove", "after_passcode_change"):
        return {"accepted": False, "error": "simulated: ACL invalidated"}
    return {
        "accepted": True,
        "public_key_hex": "00" * 65,
        "output_buffers": [],
        "error": "",
        "duration_ms": 15.0,
    }


def _make_usb_fuzzer_submit(
    vid: int = 0x05AC,
    pid: int = 0x1234,
    serial: str | None = None,
    timeout: float = 30.0,
) -> Callable[[bytes, dict[str, Any]], dict[str, Any]]:
    """Build a submit callable that sends wrapper bytes via USBConsole.

    The monitor-side test app receives:
        ``sep-fuzz <hex-encoded-wrapper> <variation-name>``

    and returns JSON with keys: ``accepted``, ``public_key_hex``,
    ``output_buffers``, ``error``, ``duration_ms``.
    """
    try:
        from host.usb_serial import USBConsole, TransportError
    except ImportError:
        raise ImportError("pyusb is required for USB transport")

    console = USBConsole(vid=vid, pid=pid, serial=serial)
    console.open()

    def _submit(mutated: bytes, metadata: dict[str, Any]) -> dict[str, Any]:
        wrapper_hex = mutated.hex()
        variation = metadata.get("variation", "unknown")
        command = f"sep-fuzz {wrapper_hex} {variation}"
        try:
            raw = console.run_command(command, timeout=timeout)
        except TransportError as exc:
            return {
                "accepted": False,
                "error": str(exc),
                "public_key_hex": "",
                "output_buffers": [],
                "duration_ms": 0.0,
            }
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {
                "accepted": False,
                "error": f"non-JSON response: {raw[:200]}",
                "public_key_hex": "",
                "output_buffers": [],
                "duration_ms": 0.0,
            }

    return _submit


def _make_serial_fuzzer_submit(
    port: str = "/dev/ttyUSB0",
    baud: int = 115200,
    timeout: float = 30.0,
) -> Callable[[bytes, dict[str, Any]], dict[str, Any]]:
    """Build a submit callable that sends wrapper bytes via FBDP serial."""
    try:
        from host.deployment_transport import (
            FramedStreamTransport,
            PosixSerialEndpoint,
            TransportError,
        )
        from host.wire_protocol import Frame, MessageType
    except ImportError:
        raise ImportError("FBDP transport modules required for serial transport")

    endpoint = PosixSerialEndpoint(port=port, baud=baud)
    transport = FramedStreamTransport(endpoint)

    def _submit(mutated: bytes, metadata: dict[str, Any]) -> dict[str, Any]:
        wrapper_hex = mutated.hex()
        variation = metadata.get("variation", "unknown")
        payload = json.dumps(
            {
                "wrapper_hex": wrapper_hex,
                "variation": variation,
            }
        )
        try:
            req = Frame(
                message_type=MessageType.DATA,
                payload=payload.encode("utf-8"),
                sequence=0,
            )
            resp = transport.exchange(req, timeout=timeout)
            raw = resp.payload.decode("utf-8", errors="replace")
            return json.loads(raw)
        except TransportError as exc:
            return {
                "accepted": False,
                "error": str(exc),
                "public_key_hex": "",
                "output_buffers": [],
                "duration_ms": 0.0,
            }
        except (json.JSONDecodeError, TypeError):
            return {
                "accepted": False,
                "error": f"non-JSON response: {raw[:200]}",
                "public_key_hex": "",
                "output_buffers": [],
                "duration_ms": 0.0,
            }

    return _submit


def make_fuzzer_submit(
    backend: str = "simulator",
    **kwargs: Any,
) -> Callable[[bytes, dict[str, Any]], dict[str, Any]]:
    """Create a key fuzzer ``submit`` callable for the given transport backend.

    Args:
        backend: One of ``"simulator"``, ``"usb"``, ``"serial"``.
        **kwargs: Backend-specific arguments:
            - ``usb``: ``vid``, ``pid``, ``serial``, ``timeout``
            - ``serial``: ``port``, ``baud``, ``timeout``

    Returns:
        A callable suitable as ``submit`` for ``SEPKeyFuzzer.run()``.

    Usage::

        submit = make_fuzzer_submit("usb")
        manifest = run_campaign(submit, output_dir)

        submit = make_fuzzer_submit("serial", port="/dev/ttyUSB0")
        manifest = run_campaign(submit, output_dir)
    """
    _backends: dict[
        str, Callable[..., Callable[[bytes, dict[str, Any]], dict[str, Any]]]
    ] = {
        "simulator": lambda **_kw: _simulated_submit,
        "usb": _make_usb_fuzzer_submit,
        "serial": _make_serial_fuzzer_submit,
    }

    maker = _backends.get(backend)
    if maker is None:
        raise ValueError(
            f"Unknown backend: {backend}. Choose from: {', '.join(sorted(_backends))}"
        )
    return maker(**kwargs)


# ---------------------------------------------------------------------------
# FBDP Deployment adapter — full artifact deployment for on-device testing
# ---------------------------------------------------------------------------


def deploy_swift_harness(
    profile_path: pathlib.Path,
    harness_path: pathlib.Path,
    *,
    transport: str = "simulator",
    transport_args: dict[str, Any] | None = None,
    start: bool = True,
    authorize: bool = True,
) -> dict[str, Any]:
    """Deploy the SEP key baseline Swift harness to a target via FBDP.

    Args:
        profile_path: Path to a JSON deployment profile (e.g.
            ``profiles/qemu-virt-deployment.json``).
        harness_path: Path to the compiled Swift harness binary.
        transport: ``"simulator"``, ``"tcp"``, or ``"serial"``.
        transport_args: Arguments for the transport (host, port, serial port, etc.).
        start: Whether to start execution after deployment.
        authorize: Whether to authorise the deployment session.

    Returns:
        The deployment result dict from ``DeploymentClient.deploy()``.

    Usage::

        result = deploy_swift_harness(
            pathlib.Path("profiles/qemu-virt-deployment.json"),
            pathlib.Path("build/BaselineHarness"),
            transport="serial",
            transport_args={"port": "/dev/ttyUSB0"},
        )
    """
    try:
        from host.deployment import DeploymentClient, LocalArtifact
        from host.deployment_profile import load_profile
        from host.deployment_target import SimulatedDeploymentTarget
        from host.deployment_transport import (
            FramedStreamTransport,
            SimulatorTransport,
            SocketEndpoint,
            PosixSerialEndpoint,
        )
    except ImportError:
        raise ImportError("FBDP deployment modules required")

    profile = load_profile(str(profile_path))
    targs = transport_args or {}

    if transport == "simulator":
        try:
            from host.deployment_target import SimulatedDeploymentTarget
        except ImportError:
            raise ImportError("simulated target module required")
        target = SimulatedDeploymentTarget(
            profile,
            targs.get("state_dir", "runtime-artifacts/deployment-target"),
        )
        xport = SimulatorTransport(target)
    elif transport == "serial":
        endpoint = PosixSerialEndpoint(
            port=targs.get("port", "/dev/ttyUSB0"),
            baud=targs.get("baud", 115200),
        )
        xport = FramedStreamTransport(endpoint)
    elif transport == "tcp":
        endpoint = SocketEndpoint.tcp(
            targs.get("host", "127.0.0.1"),
            targs.get("port", 9999),
        )
        xport = FramedStreamTransport(endpoint)
    else:
        raise ValueError(f"Unknown transport: {transport}")

    client = DeploymentClient(
        xport,
        timeout=targs.get("timeout", 5.0),
        retries=targs.get("retries", 3),
        chunk_size=targs.get("chunk_size", 4096),
    )

    artifact = LocalArtifact.from_path(
        name="sep-harness",
        kind="payload",
        path=str(harness_path),
        load_address=targs.get("load_address", 0x80000000),
    )

    try:
        result = client.deploy(
            profile,
            [artifact],
            authorize=authorize,
            resume=True,
            start=start,
        )
        return {
            "success": True,
            "result": result,
            "evidence": client.evidence(),
        }
    except (OSError, RuntimeError) as exc:
        return {
            "success": False,
            "error": str(exc),
        }
    finally:
        client.close()


def list_backends() -> dict[str, str]:
    """Return a dict of available transport backends with descriptions."""
    return dict(TRANSPORT_BACKENDS)
