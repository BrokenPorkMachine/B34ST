#!/usr/bin/env python3
"""Create deterministic FBR34KER release ZIP archives.

Archive kinds:
  source      — Full source tree (excludes build artifacts)
  complete    — Source + all build artifacts, boot images, simulations
  sdk         — Minimal SDK-only: headers, library, examples, templates, tests
  operational — Public release: B34ST, scripts, tests, all builds, SDK,
                host tools, linker, profiles, modules, curated docs, tutorial,
                and CLI. Excludes private firmware/platform source code.
  all         — source + complete + sdk + operational
"""

from __future__ import annotations

import argparse
import hashlib
import os
import pathlib
import re
import stat
import subprocess
import time
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]

# ── Private/internal source directories (excluded from operational release) ──
PRIVATE_SOURCE_DIRS = {
    "kernel", "arch", "platform",
}
OPERATIONAL_EXCLUDED_DIRS = {
    ".git", "__pycache__",
    "runtime-artifacts", "diagnostics", "dist", "validation-logs",
    "FBR34KER_0.1",
    "FBR34KER_0.1.1",
}
SDK_INCLUDED_TOP_LEVEL = {
    "README.md", "LICENSE", "CHANGELOG.md", "TUTORIAL.md",
}
SDK_INCLUDED_DOCS = {
    "ARCHITECTURE.md",
    "LOADER_SDK.md",
    "BINARY_HANDOFF.md",
    "HANDOFF.md",
    "LOADER_CONFORMANCE.md",
    "LOADER_SIMULATOR.md",
    "PORTING.md",
    "PORT_CERTIFICATION.md",
    "FIRST_STAGE_ADAPTER.md",
    "MODULE_FORMAT.md",
    "BRIDGE_PROTOCOL.md",
    "HOST_PROTOCOL.md",
    "DEPLOYMENT_PROTOCOL.md",
    "PLATFORM_SERVICES.md",
    "BOOT_IMAGE.md",
    "QUICK_START.md",
}

