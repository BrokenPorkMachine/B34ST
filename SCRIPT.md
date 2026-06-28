# FBR34KER exploit chain setup script

These compatibility scripts build and package the FBR34KER exploit chain
subsystems. Build with `SECURITY_MODEL=1` to enable mutation paths.

## Usage

```sh
# Full exploit chain build and verification
bash scripts/start_exploit.sh

# Persistence deployment plan
bash scripts/establish_persistence.sh

# Build with mutation paths enabled
make SECURITY_MODEL=1 build-operational
```

## Build targets

```sh
# Individual subsystems (also available via Makefile)
make kernel-patches
make secure-boot-bypass
make persistence

# Full exploit chain
make exploit-chain

# Operational build with all mutation paths enabled
make SECURITY_MODEL=1 build-operational
```

## Artifacts

The exploit chain produces artifacts in `build-exploit/`:

```
build-exploit/
  exploit-summary.txt        # Chain capability summary
  persistence-plan.txt       # Persistence deployment plan
  fbr34ker-operational.elf   # Monitor ELF with mutation paths enabled (SECURITY_MODEL=1)
  fbr34ker-operational.bin   # Monitor binary with mutation paths enabled
```

## Monitor shell interaction

Once the monitor is running (e.g. via `make run` under QEMU for default build,
or deployed to physical hardware with the operational build), the exploit
subsystems are available as shell commands:

```
fbr34ker> kernel-patches status|apply|revert|escalate
fbr34ker> secure-boot-bypass status|activate|forgive|manifest
fbr34ker> persistence status|deploy|activate|evade
fbr34ker> exploit-chain status|pwndfu|load|exec|run|reset
fbr34ker> jailbreak status|bypass-all|detect-kernel|inject-bootargs|chain-all|boot-kernel
fbr34ker> exploit-status
```

Mutation commands require the operational build (`SECURITY_MODEL=1`). The
default build rejects all mutation paths and reports status only.
