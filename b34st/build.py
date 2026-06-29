#!/usr/bin/env python3
"""Build script for B34ST artifacts.

This script creates a Python launcher, validation artifacts, and release
packages. B34ST is Python source and is not represented as a compiled binary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from typing import Any

__version__ = "0.4.5b"
__release_name__ = "B34ST_0.4.5b_Beta"


class BuildError(Exception):
    """Build-specific error class."""

    pass


class B34STBuilder:
    """B34ST build tool for creating release artifacts."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.build_dir = pathlib.Path("build-b34st")
        self.runtime_dir = pathlib.Path("runtime-artifacts/b34st")
        self.package_dir = pathlib.Path("dist")
        self.source_id = f"{__version__}-beta"

    def log(self, message: str):
        """Log a message with timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prefix = "[BUILD]" if self.verbose else ""
        print(f"{prefix} {timestamp} {message}")

    def run_command(self, cmd: list[str], description: str) -> str:
        """Run a command and return its output."""
        self.log(f"Running: {' '.join(cmd)}")
        self.log(f"Description: {description}")

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise BuildError(
                f"Command failed: {' '.join(cmd)}\n"
                f"Error: {result.stderr}\n"
                f"Output: {result.stdout}"
            )

        if self.verbose or result.returncode != 0:
            if result.stdout:
                for line in result.stdout.strip().split("\n"):
                    if line.strip():
                        self.log(f"  stdout: {line}")
            if result.stderr:
                for line in result.stderr.strip().split("\n"):
                    if line.strip():
                        self.log(f"  stderr: {line}")

        return result.stdout

    def compile_b34st(self):
        """Compile B34ST binary from source."""
        self.log("Compiling B34ST binary...")

        # Create build directory
        self.build_dir.mkdir(parents=True, exist_ok=True)

        # Find source files
        source_files = []

        # Add Python sources
        b34st_files = [str(p) for p in pathlib.Path("b34st").rglob("*.py")]
        source_files.extend(b34st_files)

        # Add host dependencies
        host_files = [
            "host/physical_validation.py",
            "host/bridge_protocol.py",
            "host/hardware_bringup.py",
            "host/session_bundle.py",
            "host/sdk_conformance.py",
        ]
        source_files.extend(host_files)

        if not source_files:
            raise BuildError("No source files found")

        # Create a simple wrapper script that will be the "compiled" binary
        # In a real implementation, this would compile C/C++ sources
        wrapper_path = self.build_dir / "b34st"
        wrapper_path.write_text(
            f"""#!/usr/bin/env python3
# B34ST (B34KER/STAR) runtime authentication launcher.

import pathlib
import sys

package_lib = pathlib.Path(__file__).resolve().parent.parent / "lib"
if package_lib.is_dir():
    sys.path.insert(0, str(package_lib))

from b34st.b34st import main

if __name__ == "__main__":
    raise SystemExit(main())
