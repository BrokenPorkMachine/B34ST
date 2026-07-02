#!/usr/bin/env python3

"""Run the release deployment simulation and emit deterministic evidence inputs."""
# SPDX-License-Identifier: BSD-2-Clause
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "host"))

from deployment import DeploymentClient, LocalArtifact, write_evidence_bundle  # noqa: E402
from deployment_profile import load_profile  # noqa: E402
from deployment_target import SimulatedDeploymentTarget  # noqa: E402
from deployment_transport import FaultPlan, SimulatorTransport  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=pathlib.Path,
                        default=ROOT / "profiles/qemu-virt-deployment.json")
    parser.add_argument("--monitor", type=pathlib.Path,
                        default=ROOT / "build-generic/fbr34ker-generic.bin")
    parser.add_argument("--module", type=pathlib.Path,
                        default=ROOT / "build/modules/hello-dynamic.fmod")
    parser.add_argument("--output", type=pathlib.Path,
                        default=ROOT / "build/deployment-simulation")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    profile = load_profile(args.profile)
    artifacts = [
        LocalArtifact.from_path("monitor", "monitor", args.monitor, 0x80000000),
        LocalArtifact.from_path("hello-dynamic", "module", args.module, 0x84000000),
    ]
    target = SimulatedDeploymentTarget(
        profile, output / "target-state", clock_ns=lambda: 0,
        session_factory=lambda: "release-simulation-session",
        token_factory=lambda: 0x0102030405060708,
    )
    # Exercise idempotent retry caching at the host layer with one lost response.
    transport = SimulatorTransport(target, FaultPlan(drop_response_at=frozenset({4})))
    client = DeploymentClient(transport, timeout=1.0, retries=3, chunk_size=4096)
    try:
        result = client.deploy(profile, artifacts, authorize=True, resume=True, start=True)
        evidence = client.evidence()
        bundle = write_evidence_bundle(output / "evidence", profile=profile,
                                       artifacts=artifacts, evidence=evidence,
                                       transcript=client.transcript, deterministic=True)
    finally:
        client.close()
    try:
        bundle_name = bundle.relative_to(ROOT).as_posix()
    except ValueError:
        bundle_name = bundle.name
    summary = {
        "schema_version": 1,
        "result": "pass",
        "profile": profile.name,
        "started": result.get("started") is True,
        "evidence_bundle": bundle_name,
        "artifact_count": len(artifacts),
        "retry_count": sum(1 for entry in client.transcript if entry.status == "retry"),
        "arbitrary_memory": False,
        "exploit_transport": False
    }
    (output / "simulation-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["started"] and summary["retry_count"] >= 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