SOURCE_EXCLUDED_DIRS = {
    ".git", "__pycache__", "build", "build-generic", "build-loader", "build-hardware-probe", "build-sdk", "build-integration",
    "runtime-artifacts", "diagnostics", "dist", "validation-logs", "build-apple",
    ".pytest_cache", ".ruff_cache",
}
SOURCE_EXCLUDED_NAMES = {
    ".DS_Store", "RELEASE_MANIFEST.json", "CHECKSUMS.sha256",
    "b34st_complete.tar.gz", "idevicerestore_verbose.log",
}
COMPLETE_ARTIFACTS = (
    # QEMU virt monitor
    pathlib.Path("build/fbr34ker.bin"),
    pathlib.Path("build/fbr34ker.elf"),
    pathlib.Path("build/fbr34ker.map"),
    pathlib.Path("build/modules/hello-dynamic.fmod"),
    # Generic ARM64 monitor
    pathlib.Path("build-generic/fbr34ker-generic.bin"),
    pathlib.Path("build-generic/fbr34ker-generic.elf"),
    pathlib.Path("build-generic/fbr34ker-generic.map"),
    # Operational/exploit build (security model enabled)
    pathlib.Path("build-exploit/fbr34ker-operational.bin"),
    pathlib.Path("build-exploit/fbr34ker-operational.elf"),
    pathlib.Path("build-exploit/fbr34ker-operational.map"),
    # QEMU handoff loader
    pathlib.Path("build-loader/fbr34ker-qemu-loader.bin"),
    pathlib.Path("build-loader/fbr34ker-qemu-loader.elf"),
    pathlib.Path("build-loader/fbr34ker-qemu-loader.map"),
    # Hardware probe image
    pathlib.Path("build-hardware-probe/fbr34ker-hardware-probe.bin"),
    pathlib.Path("build-hardware-probe/fbr34ker-hardware-probe.elf"),
    pathlib.Path("build-hardware-probe/fbr34ker-hardware-probe.map"),
    # SDK library
    pathlib.Path("build-sdk/libfbr34ker_sdk.a"),
    # SDK compiled examples and test harness
    pathlib.Path("build-sdk/examples/minimal_loader"),
    pathlib.Path("build-sdk/examples/callback_console"),
    pathlib.Path("build-sdk/examples/framebuffer_loader"),
    pathlib.Path("build-sdk/tests/sdk_harness"),
    # Handoff binary and conformance
    pathlib.Path("build/handoff/handoff-v4.fbhb"),
    pathlib.Path("build/handoff/sdk-conformance.json"),
    # Loader simulation outputs
    pathlib.Path("build/loader-simulation/loader-conformance.json"),
    pathlib.Path("build/loader-simulation/normalized-handoff.json"),
    pathlib.Path("build/loader-simulation/sparse-memory.json"),
    pathlib.Path("build/loader-simulation/handoff-v4.bin"),
    pathlib.Path("build/loader-simulation/memory-regions.bin"),
    pathlib.Path("build/loader-simulation/platform-services.bin"),
    pathlib.Path("build/loader-simulation/callback-stubs.bin"),
    pathlib.Path("build/loader-simulation/boot-modules.bin"),
    # Deployment simulation
    pathlib.Path("build/deployment-simulation/simulation-summary.json"),
    pathlib.Path("build/deployment-simulation/evidence.zip"),
    # Apple-family boot images
    pathlib.Path("build-apple/a12/boot.img"),
    pathlib.Path("build-apple/a12/boot.img.json"),
    pathlib.Path("build-apple/a12/boot.raw"),
    pathlib.Path("build-apple/a12/boot.raw.json"),
    pathlib.Path("build-apple/a12x/boot.img"),
    pathlib.Path("build-apple/a12x/boot.img.json"),
    pathlib.Path("build-apple/a12x/boot.raw"),
    pathlib.Path("build-apple/a12x/boot.raw.json"),
    pathlib.Path("build-apple/a13/boot.img"),
    pathlib.Path("build-apple/a13/boot.img.json"),
    pathlib.Path("build-apple/a13/boot.raw"),
    pathlib.Path("build-apple/a13/boot.raw.json"),
    pathlib.Path("build-apple/a14/boot.img"),
    pathlib.Path("build-apple/a14/boot.img.json"),
    pathlib.Path("build-apple/a14/boot.raw"),
    pathlib.Path("build-apple/a14/boot.raw.json"),
    pathlib.Path("build-apple/a15/boot.img"),
    pathlib.Path("build-apple/a15/boot.img.json"),
    pathlib.Path("build-apple/a15/boot.raw"),
    pathlib.Path("build-apple/a15/boot.raw.json"),
    pathlib.Path("build-apple/m1/boot.img"),
    pathlib.Path("build-apple/m1/boot.img.json"),
    pathlib.Path("build-apple/m1/boot.raw"),
    pathlib.Path("build-apple/m1/boot.raw.json"),
    pathlib.Path("build-apple/m2/boot.img"),
    pathlib.Path("build-apple/m2/boot.img.json"),
    pathlib.Path("build-apple/m2/boot.raw"),
    pathlib.Path("build-apple/m2/boot.raw.json"),
    # Apple bring-up simulation
    pathlib.Path("build-apple/bringup-simulation/simulation-summary.json"),
    pathlib.Path("build-apple/bringup-simulation/success-evidence.zip"),
    pathlib.Path("build-apple/bringup-simulation/failure-evidence.zip"),
    pathlib.Path("build-apple/bringup-simulation/recovered-evidence.zip"),
    # Physical integration simulation
    pathlib.Path("build-apple/physical-integration-simulation/simulation-summary.json"),
    pathlib.Path("build-apple/physical-integration-simulation/success-session.zip"),
    pathlib.Path("build-apple/physical-integration-simulation/failure-session.zip"),
    pathlib.Path("build-apple/physical-integration-simulation/recovered-session.zip"),
    # Physical validation candidate
    pathlib.Path("build-apple/physical-validation-candidate/summary.json"),
    pathlib.Path("build-apple/physical-validation-candidate/candidate-report.json"),
    pathlib.Path("build-apple/physical-validation-candidate/qemu-summary.json"),
    pathlib.Path("build-apple/physical-validation-candidate/success-session.zip"),
    pathlib.Path("build-apple/physical-validation-candidate/failure-session.zip"),
    pathlib.Path("build-apple/physical-validation-candidate/recovered-session.zip"),
    pathlib.Path("build-apple/physical-validation-candidate/failure-matrix/console.zip"),
    pathlib.Path("build-apple/physical-validation-candidate/failure-matrix/memory-map.zip"),
    pathlib.Path("build-apple/physical-validation-candidate/failure-matrix/timer.zip"),
    pathlib.Path("build-apple/physical-validation-candidate/failure-matrix/boot-evidence.zip"),
    # Release metadata
    pathlib.Path("RELEASE_MANIFEST.json"),
    pathlib.Path("CHECKSUMS.sha256"),
    # Tutorial (also in source, listed here for explicit verification)
    pathlib.Path("TUTORIAL.md"),
)
EXECUTABLE_PATHS = {
    pathlib.Path("fbr34ker"),
    pathlib.Path("b34stctl"),
    pathlib.Path("scripts/B34ST"),
    pathlib.Path("host/fbr34kctl"),
    pathlib.Path("host/forgectl"),
    pathlib.Path("host/fbr34kdeploy"),
    pathlib.Path("host/fbr34kdeploy-target"),
    pathlib.Path("host/fbr34kbootimg"),
    pathlib.Path("host/fbr34kirecovery"),
    pathlib.Path("host/fbr34kbringup"),
    pathlib.Path("host/fbr34kdevice"),
    pathlib.Path("host/fbr34kbridge"),
    pathlib.Path("host/fbr34ksession"),
    pathlib.Path("host/fbr34khardware"),
    pathlib.Path("examples/tether_adapter_contract_example.py"),
}
BUILD_OUTPUT_DIRS = (
    "build",
    "build-generic",
    "build-loader",
    "build-hardware-probe",
    "build-sdk",
    "build-integration",
    "build-apple",
    "build-exploit",
)
TRANSIENT_BUILD_SUFFIXES = {".d", ".o", ".pyc", ".tmp"}
RELEASE_NAME_RE = re.compile(r"(?:FBR34KER|B34ST)_[A-Za-z0-9][A-Za-z0-9._-]*")