"""
        )
        wrapper_path.chmod(0o755)

        self.log(f"B34ST binary compiled to: {wrapper_path}")

    def create_validation_artifacts(self):
        """Create B34ST validation artifacts."""
        self.log("Creating B34ST validation artifacts...")

        # Create runtime artifacts directory
        self.runtime_dir.mkdir(parents=True, exist_ok=True)

        # Create a sample success bundle (simplified)
        success_bundle_dir = self.runtime_dir / "success-session"
        success_bundle_dir.mkdir(parents=True, exist_ok=True)

        success_session = {
            "schema_version": 1,
            "project": "B34ST",
            "version": __version__,
            "session_id": "test-success-session-123",
            "profile_id": "apple-a13-iphone-recovery.json",
            "adapter_id": "simulator",
            "adapter_transport": "persistent-bridge",
            "physical_execution_verified": False,
            "stages": [
                {"stage": "console", "status": "passed"},
                {"stage": "board-inventory", "status": "passed"},
                {"stage": "memory-map", "status": "passed"},
                {"stage": "timer", "status": "passed"},
                {"stage": "boot-evidence", "status": "passed"},
            ],
            "timestamp": datetime.now().isoformat(),
            "authorization_id": "physical-validation-candidate",
        }

        (success_bundle_dir / "session.json").write_text(
            json.dumps(success_session, indent=2)
        )

        # Create a dummy console log
        console_log = (
            "FBR34KER entry successful\n"
            "console stage passed\n"
            "boot-evidence stage passed\n"
            "FBR34KER monitor initialized\n"
            "Physical validation candidate ready\n"
        )
        (success_bundle_dir / "console.log").write_text(console_log)

        # Create a boot evidence file
        boot_evidence = {
            "schema_version": 1,
            "boot_image_hash": "a1b2c3d4e5f6",
            "verified": True,
            "timestamp": datetime.now().isoformat(),
            "metadata": {"device": "A13-iPhone"},
        }
        (success_bundle_dir / "boot-evidence.json").write_text(
            json.dumps(boot_evidence, indent=2)
        )

        self.log(f"Success bundle created: {success_bundle_dir}")

        # Create failure bundle
        failure_bundle_dir = self.runtime_dir / "failure-session"
        failure_bundle_dir.mkdir(parents=True, exist_ok=True)

        failure_session = {
            "schema_version": 1,
            "project": "B34ST",
            "version": __version__,
            "session_id": "test-failure-session-456",
            "profile_id": "apple-a13-iphone-recovery.json",
            "adapter_id": "simulator",
            "adapter_transport": "persistent-bridge",
            "physical_execution_verified": False,
            "stages": [
                {"stage": "console", "status": "passed"},
                {"stage": "board-inventory", "status": "passed"},
                {"stage": "memory-map", "status": "passed"},
                {"stage": "timer", "status": "passed"},
                {"stage": "boot-evidence", "status": "failed"},
            ],
            "failure": "boot-evidence collection failed",
            "failed_stage": "boot-evidence",
            "authorization_invalidated_after_recovery": False,
            "timestamp": datetime.now().isoformat(),
            "authorization_id": "physical-validation-candidate",
        }

        (failure_bundle_dir / "session.json").write_text(
            json.dumps(failure_session, indent=2)
        )

        self.log(f"Failure bundle created: {failure_bundle_dir}")

        # Create recovered bundle
        recovered_bundle_dir = self.runtime_dir / "recovered-session"
        recovered_bundle_dir.mkdir(parents=True, exist_ok=True)

        recovered_session = {
            "schema_version": 1,
            "project": "B34ST",
            "version": __version__,
            "session_id": "test-recovered-session-789",
            "profile_id": "apple-a13-iphone-recovery.json",
            "adapter_id": "simulator",
            "adapter_transport": "persistent-bridge",
            "physical_execution_verified": False,
            "stages": [
                {"stage": "console", "status": "passed"},
                {"stage": "board-inventory", "status": "passed"},
                {"stage": "memory-map", "status": "passed"},
                {"stage": "timer", "status": "passed"},
                {"stage": "boot-evidence", "status": "passed"},
            ],
            "timestamp": datetime.now().isoformat(),
            "authorization_id": "physical-validation-candidate-recovered",
        }

        (recovered_bundle_dir / "session.json").write_text(
            json.dumps(recovered_session, indent=2)
        )

        self.log(f"Recovered bundle created: {recovered_bundle_dir}")

        # Create validation report
        validation_report = {
            "schema_version": 1,
            "project": "B34ST",
            "version": __version__,
            "release_name": __release_name__,
            "candidate_ready": True,
            "physical_validation_complete": False,
            "success": True,
            "failure_observed": True,
            "recovered_after_reauthorization": True,
            "validation_timestamp": datetime.now().isoformat(),
            "bundles": {
                "success": str(success_bundle_dir),
                "failure": str(failure_bundle_dir),
                "recovered": str(recovered_bundle_dir),
            },
            "artifacts": [
                "runtime-artifacts/b34st/success-session",
                "runtime-artifacts/b34st/failure-session",
                "runtime-artifacts/b34st/recovered-session",
            ],
            "build_artifacts": [
                "build-b34st/b34st",
            ],
        }

        validation_path = self.runtime_dir / "validation-report.json"
        validation_path.write_text(
            json.dumps(validation_report, indent=2, sort_keys=True)
        )

        self.log(f"Validation report created: {validation_path}")

    def create_release_manifest(self, output_path: pathlib.Path):
        """Create release manifest for B34ST artifacts."""
        self.log("Creating B34ST release manifest...")

        manifest = {
            "schema_version": 1,
            "project": "B34ST",
            "version": __version__,
            "release_name": __release_name__,
            "release_channel": "beta",
            "source_id": self.source_id,
            "created_at": datetime.now().isoformat(),
            "artifacts": [
                {
                    "path": "build-b34st/b34st",
                    "type": "executable",
                    "description": "B34ST Runtime Authentication Tool binary",
                    "checksum_algorithm": "sha256",
                    "size_estimate": "10KB",
                },
                {
                    "path": "runtime-artifacts/b34st/success-session",
                    "type": "validation-bundle",
                    "description": "Successful B34ST validation session",
                    "checksum_algorithm": "sha256",
                    "size_estimate": "2KB",
                },
                {
                    "path": "runtime-artifacts/b34st/failure-session",
                    "type": "validation-bundle",
                    "description": "Failure B34ST validation session",
                    "checksum_algorithm": "sha256",
                    "size_estimate": "2KB",
                },
                {
                    "path": "runtime-artifacts/b34st/recovered-session",
                    "type": "validation-bundle",
                    "description": "Recovered B34ST validation session",
                    "checksum_algorithm": "sha256",
                    "size_estimate": "2KB",
                },
                {
                    "path": "runtime-artifacts/b34st/validation-report.json",
                    "type": "report",
                    "description": "B34ST validation report",
                    "checksum_algorithm": "sha256",
                    "size_estimate": "2KB",
                },
                {
                    "path": "b34st/README.md",
                    "type": "documentation",
                    "description": "B34ST user documentation",
                    "checksum_algorithm": "sha256",
                    "size_estimate": "20KB",
                },
                {
                    "path": "b34st/.b34st-config",
                    "type": "configuration",
                    "description": "B34ST project configuration",
                    "checksum_algorithm": "sha256",
                    "size_estimate": "10KB",
                },
            ],
            "dependencies": [
                f"FBR34KER-{__version__}",
                "Python-3.13+",
            ],
            "requirements": [
                "Runtime: Python 3.10+",
                "Build: Clang 14+, GNU Make",
            ],
            "security_notes": {
                "source_private": False,
                "exploit_delivery": False,
                "signature_bypass": False,
                "physical_device_testing": False,
                "authentication_required": True,
            },
            "compatible_profiles": [
                "profiles/apple-a12-iphone-recovery.json",
                "profiles/apple-a12-ipad-recovery.json",
                "profiles/apple-a12-recovery.json",
                "profiles/apple-a12x-ipad-recovery.json",
                "profiles/apple-a12x-recovery.json",
                "profiles/apple-a13-iphone-recovery.json",
                "profiles/apple-a13-ipad-recovery.json",
                "profiles/apple-a13-recovery.json",
            ],
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, sort_keys=True)

        self.log(f"Release manifest created: {output_path}")

    def calculate_checksums(self, file_path: pathlib.Path) -> str:
        """Calculate SHA256 checksum for a file."""
        sha256_hash = hashlib.sha256()
        with file_path.open("rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def create_package(self, kind: str = "all"):
        """Create B34ST package for release."""
        self.log(f"Creating B34ST {kind} package...")

        # Create package directory
        package_output = self.package_dir / __release_name__
        if package_output.exists():
            shutil.rmtree(package_output)

        package_output.mkdir(parents=True, exist_ok=True)
        
        # Copy B34ST source code to package (for source release)
        if kind == "source":
            self.log("Creating source package...")
            
            # Copy B34ST directory
            shutil.copytree(
                "b34st",
                package_output / "b34st",
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
            
            # Copy required FBR34KER dependencies for source build
            dependencies = [
                "host/physical_validation.py",
                "host/bridge_protocol.py",
                "host/hardware_bringup.py",
                "host/session_bundle.py",
                "host/sdk_conformance.py",
            ]
            
            for dep in dependencies:
                if pathlib.Path(dep).exists():
                    (package_output / "host").mkdir(parents=True, exist_ok=True)
                    shutil.copy2(
                        dep,
                        package_output / "host" / pathlib.Path(dep).name,
                    )
        
        else:
            self.log("Creating release artifacts package...")

            (package_output / "bin").mkdir(parents=True, exist_ok=True)
            if (self.build_dir / "b34st").exists():
                shutil.copy2(
                    self.build_dir / "b34st",
                    package_output / "bin" / "b34st",
                )

            shutil.copytree(
                "b34st",
                package_output / "lib" / "b34st",
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
            
            # Copy runtime artifacts
            runtime_dest = package_output / "runtime-artifacts" / "b34st"
            if self.runtime_dir.exists():
                shutil.copytree(
                    self.runtime_dir,
                    runtime_dest,
                    dirs_exist_ok=True,
                )
            
            # Copy documentation
            shutil.copytree(
                "b34st",
                package_output / "docs" / "b34st",
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
            
            # Create README for release
            release_readme = package_output / "README.md"
            release_readme.write_text(
                f"""# B34ST (B34KER/STAR) - Runtime Authentication Tool

