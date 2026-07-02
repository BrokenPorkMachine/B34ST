#!/usr/bin/env python3

"""Reference local development receiver for FBDP transport testing.
# SPDX-License-Identifier: BSD-2-Clause

The server is intentionally a file-backed target.  It does not access USB,
physical memory, or device boot mechanisms.
"""
from __future__ import annotations

import argparse
import pathlib
import socket
import sys
import threading
import time
from typing import Sequence

from deployment_profile import ProfileError, load_profile
from deployment_target import SimulatedDeploymentTarget
from wire_protocol import ProtocolError, StreamDecoder, encode_frame


class ServerError(RuntimeError):
    pass


def serve_connection(connection: socket.socket, target: SimulatedDeploymentTarget,
                     *, stop_event: threading.Event | None = None,
                     idle_timeout: float = 30.0, max_frames: int = 4096) -> int:
    if idle_timeout <= 0 or max_frames <= 0:
        raise ServerError("idle timeout and max_frames must be positive")
    decoder = StreamDecoder()
    handled = 0
    deadline = time.monotonic() + idle_timeout
    while stop_event is None or not stop_event.is_set():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        connection.settimeout(min(remaining, 1.0))
        try:
            data = connection.recv(8192)
        except socket.timeout:
            continue
        if not data:
            break
        deadline = time.monotonic() + idle_timeout
        try:
            frames = decoder.feed(data)
        except ProtocolError as exc:
            raise ServerError(str(exc)) from exc
        for frame in frames:
            connection.sendall(encode_frame(target.handle(frame)))
            handled += 1
            if handled >= max_frames:
                return handled
    return handled


def parse_tcp(value: str) -> tuple[str, int]:
    if ":" not in value:
        raise argparse.ArgumentTypeError("TCP listener must be HOST:PORT")
    host, port_text = value.rsplit(":", 1)
    try:
        port = int(port_text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("TCP port is not an integer") from exc
    if not 0 <= port <= 65535:
        raise argparse.ArgumentTypeError("TCP port must be 0..65535")
    return host, port


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=pathlib.Path, required=True)
    parser.add_argument("--state-dir", type=pathlib.Path, required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--tcp", type=parse_tcp, metavar="HOST:PORT")
    group.add_argument("--unix", type=pathlib.Path, metavar="PATH")
    parser.add_argument("--allow-nonloopback", action="store_true")
    parser.add_argument("--idle-timeout", type=float, default=30.0)
    parser.add_argument("--max-frames", type=int, default=4096)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.idle_timeout <= 0 or args.max_frames <= 0:
        print("fbr34kdeploy-target: idle timeout and max frames must be positive", file=sys.stderr)
        return 2
    try:
        profile = load_profile(args.profile)
        target = SimulatedDeploymentTarget(profile, args.state_dir)
        if args.tcp:
            host, port = args.tcp
            if host not in {"127.0.0.1", "::1", "localhost"} and not args.allow_nonloopback:
                raise ServerError("non-loopback listeners require --allow-nonloopback")
            family = socket.AF_INET6 if ":" in host else socket.AF_INET
            listener = socket.socket(family, socket.SOCK_STREAM)
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((host, port))
        else:
            if args.unix.exists():
                args.unix.unlink()
            listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            listener.bind(str(args.unix))
        listener.listen(1)
        address = listener.getsockname()
        print(f"FBDP development target listening on {address}", flush=True)
        connection, _peer = listener.accept()
        try:
            handled = serve_connection(connection, target, idle_timeout=args.idle_timeout,
                                       max_frames=args.max_frames)
        finally:
            connection.close()
            listener.close()
            if args.unix and args.unix.exists():
                args.unix.unlink()
        print(f"handled {handled} deployment frames", flush=True)
        return 0
    except (OSError, ProfileError, ServerError) as exc:
        print(f"fbr34kdeploy-target: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