def hash_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def executable_path(path: pathlib.Path) -> bool:
    if path in EXECUTABLE_PATHS:
        return True
    if path.parts and path.parts[0] == "scripts" and path.suffix in {".py", ".sh"}:
        return True
    if path.parts and path.parts[0] == "host" and path.suffix == ".py":
        return True
    return False


def validate_release_name(release_name: str) -> None:
    if RELEASE_NAME_RE.fullmatch(release_name) is None:
        raise ValueError(
            "release name must use FBR34KER_ or B34ST_ followed by "
            "letters, digits, dots, underscores, or hyphens"
        )


def _tracked_paths() -> list[pathlib.Path] | None:
    """List tracked paths while retaining modified working-tree contents."""
    if not (ROOT / ".git").exists():
        return None
    try:
        completed = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "-z"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return [
        pathlib.Path(os.fsdecode(value))
        for value in completed.stdout.split(b"\0")
        if value
    ]


def source_paths() -> list[pathlib.Path]:
    results: list[pathlib.Path] = []
    tracked = _tracked_paths()
    candidates = tracked if tracked is not None else [
        path.relative_to(ROOT) for path in ROOT.rglob("*")
    ]
    for relative in candidates:
        path = ROOT / relative
        if path.is_symlink():
            raise ValueError(f"release source contains a symbolic link: {relative}")
        if any(part in SOURCE_EXCLUDED_DIRS for part in relative.parts):
            continue
        if relative.parts and relative.parts[0].startswith("build-"):
            continue
        if path.is_dir():
            continue
        if path.name in SOURCE_EXCLUDED_NAMES:
            continue
        if path.suffix in {".pyc", ".tmp", ".zip"}:
            continue
        results.append(relative)
    return sorted(results, key=lambda value: value.as_posix())


def sdk_paths() -> list[pathlib.Path]:
    """Return paths for a minimal SDK-only release (headers, library, tests)."""
    results: list[pathlib.Path] = []

    # SDK source tree
    for path in (ROOT / "sdk").rglob("*"):
        relative = path.relative_to(ROOT)
        if path.is_symlink():
            raise ValueError(f"SDK release contains a symbolic link: {relative}")
        if path.is_dir():
            continue
        if path.suffix in {".pyc", ".o"}:
            continue
        results.append(relative)

    # SDK build artifacts
    sdk_build = ROOT / "build-sdk"
    if sdk_build.is_dir():
        for path in sdk_build.rglob("*"):
            relative = path.relative_to(ROOT)
            if path.is_symlink():
                raise ValueError(f"SDK release contains a symbolic link: {relative}")
            if path.is_dir():
                continue
            if path.suffix in TRANSIENT_BUILD_SUFFIXES:
                continue
            results.append(relative)

    # Top-level files
    for name in SDK_INCLUDED_TOP_LEVEL:
        path = ROOT / name
        if path.is_file():
            results.append(pathlib.Path(name))

    # Curated docs
    for name in SDK_INCLUDED_DOCS:
        path = ROOT / "docs" / name
        if path.is_file():
            results.append(pathlib.Path("docs") / name)

    return sorted(results, key=lambda value: value.as_posix())


