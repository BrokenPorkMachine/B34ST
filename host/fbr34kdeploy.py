#!/usr/bin/env python3
"""FBR34KER bounded deployment, simulation, resume, and evidence utility."""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Sequence

from deployment import (DeploymentCancelled, DeploymentClient, DeploymentError, LocalArtifact,
                        validate_local_plan, write_evidence_bundle)
from deployment_profile import ProfileError, load_profile
from deployment_target import SimulatedDeploymentTarget
from deployment_transport import (FaultPlan, FramedStreamTransport,
                                  PosixSerialEndpoint, SimulatorTransport,
                                  SocketEndpoint, TransportError)

VERSION = "0.4.2b"


def parse_address(value: str) -> int:
    try:
        result = int(value, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("address must be an integer") from exc
    if not 0 <= result <= 0xFFFFFFFFFFFFFFFF:
        raise argparse.ArgumentTypeError("address exceeds 64-bit range")
    return result


def artifact_value(value: str) -> tuple[str, str, pathlib.Path, int]:
    # NAME:KIND:PATH@ADDRESS.  Split from the right so PATH may contain colons.
    if "@" not in value:
        raise argparse.ArgumentTypeError("artifact must be NAME:KIND:PATH@ADDRESS")
    left, address_text = value.rsplit("@", 1)
    parts = left.split(":", 2)
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("artifact must be NAME:KIND:PATH@ADDRESS")
    name, kind, path_text = parts
    if not name or not kind or not path_text:
        raise argparse.ArgumentTypeError("artifact fields cannot be empty")
    return name, kind, pathlib.Path(path_text), parse_address(address_text)


def add_transport_arguments(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--simulator-state", type=pathlib.Path,
                       help="use the included persistent file-backed target")
    group.add_argument("--tcp", metavar="HOST:PORT",
                       help="connect to an authorized FBDP socket receiver")
    group.add_argument("--unix", type=pathlib.Path, metavar="PATH",
                       help="connect to an authorized FBDP Unix socket receiver")
    group.add_argument("--serial", type=pathlib.Path, metavar="DEVICE",
                       help="connect to an authorized FBDP serial receiver")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--fault-plan", type=pathlib.Path,
                        help="simulator-only JSON fault injection plan")
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--chunk-size", type=int, default=4096)


