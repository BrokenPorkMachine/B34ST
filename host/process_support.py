"""Subprocess helpers for preserving terminal file status flags."""

from __future__ import annotations

import contextlib
import sys
from collections.abc import Iterator, Sequence
from typing import IO


@contextlib.contextmanager
def preserved_stdio_flags(
    streams: Sequence[IO[object]] | None = None,
) -> Iterator[None]:
    """Restore file status flags changed by an interactive child process."""

    if streams is None:
        streams = (sys.stdin, sys.stdout, sys.stderr)
    snapshots: dict[int, int] = {}
    try:
        import fcntl

        for stream in streams:
            try:
                descriptor = stream.fileno()
                snapshots[descriptor] = fcntl.fcntl(descriptor, fcntl.F_GETFL)
            except (AttributeError, OSError, ValueError):
                continue
    except ImportError:
        fcntl = None

    try:
        yield
    finally:
        if fcntl is not None:
            for descriptor, flags in snapshots.items():
                try:
                    fcntl.fcntl(descriptor, fcntl.F_SETFL, flags)
                except OSError:
                    pass
