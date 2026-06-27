from __future__ import annotations
import dataclasses, datetime, json, pathlib, subprocess, sys
from typing import Any, Callable


class FuzzerError(RuntimeError):
    pass


@dataclasses.dataclass
class FuzzTarget:
    name: str
    component: str
    description: str
    harness_path: str | None = None
    corpus_path: str | None = None
    fuzzer: str = "honggfuzz"
    args: list[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class FuzzResult:
    target: str
    runs: int
    crashes: int
    unique_crashes: int
    coverage: float
    time_seconds: int
    crashes_dir: pathlib.Path | None = None
    notes: str = ""


FUZZ_TARGETS: dict[str, FuzzTarget] = {
    "webkit-jscore": FuzzTarget(
        name="webkit-jscore",
        component="webkit",
        description="JavaScriptCore JIT compiler fuzzing",
        fuzzer="honggfuzz",
        args=["--threads", "2", "--timeout", "10"],
    ),
    "webkit-html": FuzzTarget(
        name="webkit-html",
        component="webkit",
        description="WebKit HTML parser fuzzing",
        fuzzer="honggfuzz",
    ),
    "kernel-mach": FuzzTarget(
        name="kernel-mach",
        component="kernel",
        description="XNU Mach trap fuzzing",
        fuzzer="honggfuzz",
    ),
    "imageio-jpeg": FuzzTarget(
        name="imageio-jpeg",
        component="imageio",
        description="ImageIO JPEG parsing fuzzing",
        fuzzer="honggfuzz",
    ),
    "imageio-png": FuzzTarget(
        name="imageio-png",
        component="imageio",
        description="ImageIO PNG parsing fuzzing",
        fuzzer="honggfuzz",
    ),
    "coretext-font": FuzzTarget(
        name="coretext-font",
        component="coretext",
        description="CoreText font parsing fuzzing",
        fuzzer="honggfuzz",
    ),
    "coreaudio": FuzzTarget(
        name="coreaudio",
        component="coreaudio",
        description="CoreAudio media parsing fuzzing",
        fuzzer="honggfuzz",
    ),
}


class FuzzerFramework:
    def __init__(self, output_dir: pathlib.Path | None = None):
        self.output_dir = output_dir or pathlib.Path("fuzz-output")
        self.targets: dict[str, FuzzTarget] = dict(FUZZ_TARGETS)

    def list_targets(self) -> dict[str, str]:
        return {name: t.description for name, t in self.targets.items()}

    def register_target(self, target: FuzzTarget) -> None:
        self.targets[target.name] = target

    def fuzz(self, target_name: str, *,
             runs: int = 10000,
             timeout_seconds: int = 300,
             corpus_dir: pathlib.Path | None = None,
             ) -> FuzzResult:
        if target_name not in self.targets:
            raise FuzzerError(f"Unknown fuzz target: {target_name}")

        target = self.targets[target_name]
        fuzzer_bin = shutil_which(target.fuzzer)

        if not fuzzer_bin:
            raise FuzzerError(
                f"Fuzzer '{target.fuzzer}' not found in PATH. "
                f"Install it to run '{target_name}' fuzzing sessions."
            )

        output_dir = self.output_dir / target_name / datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir.mkdir(parents=True, exist_ok=True)

        if target.fuzzer == "honggfuzz":
            cmd = [
                fuzzer_bin,
                "--input", str(corpus_dir or target.corpus_path or "."),
                "--output", str(output_dir),
                "--iterations", str(runs),
                "--timeout", str(timeout_seconds),
                *target.args,
            ]
            if target.harness_path:
                cmd.append(target.harness_path)
        else:
            cmd = [fuzzer_bin, *target.args]
            if target.harness_path:
                cmd.append(target.harness_path)

        manifest = {
            "target": target_name,
            "fuzzer": target.fuzzer,
            "runs": runs,
            "timeout_seconds": timeout_seconds,
            "harness": target.harness_path,
            "corpus": str(corpus_dir or target.corpus_path or ""),
            "command": " ".join(str(c) for c in cmd),
            "started": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        (output_dir / "fuzz-manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

        print(f"[fuzzer] Target: {target.name}")
        print(f"[fuzzer] Fuzzer: {target.fuzzer}")
        print(f"[fuzzer] Command: {' '.join(str(c) for c in cmd)}")
        print(f"[fuzzer] Runs: {runs}")
        print(f"[fuzzer] Output: {output_dir}")
        print(f"[fuzzer] NOTE: Fuzzing requires pre-built harness at {target.harness_path}")

        return FuzzResult(
            target=target_name,
            runs=0,
            crashes=0,
            unique_crashes=0,
            coverage=0.0,
            time_seconds=0,
            crashes_dir=None,
            notes="Fuzzing session configured. Build harness and run the fuzzer manually.",
        )


def shutil_which(name: str) -> str | None:
    import shutil
    result = shutil.which(name)
    return result