def load_fault_plan(path: pathlib.Path | None) -> FaultPlan:
    if path is None:
        return FaultPlan()
    try:
        if path.stat().st_size > 64 * 1024:
            raise TransportError("fault plan exceeds 65536 bytes")
        return FaultPlan.from_json(json.loads(path.read_text(encoding="utf-8")))
    except OSError as exc:
        raise TransportError(f"cannot read fault plan: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise TransportError(f"fault plan is not valid JSON: {exc}") from exc


def make_client(args: argparse.Namespace, profile_path: pathlib.Path) -> tuple[DeploymentClient, object]:
    profile = load_profile(profile_path)
    if args.simulator_state is not None or not any((args.tcp, args.unix, args.serial)):
        state = args.simulator_state or pathlib.Path("runtime-artifacts/deployment-target")
        target = SimulatedDeploymentTarget(profile, state)
        transport = SimulatorTransport(target, load_fault_plan(args.fault_plan))
    else:
        if args.fault_plan is not None:
            raise TransportError("--fault-plan is available only with --simulator-state")
        if args.tcp:
            endpoint = SocketEndpoint.tcp(args.tcp, args.timeout)
        elif args.unix:
            endpoint = SocketEndpoint.unix(args.unix, args.timeout)
        else:
            if args.baud <= 0:
                raise TransportError("baud must be positive")
            endpoint = PosixSerialEndpoint(args.serial, args.baud)
        transport = FramedStreamTransport(endpoint)
    return DeploymentClient(transport, timeout=args.timeout, retries=args.retries,
                            chunk_size=args.chunk_size), profile


def local_artifacts(values: Sequence[tuple[str, str, pathlib.Path, int]]) -> list[LocalArtifact]:
    return [LocalArtifact.from_path(name, kind, path, address)
            for name, kind, path, address in values]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan = subparsers.add_parser("plan", help="validate a deployment without contacting a target")
    plan.add_argument("--profile", type=pathlib.Path, required=True)
    plan.add_argument("--artifact", action="append", type=artifact_value, required=True)

    deploy = subparsers.add_parser("deploy", help="stage, verify, start, and collect evidence")
    deploy.add_argument("--profile", type=pathlib.Path, required=True)
    deploy.add_argument("--artifact", action="append", type=artifact_value, required=True)
    deploy.add_argument("--authorize", action="store_true",
                        help="confirm this is an authorized development target")
    resume_group = deploy.add_mutually_exclusive_group()
    resume_group.add_argument("--recover", action="store_true",
                              help="explicitly resume a matching interrupted session")
    resume_group.add_argument("--no-resume", action="store_true",
                              help="always begin a new deployment session")
    validation_group = deploy.add_mutually_exclusive_group()
    validation_group.add_argument("--dry-run", action="store_true",
                                  help="validate the local plan without contacting a target")
    validation_group.add_argument("--verify-only", action="store_true",
                                  help="validate the plan and target capabilities without mutation")
    deploy.add_argument("--stage-only", action="store_true")
    deploy.add_argument("--evidence-dir", type=pathlib.Path,
                        default=pathlib.Path("runtime-artifacts/deployment-evidence"))
    add_transport_arguments(deploy)

    inspect = subparsers.add_parser("inspect", help="read target identity and capabilities")
    inspect.add_argument("--profile", type=pathlib.Path, required=True)
    add_transport_arguments(inspect)

    evidence = subparsers.add_parser("evidence", help="read current target evidence")
    evidence.add_argument("--profile", type=pathlib.Path, required=True)
    add_transport_arguments(evidence)

    reset = subparsers.add_parser("reset", help="reset a deployment session, preserving evidence")
    reset.add_argument("--profile", type=pathlib.Path, required=True)
    reset.add_argument("--authorize", action="store_true")
    add_transport_arguments(reset)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    client: DeploymentClient | None = None
    try:
        if args.command == "plan":
            profile = load_profile(args.profile)
            artifacts = local_artifacts(args.artifact)
            validate_local_plan(profile, artifacts)
            print(json.dumps({
                "schema_version": 1,
                "status": "valid",
                "profile": profile.name,
                "total_size": sum(artifact.size for artifact in artifacts),
                "artifacts": [artifact.manifest_record() for artifact in artifacts],
            }, indent=2, sort_keys=True))
            return 0

        if args.command == "deploy" and args.dry_run:
            profile = load_profile(args.profile)
            artifacts = local_artifacts(args.artifact)
            validate_local_plan(profile, artifacts)
            print(json.dumps({
                "schema_version": 1,
                "status": "dry-run-valid",
                "profile": profile.name,
                "artifacts": [artifact.manifest_record() for artifact in artifacts],
            }, indent=2, sort_keys=True))
            return 0

        client, profile = make_client(args, args.profile)
        if args.command == "inspect":
            print(json.dumps({"hello": client.hello(),
                              "capabilities": client.capabilities()},
                             indent=2, sort_keys=True))
            return 0
        if args.command == "evidence":
            print(json.dumps(client.evidence(), indent=2, sort_keys=True))
            return 0
        if args.command == "reset":
            if not args.authorize:
                raise DeploymentError("session reset requires explicit --authorize")
            print(json.dumps(client.reset(), indent=2, sort_keys=True))
            return 0
        if args.command == "deploy":
            artifacts = local_artifacts(args.artifact)
            validate_local_plan(profile, artifacts)
            if args.verify_only:
                print(json.dumps({
                    "schema_version": 1,
                    "status": "verified",
                    "profile": profile.name,
                    "hello": client.hello(),
                    "capabilities": client.capabilities(),
                    "artifacts": [artifact.manifest_record() for artifact in artifacts],
                }, indent=2, sort_keys=True))
                return 0
            result = client.deploy(profile, artifacts, authorize=args.authorize,
                                   resume=args.recover or not args.no_resume, start=not args.stage_only)
            evidence = client.evidence()
            archive = write_evidence_bundle(args.evidence_dir, profile=profile,
                                            artifacts=artifacts, evidence=evidence,
                                            transcript=client.transcript)
            print(json.dumps({
                "result": result,
                "evidence": evidence,
                "evidence_bundle": str(archive),
            }, indent=2, sort_keys=True))
            return 0
        parser.error("unsupported command")
    except DeploymentCancelled as exc:
        print(f"fbr34kdeploy: {exc}", file=sys.stderr)
        return 130
    except KeyboardInterrupt:
        print("fbr34kdeploy: interrupted", file=sys.stderr)
        return 130
    except (DeploymentError, ProfileError, TransportError, OSError) as exc:
        print(f"fbr34kdeploy: {exc}", file=sys.stderr)
        return 2
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
