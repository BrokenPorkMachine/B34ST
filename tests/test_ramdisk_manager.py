from __future__ import annotations

import argparse
import json
import pathlib
import tempfile
import unittest
import warnings
import zipfile

from host import ramdisk_manager


class RamdiskManagerTests(unittest.TestCase):
    def components(self, root: pathlib.Path) -> dict[str, pathlib.Path]:
        values = {
            "ramdisk": b"ramdisk-image",
            "kernelcache": b"kernelcache-image",
            "devicetree": b"device-tree-image",
            "trustcache": b"trust-cache-image",
        }
        result = {}
        for role, content in values.items():
            path = root / role
            path.write_bytes(content)
            result[role] = path
        return result

    def build_args(
        self, root: pathlib.Path, output: pathlib.Path
    ) -> argparse.Namespace:
        components = self.components(root)
        return argparse.Namespace(
            product="iPhone12,1",
            os_version="18.5",
            build="22F76",
            profile=None,
            ramdisk=components["ramdisk"],
            kernelcache=components["kernelcache"],
            devicetree=components["devicetree"],
            trustcache=components["trustcache"],
            ibss=None,
            ibec=None,
            iboot=None,
            bootlogo=None,
            restore_device_tree=None,
            component=[],
            output=output,
            force=False,
        )

    def test_target_catalog_covers_iphone_ipad_and_mac_without_physical_claim(self) -> None:
        targets = ramdisk_manager.target_records()
        self.assertGreater(len(targets), 50)
        self.assertEqual(
            {target["device_class"] for target in targets},
            {"iphone", "ipad", "mac"},
        )
        self.assertIn(
            "MacBookAir10,1", {target["product"] for target in targets}
        )
        self.assertTrue(
            all(not target["physical_execution_verified"] for target in targets)
        )
        self.assertTrue(
            all(target["compatibility"] == "profiled-unverified" for target in targets)
        )

    def test_plan_rejects_unlisted_product_and_mismatched_profile(self) -> None:
        with self.assertRaisesRegex(ramdisk_manager.RamdiskError, "no exact"):
            ramdisk_manager.make_plan(
                product="iPhone99,9",
                os_version="18.5",
                build=None,
                profile_path=None,
            )
        with self.assertRaisesRegex(ramdisk_manager.RamdiskError, "does not include"):
            ramdisk_manager.make_plan(
                product="iPhone12,1",
                os_version="18.5",
                build=None,
                profile_path=pathlib.Path(
                    "profiles/apple-a12-iphone-recovery.json"
                ),
            )

    def test_bundle_is_deterministic_and_inspection_verifies_components(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            first = ramdisk_manager.build_bundle(
                self.build_args(root, root / "first.fbrd")
            )
            second_args = self.build_args(root, root / "second.fbrd")
            second = ramdisk_manager.build_bundle(second_args)
            self.assertEqual(first["sha256"], second["sha256"])
            inspected = ramdisk_manager.inspect_bundle(root / "first.fbrd")
            self.assertTrue(inspected["ok"])
            self.assertEqual(inspected["component_count"], 4)
            self.assertEqual(
                inspected["manifest"]["target"]["product"], "iPhone12,1"
            )
            self.assertFalse(
                inspected["manifest"]["physical_execution_verified"]
            )

    def test_inspection_rejects_archive_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            output = root / "bundle.fbrd"
            ramdisk_manager.build_bundle(self.build_args(root, output))
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(output, "a") as bundle:
                    bundle.writestr("components/ramdisk/ramdisk", b"tampered")
            with self.assertRaisesRegex(ramdisk_manager.RamdiskError, "duplicate"):
                ramdisk_manager.inspect_bundle(output)

    def test_load_is_plan_only_by_default_and_adapter_execution_is_evidenced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            output = root / "bundle.fbrd"
            ramdisk_manager.build_bundle(self.build_args(root, output))
            plan_args = argparse.Namespace(
                bundle=output,
                adapter=None,
                ecid="1234",
                execute=False,
                owner_authorization=None,
                confirm=None,
                timeout=5.0,
                evidence=root / "plan.json",
            )
            plan = ramdisk_manager.load_bundle(plan_args)
            self.assertFalse(plan["executed"])
            self.assertTrue((root / "plan.json").is_file())

            adapter = root / "adapter"
            adapter.write_text(
                "#!/usr/bin/env python3\n"
                "import json, sys\n"
                "request = json.load(sys.stdin)\n"
                "print(json.dumps({'schema_version': 1, 'ok': True, "
                "'status': 'ramdisk-started', "
                "'bundle': request['bundle']['sha256']}))\n",
                encoding="utf-8",
            )
            adapter.chmod(0o755)
            execute_args = argparse.Namespace(
                bundle=output,
                adapter=str(adapter),
                ecid="1234",
                execute=True,
                owner_authorization=ramdisk_manager.OWNER_AUTHORIZATION,
                confirm=ramdisk_manager.EXECUTION_CONFIRMATION,
                timeout=5.0,
                evidence=root / "result.json",
            )
            result = ramdisk_manager.load_bundle(execute_args)
            self.assertTrue(result["executed"])
            self.assertEqual(
                result["adapter_response"]["status"], "ramdisk-started"
            )
            self.assertTrue((root / "result.json").is_file())

    def test_execution_requires_exact_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            output = root / "bundle.fbrd"
            ramdisk_manager.build_bundle(self.build_args(root, output))
            args = argparse.Namespace(
                bundle=output,
                adapter="/does/not/exist",
                ecid=None,
                execute=True,
                owner_authorization="yes",
                confirm=ramdisk_manager.EXECUTION_CONFIRMATION,
                timeout=5.0,
                evidence=None,
            )
            with self.assertRaisesRegex(
                ramdisk_manager.RamdiskError, "owner-authorization"
            ):
                ramdisk_manager.load_bundle(args)


if __name__ == "__main__":
    unittest.main()
