# FBR34KER exploit chain setup script

This compatibility script verifies the build environment and packages the
disabled security-state models. It does not execute or deploy to a target.

## Usage

```sh
# Full exploit chain build and verification
bash scripts/start_exploit.sh

# Persistence deployment plan
bash scripts/establish_persistence.sh
```

## Build targets

```sh
# Individual subsystems (also available via Makefile)
make kernel-patches
make secure-boot-bypass
make persistence

# Full chain
make exploit-chain
```

## Artifacts

The exploit chain produces artifacts in `build-exploit/`:

```
build-exploit/
  exploit-summary.txt     # Chain capability summary
  persistence-plan.txt    # Persistence deployment plan (from establish-persistence)
  fbr34ker.elf            # Monitor ELF with mutation gates disabled
  fbr34ker.bin            # Monitor binary with mutation gates disabled
```

## Monitor shell interaction

Once the monitor is running (e.g. via `make run` under QEMU), the exploit
subsystems are available as shell commands:

```
fbr34ker> kernel-patches status
fbr34ker> secure-boot-bypass forgive
fbr34ker> persistence evade
fbr34ker> exploit-chain run
fbr34ker> exploit-status
```

The `exploit-chain run` command is rejected in release builds. The listed
stages are state-model labels only and are not implemented as target mutation:
kernel patching, secure-boot bypass, and persistence deployment.
