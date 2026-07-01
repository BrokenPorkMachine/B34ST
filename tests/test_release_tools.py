from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import collect_diagnostics  # noqa: E402
import package_release  # noqa: E402
import qemu_smoke  # noqa: E402
import release_gate  # noqa: E402


class ReleaseToolTests(unittest.TestCase):
    def run_python(self, script: str, *arguments: str, cwd: pathlib.Path | None = None):
        return subprocess.run(
            [sys.executable, str(ROOT / script), *arguments],
            cwd=cwd or ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=30,
            check=False,
        )

    def test_doctor_json_uses_sanitized_executable_names(self) -> None:
        completed = self.run_python("scripts/doctor.py", "--json")
        self.assertEqual(completed.returncode, 0, completed.stdout)
        report = json.loads(completed.stdout)
        self.assertTrue(report["passed"])
        self.assertNotIn("project_root", report)
        self.assertNotIn("path", report)
        for check in report["checks"]:
            path = check["path"]
            if path is not None:
                self.assertEqual(pathlib.Path(path).name, path)

    def test_release_manifest_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            artifact = root / "monitor.bin"
            artifact.write_bytes(b"deterministic-monitor")
            command = (
                "scripts/release_manifest.py",
                "--version",
                "0.2.0",
                "--release-name",
                "FBR34KER_test",
                "--channel",
                "public-preview",
                "--source-id",
                "0.2.0-public-preview",
                "--output",
                "manifest.json",
                "--checksums",
                "checksums.sha256",
                "monitor.bin",
            )
            first = self.run_python(*command, cwd=root)
            self.assertEqual(first.returncode, 0, first.stdout)
            manifest_one = (root / "manifest.json").read_bytes()
            checksums_one = (root / "checksums.sha256").read_bytes()
            second = self.run_python(*command, cwd=root)
            self.assertEqual(second.returncode, 0, second.stdout)
            self.assertEqual(manifest_one, (root / "manifest.json").read_bytes())
            self.assertEqual(checksums_one, (root / "checksums.sha256").read_bytes())

    def test_diagnostics_preserves_external_smoke_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            smoke = root / "smoke"
            smoke.mkdir()
            (smoke / "summary.json").write_text('{"passed": true}\n', encoding="utf-8")
            output = root / "diagnostics"
            completed = collect_diagnostics.main(
                [
                    "--output",
                    str(output),
                    "--smoke-dir",
                    str(smoke),
                    "--skip-tool-probes",
                ]
            )
            self.assertEqual(completed, 0)
            self.assertEqual(
                (output / "smoke" / "summary.json").read_text(encoding="utf-8"),
                '{"passed": true}\n',
            )
            archive = output.with_suffix(".zip")
            self.assertTrue(archive.is_file())
            tools = json.loads(
                (output / "tool-commands.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                tools["doctor"]["command"][0], pathlib.Path(sys.executable).name
            )
            self.assertNotIn(str(ROOT), json.dumps(tools))
            with zipfile.ZipFile(archive) as bundle:
                self.assertIn("diagnostics/smoke/summary.json", bundle.namelist())

    def test_environment_target_does_not_redirect_build_output(self) -> None:
        environment = {**os.environ, "TARGET": "poisoned-output"}
        completed = subprocess.run(
            [
                "make",
                "--no-print-directory",
                "-s",
                "-f",
                "Makefile",
                "print-target",
            ],
            cwd=ROOT,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=20,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout)
        self.assertEqual(completed.stdout.strip(), "build/fbr34ker")

    def test_command_line_target_override_is_supported(self) -> None:
        completed = subprocess.run(
            [
                "make",
                "--no-print-directory",
                "-s",
                "-f",
                "Makefile",
                "TARGET=custom/image",
                "print-target",
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=20,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout)
        self.assertEqual(completed.stdout.strip(), "custom/image")

    def test_version_consistency_accepts_beta_suffix(self) -> None:
        completed = self.run_python(
            "scripts/check_version_consistency.py", "--expected", "0.6.2b"
        )
        self.assertNotEqual(completed.returncode, 2, completed.stdout)
        self.assertNotIn("must be a release version", completed.stdout)

    def test_version_consistency_rejects_invalid_version(self) -> None:
        completed = self.run_python(
            "scripts/check_version_consistency.py", "--expected", "0.4.3beta"
        )
        self.assertEqual(completed.returncode, 2, completed.stdout)
        self.assertIn("must be a release version", completed.stdout)

    def test_smoke_report_paths_are_sanitized(self) -> None:
        self.assertEqual(
            qemu_smoke.display_path(ROOT / "build" / "fbr34ker.bin"),
            "build/fbr34ker.bin",
        )
        with tempfile.TemporaryDirectory() as directory:
            outside = pathlib.Path(directory) / "private-monitor.bin"
            self.assertEqual(qemu_smoke.display_path(outside), "private-monitor.bin")

    def test_gate_stage_logs_and_commands_are_sanitized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory)
            stage = release_gate.run_stage(
                "privacy",
                [sys.executable, "-c", f"print({str(ROOT)!r})"],
                output,
                5.0,
            )
            self.assertEqual(stage.status, "passed")
            self.assertEqual(stage.command[0], pathlib.Path(sys.executable).name)
            log = (output / str(stage.log)).read_text(encoding="utf-8")
            self.assertNotIn(str(ROOT), log)
            self.assertEqual(log.strip(), ".")

    def test_source_package_is_reproducible_and_preserves_modes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            first = root / "first.zip"
            second = root / "second.zip"
            paths = package_release.source_paths()
            package_release.write_archive(first, "FBR34KER_test", paths)
            package_release.write_archive(second, "FBR34KER_test", paths)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            package_release.verify_archive(first, "FBR34KER_test", complete=False)
            with zipfile.ZipFile(first) as bundle:
                launcher = bundle.getinfo("FBR34KER_test/fbr34ker")
                self.assertEqual((launcher.external_attr >> 16) & 0o777, 0o755)
                self.assertFalse(any("/build/" in name for name in bundle.namelist()))
                self.assertFalse(
                    any("/validation-logs/" in name for name in bundle.namelist())
                )
                self.assertFalse(
                    any("/.pytest_cache/" in name for name in bundle.namelist())
                )
                self.assertFalse(
                    any("/.ruff_cache/" in name for name in bundle.namelist())
                )
                self.assertFalse(
                    any(name.endswith(".tmp") for name in bundle.namelist())
                )
                self.assertFalse(
                    any(name.endswith(".tar.gz") for name in bundle.namelist())
                )

            extracted = root / "extracted"
            with zipfile.ZipFile(first) as bundle:
                bundle.extractall(extracted)
            project = extracted / "FBR34KER_test"
            launcher = project / "fbr34ker"
            shebang = launcher.read_text().splitlines()[0]
            if shebang.startswith("#!"):
                parts = shebang[2:].split()
                if parts[0].endswith("/env") and len(parts) > 1:
                    interpreter = shutil.which(parts[1]) or parts[1]
                else:
                    interpreter = parts[0]
            else:
                interpreter = shutil.which("sh") or "sh"
            completed = subprocess.run(
                [interpreter, str(launcher), "--permissions"],
                cwd=project,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout)
            self.assertTrue(os.access(launcher, os.X_OK))
            self.assertTrue(os.access(project / "scripts" / "fbr34ker.sh", os.X_OK))

    def test_package_rejects_unsafe_release_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive = pathlib.Path(directory) / "unsafe.zip"
            with self.assertRaisesRegex(ValueError, "release name"):
                package_release.write_archive(
                    archive, "B34ST_../../outside", [pathlib.Path("README.md")]
                )

    def test_operational_package_keeps_required_host_runtime(self) -> None:
        paths = set(package_release.operational_paths())
        self.assertIn(pathlib.Path("host/process_support.py"), paths)
        self.assertIn(pathlib.Path("host/tls_support.py"), paths)
        self.assertIn(pathlib.Path("host/ipsw_manager.py"), paths)
        self.assertIn(
            pathlib.Path("examples/tether_adapter_contract_example.py"), paths
        )
        self.assertNotIn(pathlib.Path("kernel/main.c"), paths)
        self.assertNotIn(pathlib.Path("arch/arm64/start.S"), paths)
        self.assertNotIn(pathlib.Path("platform/qemu_virt/platform.c"), paths)
        self.assertFalse(
            any(
                ".pytest_cache" in path.parts or ".ruff_cache" in path.parts
                for path in paths
            )
        )
        self.assertFalse(any(path.suffix in {".d", ".o"} for path in paths))

    @unittest.skipUnless(shutil.which("openssl"), "OpenSSL is not installed")
    def test_release_verifier_accepts_signer_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            artifact = root / "monitor.bin"
            artifact.write_bytes(b"signed release artifact")
            generated = self.run_python(
                "scripts/release_manifest.py",
                "--version",
                "0.6.2b",
                "--release-name",
                "B34ST_0.6.0_Beta",
                "--channel",
                "beta",
                "--source-id",
                "0.6.0-beta",
                "--output",
                "manifest.json",
                "--checksums",
                "checksums.sha256",
                "monitor.bin",
                cwd=root,
            )
            self.assertEqual(generated.returncode, 0, generated.stdout)
            private_key = root / "private.pem"
            public_key = root / "public.pem"
            for command in (
                [
                    "openssl",
                    "genpkey",
                    "-algorithm",
                    "RSA",
                    "-pkeyopt",
                    "rsa_keygen_bits:2048",
                    "-out",
                    str(private_key),
                ],
                [
                    "openssl",
                    "pkey",
                    "-in",
                    str(private_key),
                    "-pubout",
                    "-out",
                    str(public_key),
                ],
                [
                    "openssl",
                    "dgst",
                    "-sha256",
                    "-sign",
                    str(private_key),
                    "-out",
                    str(root / "manifest.json.sig"),
                    str(root / "manifest.json"),
                ],
            ):
                completed = subprocess.run(
                    command,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    timeout=30,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, completed.stdout)
            verified = self.run_python(
                "scripts/release_verify.py",
                "manifest.json",
                "--root",
                ".",
                "--signature",
                "manifest.json.sig",
                "--public-key",
                "public.pem",
                "--json",
                cwd=root,
            )
            self.assertEqual(verified.returncode, 0, verified.stdout)
            self.assertTrue(json.loads(verified.stdout)["passed"])

    def test_release_verifier_handles_malformed_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            manifest = root / "manifest.json"
            manifest.write_text(
                '{"schema_version": 2, "artifacts": [{"path": null}]}',
                encoding="utf-8",
            )
            completed = self.run_python(
                "scripts/release_verify.py", str(manifest), "--json"
            )
            self.assertEqual(completed.returncode, 1, completed.stdout)
            result = json.loads(completed.stdout)
            self.assertFalse(result["passed"])
            self.assertIn("artifact path must be a string", result["errors"])

    def test_gate_summary_requires_every_release_stage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory)
            stages = [
                release_gate.StageResult(
                    "host-readiness", "passed", 0, 1, [], None, "ok"
                ),
                release_gate.StageResult("verify", "passed", 0, 1, [], None, "ok"),
                release_gate.StageResult(
                    "integration", "blocked", None, 0, [], None, "no qemu"
                ),
                release_gate.StageResult(
                    "smoke", "blocked", None, 0, [], None, "no qemu"
                ),
                release_gate.StageResult(
                    "generic-smoke", "blocked", None, 0, [], None, "no qemu"
                ),
                release_gate.StageResult(
                    "probe-smoke", "blocked", None, 0, [], None, "no qemu"
                ),
                release_gate.StageResult("diagnostics", "passed", 0, 1, [], None, "ok"),
            ]
            path = release_gate.write_summary(
                output, "0.2.0", "public-preview", stages, release_gate.time.monotonic()
            )
            report = json.loads(path.read_text(encoding="utf-8"))
            self.assertFalse(report["passed"])
            self.assertEqual(report["release_stage"], "public-preview")

    def test_qemu_runtime_validation_profile_is_complete(self) -> None:
        profile = json.loads(
            (ROOT / "profiles/qemu-runtime-validation.json").read_text(encoding="utf-8")
        )
        self.assertEqual(profile["schema_version"], 1)
        self.assertEqual(profile["machine"]["machine"], "virt,gic-version=3")
        self.assertEqual(profile["expected_outcome"], "rollback-then-recovery")
        sequence = profile["validation_sequence"]
        self.assertIn("fault-arm component-start 0 1 platform-catalog", sequence)
        self.assertEqual(sequence.count("architecture-restart"), 2)

    def test_qemu_smoke_reports_missing_emulator_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            image = root / "monitor.bin"
            module = root / "module.fmod"
            image.write_bytes(b"image")
            module.write_bytes(b"module")
            completed = self.run_python(
                "scripts/qemu_smoke.py",
                "--qemu",
                "definitely-not-a-qemu-binary",
                "--image",
                str(image),
                "--module",
                str(module),
                "--output",
                str(root / "output"),
                "--expected-version",
                "0.2.0",
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("QEMU executable was not found", completed.stdout)


if __name__ == "__main__":
    unittest.main()
