# SPDX-License-Identifier: BSD-2-Clause
from __future__ import annotations

import json
import pathlib
import struct
import tempfile
import unittest

from b34st.research_runtime import (
    RuntimeSession,
    audit_legacy_components,
    inspect_kernelcache,
    kernel_identity_template,
    stage_evidence_template,
    validate_kernel_identity,
    validate_stage_evidence,
)


class ResearchRuntimeTests(unittest.TestCase):
    def kernelcache(self, root: pathlib.Path) -> pathlib.Path:
        uuid = bytes.fromhex("00112233445566778899aabbccddeeff")
        header = struct.pack(
            "<IiiIIIII",
            0xFEEDFACF,
            0x0100000C,
            0,
            2,
            1,
            24,
            0,
            0,
        )
        command = struct.pack("<II16s", 0x1B, 24, uuid)
        path = root / "kernelcache"
        path.write_bytes(header + command)
        return path

    def test_kernelcache_inventory_extracts_uuid_and_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = inspect_kernelcache(self.kernelcache(pathlib.Path(directory)))
            self.assertTrue(result["format_recognized"])
            self.assertEqual(
                result["macho_uuid"],
                "00112233-4455-6677-8899-aabbccddeeff",
            )
            self.assertEqual(len(result["sha256"]), 64)

    def test_stage_evidence_is_bound_to_exact_kernel(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            digest = "a" * 64
            document = stage_evidence_template("KERNEL_PATCH_VERIFIED", digest)
            document["status"] = "verified"
            document["observations"] = ["Original bytes recorded and patched bytes read back."]
            document["rollback"] = {"available": True, "evidence": "rollback.json"}
            path = root / "evidence.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            result = validate_stage_evidence(
                path,
                expected_stage="KERNEL_PATCH_VERIFIED",
                kernel_sha256=digest,
            )
            self.assertEqual(result["document"]["target"]["kernelcache_sha256"], digest)
            with self.assertRaisesRegex(Exception, "does not match"):
                validate_stage_evidence(
                    path,
                    expected_stage="KERNEL_PATCH_VERIFIED",
                    kernel_sha256="b" * 64,
                )

    def test_kernel_identity_rejects_unknown_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            inventory = inspect_kernelcache(self.kernelcache(root))
            document = kernel_identity_template(inventory, product="iPhone12,1")
            document["ios_version"] = "17.6.1"
            document["build"] = "21G93"
            document["review"] = {
                "reviewer": "test",
                "source": "local authorized image",
                "approved": True,
            }
            path = root / "identity.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            result = validate_kernel_identity(
                path,
                inventory=inventory,
                product="iPhone12,1",
            )
            self.assertEqual(result["build"], "21G93")
            changed = dict(inventory)
            changed["sha256"] = "f" * 64
            with self.assertRaisesRegex(Exception, "not in the reviewed"):
                validate_kernel_identity(
                    path,
                    inventory=changed,
                    product="iPhone12,1",
                )

    def test_runtime_readiness_remains_blocked_without_external_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = RuntimeSession(pathlib.Path(directory))
            session.set_state("HOST_READY", "VERIFIED")
            session.finalize()
            self.assertEqual(
                session.report["states"]["RESEARCH_RUNTIME_READY"]["status"],
                "BLOCKED",
            )
            self.assertIn("KERNEL_PATCH_VERIFIED", session.report["blockers"])

    def test_legacy_component_audit_rejects_state_models_as_evidence(self) -> None:
        audit = audit_legacy_components()
        self.assertFalse(audit["accepted_as_runtime_evidence"])
        self.assertEqual(
            audit["components"]["scripts/run_exploit.py"]["classification"],
            "LEGACY_ORCHESTRATOR",
        )


if __name__ == "__main__":
    unittest.main()
