# SPDX-License-Identifier: BSD-2-Clause
from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "host"))

from deployment import (CancellationToken, DeploymentCancelled, DeploymentClient, DeploymentError, LocalArtifact,  # noqa: E402
                        validate_local_plan, write_evidence_bundle)
from deployment_profile import load_profile  # noqa: E402
from deployment_target import SimulatedDeploymentTarget  # noqa: E402
from deployment_transport import FaultPlan, SimulatorTransport  # noqa: E402


class DeploymentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.profile = load_profile(ROOT / "profiles/qemu-virt-deployment.json")
        self.monitor = self.root / "monitor.bin"
        self.module = self.root / "module.fmod"
        self.monitor.write_bytes(b"monitor" * 900)
        self.module.write_bytes(b"module" * 200)
        self.artifacts = [
            LocalArtifact.from_path("monitor", "monitor", self.monitor, 0x80000000),
            LocalArtifact.from_path("module", "module", self.module, 0x84000000),
        ]

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_local_plan_requires_one_monitor(self) -> None:
        with self.assertRaisesRegex(DeploymentError, "exactly one monitor"):
            validate_local_plan(self.profile, self.artifacts[1:])

    def test_simulated_deployment_retries_lost_response(self) -> None:
        target = SimulatedDeploymentTarget(self.profile, self.root / "state")
        transport = SimulatorTransport(target, FaultPlan(drop_response_at=frozenset({4})))
        client = DeploymentClient(transport, timeout=0.1, retries=2, chunk_size=1024)
        result = client.deploy(self.profile, self.artifacts, authorize=True)
        self.assertTrue(result["started"])
        self.assertTrue(any(entry.status == "retry" for entry in client.transcript))
        self.assertTrue(all(item.committed for item in target.artifacts))

    def test_simulated_deployment_retries_corrupt_response(self) -> None:
        target = SimulatedDeploymentTarget(self.profile, self.root / "state-corrupt")
        transport = SimulatorTransport(target, FaultPlan(corrupt_response_at=frozenset({4})))
        client = DeploymentClient(transport, timeout=0.1, retries=2, chunk_size=1024)
        result = client.deploy(self.profile, self.artifacts, authorize=True)
        self.assertTrue(result["started"])
        self.assertTrue(any(entry.status == "retry" for entry in client.transcript))

    def test_oversized_persisted_session_is_discarded(self) -> None:
        state = self.root / "oversized-state"
        state.mkdir()
        (state / "session.json").write_bytes(b" " * (256 * 1024 + 1))
        target = SimulatedDeploymentTarget(self.profile, state)
        self.assertEqual(target.artifacts, [])
        self.assertEqual(target.session_id, "")

    def test_interrupted_deployment_resumes(self) -> None:
        state = self.root / "state"
        target = SimulatedDeploymentTarget(self.profile, state)
        first = DeploymentClient(
            SimulatorTransport(target, FaultPlan(drop_response_at=frozenset({5}))),
            timeout=0.05, retries=0, chunk_size=1024,
        )
        with self.assertRaises(DeploymentError):
            first.deploy(self.profile, self.artifacts, authorize=True)
        recovered_target = SimulatedDeploymentTarget(self.profile, state)
        second = DeploymentClient(SimulatorTransport(recovered_target), timeout=0.1,
                                  retries=1, chunk_size=1024)
        result = second.deploy(self.profile, self.artifacts, authorize=True, resume=True)
        self.assertTrue(result["started"])
        self.assertTrue(all(item.committed for item in recovered_target.artifacts))

    def test_authorization_is_explicit(self) -> None:
        target = SimulatedDeploymentTarget(self.profile, self.root / "state")
        client = DeploymentClient(SimulatorTransport(target))
        with self.assertRaisesRegex(DeploymentError, "--authorize"):
            client.deploy(self.profile, self.artifacts, authorize=False)

    def test_cancellation_prevents_target_mutation(self) -> None:
        target = SimulatedDeploymentTarget(self.profile, self.root / "state")
        cancellation = CancellationToken()
        cancellation.cancel()
        client = DeploymentClient(SimulatorTransport(target), cancellation=cancellation)
        with self.assertRaises(DeploymentCancelled):
            client.deploy(self.profile, self.artifacts, authorize=True)
        self.assertEqual(target.artifacts, [])

    def test_reset_uses_active_session_token(self) -> None:
        target = SimulatedDeploymentTarget(self.profile, self.root / "state")
        client = DeploymentClient(SimulatorTransport(target))
        client.deploy(self.profile, self.artifacts, authorize=True, start=False)
        result = client.reset()
        self.assertTrue(result["reset"])
        self.assertEqual(target.artifacts, [])

    def test_evidence_bundle_is_readable(self) -> None:
        target = SimulatedDeploymentTarget(self.profile, self.root / "state")
        client = DeploymentClient(SimulatorTransport(target))
        evidence = client.deploy(self.profile, self.artifacts, authorize=True)
        archive = write_evidence_bundle(self.root / "evidence", profile=self.profile,
                                        artifacts=self.artifacts, evidence=evidence,
                                        transcript=client.transcript)
        self.assertTrue(archive.is_file())
        report = json.loads((self.root / "evidence/deployment-report.json").read_text())
        self.assertEqual(report["profile"], self.profile.name)

    def test_deterministic_evidence_bundle_reproduces(self) -> None:
        evidence = {"schema_version": 1, "started": True, "timestamp_ns": 0}
        first = write_evidence_bundle(self.root / "one", profile=self.profile,
                                      artifacts=self.artifacts, evidence=evidence,
                                      transcript=[], deterministic=True)
        second = write_evidence_bundle(self.root / "two", profile=self.profile,
                                       artifacts=self.artifacts, evidence=evidence,
                                       transcript=[], deterministic=True)
        # Archive roots differ, so compare the generated reports and checksum rows.
        self.assertEqual((self.root / "one/deployment-report.json").read_bytes(),
                         (self.root / "two/deployment-report.json").read_bytes())
        self.assertEqual((self.root / "one/SHA256SUMS").read_bytes(),
                         (self.root / "two/SHA256SUMS").read_bytes())
        self.assertTrue(first.is_file() and second.is_file())


if __name__ == "__main__":
    unittest.main()