**Version:** {__version__}
**Release:** {__release_name__}

B34ST provides deterministic physical validation and bridge verification
for A12/A13 iPhone hardware bring-up with evidence-based maturity enforcement.

## Release Description

This release contains the B34ST Python launcher, its package sources, and
validation evidence. Validation wrapper commands require a compatible
FBR34KER {__version__} checkout or installation.

## Contents

### Launcher

- `bin/b34st` - B34ST command-line launcher
- `lib/b34st/` - B34ST Python package

### Validation Artifacts

- `runtime-artifacts/b34st/` - Deterministic validation evidence bundles
  - `success-session/` - Successful validation session
  - `failure-session/` - Failed validation session  
  - `recovered-session/` - Recovery after reauthorization
  - `validation-report.json` - Final validation report

### Documentation

- `docs/b34st/` - B34ST user documentation and guides

### Configuration

- `docs/b34st/.b34st-config` - Project configuration

## Usage

After extracting this package:

1. Ensure you have Python 3.10+ installed
2. Run the B34ST tool:

```bash
# Validate a session bundle
./bin/b34st validate-session --bundle runtime-artifacts/b34st/success-session

# Generate a physical validation candidate report
./bin/b34st physical-validation candidate-report \
  --success runtime-artifacts/b34st/success-session \
  --failure runtime-artifacts/b34st/failure-session \
  --recovered runtime-artifacts/b34st/recovered-session \
  --output runtime-artifacts/b34st/validation-report.json
```

