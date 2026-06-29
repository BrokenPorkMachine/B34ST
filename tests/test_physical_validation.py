from __future__ import annotations

import importlib.util
import json
import pathlib
import tempfile
import unittest

from host.session_bundle import STANDARD_FILES, write_session_bundle

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("physical_validation", ROOT / "host/physical_validation.py")
assert SPEC and SPEC.loader
physical_validation = importlib.util.module_from_spec(SPEC)
import sys
sys.path.insert(0, str(ROOT / "host"))
SPEC.loader.exec_module(physical_validation)


class PhysicalValidationTests(unittest.TestCase):
    def bundle(self, root: pathlib.Path, name: str, *, passed: bool = True,
               physical: bool = False, failed_stage: str | None = None) -> pathlib.Path:
        stages = [
            {"stage": stage, "status": "passed"}
            for stage in ("console", "board-inventory", "memory-map", "timer",
                          "interrupts", "watchdog", "boot-evidence")
        ]
        failure = None
        if failed_stage:
            passed = False
            for item in stages:
                if item["stage"] == failed_stage:
                    item["status"] = "failed"
            failure = f"injected failure at {failed_stage}"
        session = {
            "schema_version": 1, "project": "FBR34KER", "release_version": "0.4.0",
            "session_id": name * 24, "profile_id": "apple-a13-iphone-recovery",
            "device": {"cpid": "0x8030", "product": "iPhone12,1"},
            "adapter": {"adapter_id": "authorized-test-bridge", "capabilities": ["console"]},
            "adapter_transport": "persistent-bridge",
            "stages": stages, "passed": passed, "failure": failure,
            "failed_stage": failed_stage,
            "authorization_invalidated_after_recovery": bool(failed_stage),
            "physical_execution_verified": physical,
        }
        profile = {
            "schema_version": 1, "profile_id": "apple-a13-iphone-recovery",
            "family": "a13", "cpids": ["0x8030"], "requires_exact_product": True,
            "required_bringup_stages": [item["stage"] for item in stages],
            "maturity": "simulated",
        }
        values = {member: {} if member.endswith(".json") else "" for member in STANDARD_FILES}
        values.update({
            "session.json": session, "summary.json": session,
            "profile.json": profile,
            "console.log": "FBR34KER monitor entry observed\nbringup console: passed\nbringup boot-evidence: passed\n",
            "boot-evidence.json": {"persistent": True, "previous_failure": None},
        })
        path = root / f"{name}.zip"
        write_session_bundle(path, values)
        return path

    def test_valid_bridge_console_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            result = physical_validation.validate_bundle(self.bundle(pathlib.Path(directory), "a"))
            self.assertTrue(result["valid"], result)
            self.assertEqual(result["proof_class"], "bridge")

    def test_physical_claim_requires_separate_attestation(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = self.bundle(pathlib.Path(directory), "b", physical=True)
            result = physical_validation.validate_bundle(bundle)
            self.assertEqual(physical_validation.permitted_maturity(result),
                             "boot-evidence-verified")
            self.assertEqual(physical_validation.permitted_maturity(
                result, physical_attested=True), "physical-runtime-verified")

    def test_failure_explanation_is_stage_specific(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = self.bundle(pathlib.Path(directory), "c", failed_stage="timer")
            result = physical_validation.explain_failure(bundle)
            self.assertIn("timer", result["explanation"])
            self.assertIn("timer source", result["recommended_action"])

    def test_candidate_requires_failure_recovery_proof(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            success = self.bundle(root, "d")
            failure = self.bundle(root, "e", failed_stage="timer")
            recovered = self.bundle(root, "f")
            report = physical_validation.candidate_report(success, failure, recovered)
            self.assertTrue(report["candidate_ready"], report)
            self.assertFalse(report["physical_validation_complete"])

    def test_qemu_summary_can_promote_simulator_profile_to_qemu(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            bundle = self.bundle(root, "q")
            # Rewrite the session as simulator-backed while retaining valid evidence.
            import zipfile
            from host.session_bundle import read_session_bundle
            files = read_session_bundle(bundle)
            session = json.loads(files["session.json"])
            session["adapter"] = {"adapter_id": "fbr34ker-simulator"}
            session["adapter_transport"] = "simulator"
            values = {name: data for name, data in files.items() if name != "checksums.sha256"}
            values["session.json"] = session
            values["summary.json"] = session
            write_session_bundle(bundle, values)
            result = physical_validation.validate_bundle(bundle)
            self.assertEqual(physical_validation.permitted_maturity(result, qemu_passed=True),
                             "qemu-verified")

    def test_profile_promotion_rejects_unproven_physical_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            bundle = self.bundle(root, "g")
            with self.assertRaises(physical_validation.ValidationError):
                physical_validation.promote_profile(
                    ROOT / "profiles/apple-a13-iphone-recovery.json", bundle,
                    "physical-runtime-verified", root / "profile.json")


if __name__ == "__main__":
    unittest.main()
