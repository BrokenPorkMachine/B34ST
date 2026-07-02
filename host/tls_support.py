"""Verified TLS client context and CA-bundle discovery."""

# SPDX-License-Identifier: BSD-2-Clause
from __future__ import annotations

import os
import pathlib
import ssl
from collections.abc import Iterator


class TLSConfigurationError(RuntimeError):
    """Raised when no usable certificate authority store is available."""


def _candidate_ca_bundles() -> Iterator[pathlib.Path]:
    environment_path = os.environ.get("SSL_CERT_FILE")
    if environment_path:
        yield pathlib.Path(environment_path).expanduser()

    defaults = ssl.get_default_verify_paths()
    if defaults.cafile:
        yield pathlib.Path(defaults.cafile)

    try:
        import certifi

        yield pathlib.Path(certifi.where())
    except ImportError:
        pass

    for candidate in (
        "/opt/homebrew/etc/openssl@3/cert.pem",
        "/opt/homebrew/etc/ca-certificates/cert.pem",
        "/usr/local/etc/openssl@3/cert.pem",
        "/usr/local/etc/ca-certificates/cert.pem",
        "/etc/ssl/cert.pem",
    ):
        yield pathlib.Path(candidate)


def find_ca_bundle() -> pathlib.Path | None:
    """Return the first existing, non-empty CA bundle."""

    seen: set[pathlib.Path] = set()
    for candidate in _candidate_ca_bundles():
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        try:
            if resolved.is_file() and resolved.stat().st_size > 0:
                return resolved
        except OSError:
            continue
    return None


def tls_client_context() -> ssl.SSLContext:
    """Build a server-auth context using an explicit trusted CA bundle."""

    bundle = find_ca_bundle()
    if bundle is None:
        raise TLSConfigurationError(
            "no trusted CA bundle found; set SSL_CERT_FILE or install "
            "certifi/ca-certificates"
        )
    try:
        context = ssl.create_default_context(cafile=str(bundle))
    except (OSError, ssl.SSLError) as exc:
        raise TLSConfigurationError(
            f"unable to load trusted CA bundle {bundle}: {exc}"
        ) from exc
    if not context.get_ca_certs():
        raise TLSConfigurationError(
            f"trusted CA bundle contains no usable certificates: {bundle}"
        )
    return context


def tls_ca_status() -> tuple[bool, str | None, str]:
    """Return readiness, selected path, and a diagnostic description."""

    bundle = find_ca_bundle()
    if bundle is None:
        return (
            False,
            None,
            "no trusted CA bundle found; set SSL_CERT_FILE or install "
            "certifi/ca-certificates",
        )
    try:
        count = len(tls_client_context().get_ca_certs())
    except TLSConfigurationError as exc:
        return False, str(bundle), str(exc)
    return True, str(bundle), f"{count} trusted CA certificates loaded"