def operational_paths() -> list[pathlib.Path]:
    """Return paths for the public operational release — no private code.

    Includes all source, scripts, tests, build artifacts, B34ST, SDK, linker
    scripts, profiles, demo modules, curated docs, host-side runtime tools, and
    CLI — but excludes kernel/, arch/, and platform/ firmware source.
    """
    results = {
        relative
        for relative in source_paths()
        if not any(part in PRIVATE_SOURCE_DIRS for part in relative.parts)
        and not any(part in OPERATIONAL_EXCLUDED_DIRS for part in relative.parts)
    }

    # Build products are generated and therefore untracked. Include them only
    # from known output roots, excluding compiler intermediates and staging.
    for directory in BUILD_OUTPUT_DIRS:
        root = ROOT / directory
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            relative = path.relative_to(ROOT)
            if path.is_symlink():
                raise ValueError(
                    f"operational release contains a symbolic link: {relative}"
                )
            if path.is_dir():
                continue
            nested = relative.parts[1:]
            if (
                "install-test" in nested
                or "__pycache__" in nested
                or path.suffix in TRANSIENT_BUILD_SUFFIXES | {".zip"}
            ):
                continue
            results.add(relative)

    return sorted(results, key=lambda value: value.as_posix())


def archive_timestamp() -> tuple[int, int, int, int, int, int]:
    raw = os.environ.get("SOURCE_DATE_EPOCH")
    if raw is None:
        # Earliest ZIP timestamp. This makes release archives reproducible on
        # hosts with different checkout mtimes and time zones.
        return (1980, 1, 1, 0, 0, 0)
    try:
        epoch = int(raw)
    except ValueError as exc:
        raise ValueError("SOURCE_DATE_EPOCH must be an integer") from exc
    value = time.gmtime(epoch)
    year = min(max(value.tm_year, 1980), 2107)
    return (year, value.tm_mon, value.tm_mday, value.tm_hour, value.tm_min,
            value.tm_sec - (value.tm_sec % 2))