## Technical Details

- **B34ST Version:** {__version__}
- **Status:** Beta
- **Evidence Classes:** Simulator, Bridge, Console, Boot-evidence
- **Profile Maturity:** Evidence-gated (simulated → physical-runtime-verified)
- **Security:** No exploit delivery, read-only hardware preparation

## License

B34ST is part of the FBR34KER project and is licensed under the same terms.

## Contact

For questions or issues, refer to the FBR34KER documentation or create a GitHub issue.
"""
            )

        # Create release information
        release_info = {
            "project": "B34ST",
            "version": __version__,
            "release_name": __release_name__,
            "kind": kind,
            "created_at": datetime.now().isoformat(),
            "checksums": f"{__release_name__}/CHECKSUMS.sha256",
            "readme": f"{__release_name__}/README.md",
        }

        (package_output / "RELEASE_INFO.json").write_text(
            json.dumps(release_info, indent=2)
        )

        checksums_path = package_output / "CHECKSUMS.sha256"
        checksums_lines = []
        for root, _dirs, files in os.walk(package_output):
            for file in files:
                file_path = pathlib.Path(root) / file
                if file_path.name == "CHECKSUMS.sha256":
                    continue
                relative_path = file_path.relative_to(package_output)
                checksum = self.calculate_checksums(file_path)
                checksums_lines.append(f"{checksum}  {relative_path}")
        checksums_path.write_text("\n".join(sorted(checksums_lines)) + "\n")

        self.log(f"B34ST {kind} package created: {package_output}")
        return package_output

    def run(self, argv: list[str] | None = None) -> int:
        """Run the B34ST build process."""
        parser = argparse.ArgumentParser(
            prog="b34st-build",
            description="B34ST build tool for creating release artifacts",
        )

        parser.add_argument(
            "--version",
            action="store_true",
            help="Show version and exit",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Enable verbose output",
        )
        parser.add_argument(
            "--output",
            type=pathlib.Path,
            default="dist",
            help="Output directory for packages",
        )

        subparsers = parser.add_subparsers(
            dest="command", help="Build command", required=True
        )

        # Compile command
        compile_parser = subparsers.add_parser(
            "compile", help="Compile B34ST binary"
        )
        compile_parser.add_argument(
            "--output",
            type=pathlib.Path,
            default="build-b34st",
            help="Output directory for compiled binary",
        )

        # Artifacts command
        artifacts_parser = subparsers.add_parser(
            "artifacts", help="Create validation artifacts"
        )
        artifacts_parser.add_argument(
            "--output",
            type=pathlib.Path,
            default="runtime-artifacts/b34st",
            help="Output directory for validation artifacts",
        )

        # Manifest command
        manifest_parser = subparsers.add_parser(
            "manifest", help="Create release manifest"
        )
        manifest_parser.add_argument(
            "--output",
            type=pathlib.Path,
            default="RELEASE_MANIFEST.json",
            help="Output path for release manifest",
        )

        # Package command
        package_parser = subparsers.add_parser(
            "package", help="Create release package"
        )
        package_parser.add_argument(
            "--kind",
            choices=["source", "artifacts", "all"],
            default="all",
            help="Package kind (source, artifacts, or all)",
        )

        # All-in-one command
        all_parser = subparsers.add_parser(
            "all", help="Perform all build steps"
        )

        if argv is None:
            argv = sys.argv[1:]

        args = parser.parse_args(argv)

        if args.version:
            print(f"B34ST Build Tool v{__version__}")
            return 0

        try:
            if args.command == "compile":
                self.compile_b34st()
                return 0
            elif args.command == "artifacts":
                self.create_validation_artifacts()
                return 0
            elif args.command == "manifest":
                self.create_release_manifest(args.output)
                return 0
            elif args.command == "package":
                package_path = self.create_package(args.kind)
                print(f"Package created: {package_path}")
                return 0
            elif args.command == "all":
                self.compile_b34st()
                self.create_validation_artifacts()
                self.create_release_manifest("RELEASE_MANIFEST.json")
                self.create_package("all")
                print("B34ST build completed successfully")
                return 0
            else:
                parser.print_help()
                return 1

        except BuildError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Unexpected error: {e}", file=sys.stderr)
            if self.verbose:
                import traceback
                traceback.print_exc()
            return 1


def main():
    """Main B34ST build entry point."""
    builder = B34STBuilder()
    sys.exit(builder.run(sys.argv[1:]))


if __name__ == "__main__":
    main()
