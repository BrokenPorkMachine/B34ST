#!/usr/bin/env python3
"""Create deterministic FBR34KER source and complete release ZIP archives."""

from __future__ import annotations

import argparse
import hashlib
import os
import pathlib
import stat
import time
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]

SOURCE_EXCLUDED_DIRS = {
    ".git", "__pycache__", "build", "build-generic", "build-loader", "build-hardware-probe", "build-sdk", "build-integration",
    "runtime-artifacts", "diagnostics", "dist", "validation-logs", "build-apple",
}
SOURCE_EXCLUDED_NAMES = {
    ".DS_Store", "RELEASE_MANIFEST.json", "CHECKSUMS.sha256",
}
COMPLETE_ARTIFACTS = (
    pathlib.Path("build/fbr34ker.bin"),
    pathlib.Path("build/fbr34ker.elf"),
    pathlib.Path("build/fbr34ker.map"),
    pathlib.Path("build/modules/hello-dynamic.fmod"),
    pathlib.Path("build-generic/fbr34ker-generic.bin"),
    pathlib.Path("build-generic/fbr34ker-generic.elf"),
    pathlib.Path("build-generic/fbr34ker-generic.map"),
    pathlib.Path("build-loader/fbr34ker-qemu-loader.bin"),
    pathlib.Path("build-loader/fbr34ker-qemu-loader.elf"),
    pathlib.Path("build-loader/fbr34ker-qemu-loader.map"),
    pathlib.Path("build-hardware-probe/fbr34ker-hardware-probe.bin"),
    pathlib.Path("build-hardware-probe/fbr34ker-hardware-probe.elf"),
    pathlib.Path("build-hardware-probe/fbr34ker-hardware-probe.map"),
    pathlib.Path("build-sdk/libfbr34ker_sdk.a"),
    pathlib.Path("build/loader-simulation/handoff-v4.fbhb"),
    pathlib.Path("build/loader-simulation/sdk-conformance.json"),
    pathlib.Path("build/loader-simulation/loader-conformance.json"),
    pathlib.Path("build/loader-simulation/normalized-handoff.json"),
    pathlib.Path("build/loader-simulation/sparse-memory.json"),
    pathlib.Path("build/loader-simulation/handoff-v4.bin"),
    pathlib.Path("build/loader-simulation/memory-regions.bin"),
    pathlib.Path("build/loader-simulation/platform-services.bin"),
    pathlib.Path("build/loader-simulation/callback-stubs.bin"),
    pathlib.Path("build/loader-simulation/boot-modules.bin"),
    pathlib.Path("build/deployment-simulation/simulation-summary.json"),
    pathlib.Path("build/deployment-simulation/evidence.zip"),
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
    pathlib.Path("build-apple/bringup-simulation/simulation-summary.json"),
    pathlib.Path("build-apple/bringup-simulation/success-evidence.zip"),
    pathlib.Path("build-apple/bringup-simulation/failure-evidence.zip"),
    pathlib.Path("build-apple/bringup-simulation/recovered-evidence.zip"),
    pathlib.Path("build-apple/physical-integration-simulation/simulation-summary.json"),
    pathlib.Path("build-apple/physical-integration-simulation/success-session.zip"),
    pathlib.Path("build-apple/physical-integration-simulation/failure-session.zip"),
    pathlib.Path("build-apple/physical-integration-simulation/recovered-session.zip"),
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
    pathlib.Path("RELEASE_MANIFEST.json"),
    pathlib.Path("CHECKSUMS.sha256"),
)
EXECUTABLE_PATHS = {
    pathlib.Path("fbr34ker"),
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
}


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


def source_paths() -> list[pathlib.Path]:
    results: list[pathlib.Path] = []
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
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
        if path.suffix in {".pyc", ".zip"}:
            continue
        results.append(relative)
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
    complete: bool,
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
        else:
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
    parser.add_argument("--kind", choices=("source", "complete", "all"), default="all")
    arguments = parser.parse_args(argv)

    if not arguments.release_name.startswith("FBR34KER_"):
        parser.error("release name must start with FBR34KER_")
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

    for path in created:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