def write_archive(
    archive: pathlib.Path,
    release_name: str,
    paths: list[pathlib.Path],
) -> None:
    validate_release_name(release_name)
    timestamp = archive_timestamp()
    temporary = archive.with_suffix(archive.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()
    with zipfile.ZipFile(
        temporary,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
        strict_timestamps=True,
    ) as bundle:
        for relative in paths:
            source = ROOT / relative
            if not source.is_file():
                raise FileNotFoundError(f"release input does not exist: {relative}")
            name = f"{release_name}/{relative.as_posix()}"
            info = zipfile.ZipInfo(name, date_time=timestamp)
            info.create_system = 3
            mode = stat.S_IFREG | (0o755 if executable_path(relative) else 0o644)
            info.external_attr = mode << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            info.flag_bits |= 0x800
            bundle.writestr(info, source.read_bytes(), compress_type=zipfile.ZIP_DEFLATED,
                            compresslevel=9)
    temporary.replace(archive)


def verify_archive(
    archive: pathlib.Path,
    release_name: str,
    *,
    complete: bool = False,
    sdk: bool = False,
    operational: bool = False,
) -> None:
    prefix = f"{release_name}/"
    seen: set[str] = set()
    with zipfile.ZipFile(archive) as bundle:
        bad = bundle.testzip()
        if bad is not None:
            raise ValueError(f"archive CRC failure: {bad}")
        names = bundle.namelist()
        for info in bundle.infolist():
            name = info.filename
            if name in seen:
                raise ValueError(f"duplicate archive member: {name}")
            seen.add(name)
            if not name.startswith(prefix):
                raise ValueError(f"archive member has wrong root: {name}")
            if "\\" in name:
                raise ValueError(f"archive member contains a backslash: {name}")
            relative = pathlib.PurePosixPath(name[len(prefix):])
            if not relative.parts or ".." in relative.parts or relative.is_absolute():
                raise ValueError(f"unsafe archive member: {name}")
            if "__pycache__" in relative.parts or relative.suffix == ".pyc":
                raise ValueError(f"transient Python file in archive: {name}")
            if relative.name == ".DS_Store" or ".git" in relative.parts:
                raise ValueError(f"transient metadata in archive: {name}")
            if operational and any(part in PRIVATE_SOURCE_DIRS for part in relative.parts):
                raise ValueError(f"operational release contains private code: {name}")
            expected_exec = executable_path(pathlib.Path(relative.as_posix()))
            mode = (info.external_attr >> 16) & 0o777
            if expected_exec and mode != 0o755:
                raise ValueError(f"executable mode missing for {name}: {oct(mode)}")
            if not expected_exec and mode not in {0o644, 0o755}:
                raise ValueError(f"unexpected file mode for {name}: {oct(mode)}")
        if complete:
            for relative in COMPLETE_ARTIFACTS:
                member = f"{prefix}{relative.as_posix()}"
                if member not in names:
                    raise ValueError(f"complete archive is missing {relative}")
        elif sdk:
            allowed_build_prefixes = {"build-sdk"}
            for name in names:
                relative = pathlib.PurePosixPath(name[len(prefix):])
                if not relative.parts:
                    continue
                first = relative.parts[0]
                if first == "build" or first.startswith("build-"):
                    if first not in allowed_build_prefixes:
                        raise ValueError(f"SDK archive contains private build product: {relative}")
        elif not operational:
            for name in names:
                relative = pathlib.PurePosixPath(name[len(prefix):])
                if relative.parts and (relative.parts[0] == "build" or
                                       relative.parts[0].startswith("build-")):
                    raise ValueError("source archive contains build products")


def write_checksum(path: pathlib.Path) -> pathlib.Path:
    checksum = path.with_suffix(path.suffix + ".sha256")
    checksum.write_text(f"{hash_file(path)}  {path.name}\n", encoding="ascii")
    return checksum


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-name", required=True)
    parser.add_argument("--output-dir", type=pathlib.Path, default=ROOT.parent)
    parser.add_argument("--kind", choices=("source", "complete", "sdk", "operational", "all"),
                        default="all")
    arguments = parser.parse_args(argv)

    try:
        validate_release_name(arguments.release_name)
    except ValueError as exc:
        parser.error(str(exc))
    output_dir = arguments.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    sources = source_paths()
    created: list[pathlib.Path] = []

    if arguments.kind in {"source", "all"}:
        archive = output_dir / f"{arguments.release_name}_source.zip"
        write_archive(archive, arguments.release_name, sources)
        verify_archive(archive, arguments.release_name, complete=False)
        created.extend((archive, write_checksum(archive)))

    if arguments.kind in {"complete", "all"}:
        missing = [path for path in COMPLETE_ARTIFACTS if not (ROOT / path).is_file()]
        if missing:
            parser.error("complete archive inputs are missing: " +
                         ", ".join(path.as_posix() for path in missing))
        complete_paths = sorted(set(sources).union(COMPLETE_ARTIFACTS),
                                key=lambda value: value.as_posix())
        archive = output_dir / f"{arguments.release_name}_complete.zip"
        write_archive(archive, arguments.release_name, complete_paths)
        verify_archive(archive, arguments.release_name, complete=True)
        created.extend((archive, write_checksum(archive)))

    if arguments.kind in {"sdk", "all"}:
        sdks = sdk_paths()
        archive = output_dir / f"{arguments.release_name}_sdk.zip"
        write_archive(archive, arguments.release_name, sdks)
        verify_archive(archive, arguments.release_name, sdk=True)
        sdk_build_marker = pathlib.Path("build-sdk/libfbr34ker_sdk.a")
        prefix = f"{arguments.release_name}/"
        with zipfile.ZipFile(archive) as bundle:
            names = bundle.namelist()
            if f"{prefix}{sdk_build_marker.as_posix()}" not in names:
                parser.error("SDK archive is missing the SDK library — "
                             "run 'make sdk' first")
            doc_count = sum(1 for n in names if n.startswith(f"{prefix}docs/"))
            if doc_count < 5:
                parser.error(f"SDK archive only has {doc_count} docs (expected ≥5)")
        created.extend((archive, write_checksum(archive)))

    if arguments.kind in {"operational", "all"}:
        paths = operational_paths()
        archive = output_dir / f"{arguments.release_name}_operational.zip"
        write_archive(archive, arguments.release_name, paths)
        verify_archive(archive, arguments.release_name, operational=True)
        # Verify no private source dirs leaked in
        prefix = f"{arguments.release_name}/"
        with zipfile.ZipFile(archive) as bundle:
            names = bundle.namelist()
            for private_dir in PRIVATE_SOURCE_DIRS:
                if any(f"{prefix}{private_dir}/" in n for n in names):
                    parser.error(f"operational archive leaked private dir: {private_dir}")
            doc_count = sum(1 for n in names if n.startswith(f"{prefix}docs/"))
            if doc_count < 5:
                parser.error(f"operational archive only has {doc_count} docs (expected ≥5)")
            b34st_count = sum(1 for n in names if n.startswith(f"{prefix}b34st/"))
            if b34st_count < 5:
                parser.error("operational archive is missing B34ST")
        created.extend((archive, write_checksum(archive)))

    for path in created:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
