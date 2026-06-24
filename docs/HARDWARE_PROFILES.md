# Hardware profiles and compatibility matrices

A profile describes the expected public contract of an authorized ARM64 target.
It contains no exploit offsets, memory contents, keys, or credentials.

Create and validate a profile:

```bash
python3 host/fbr34kctl.py profile-template board.json
python3 host/fbr34kctl.py profile-validate board.json --output board.normalized.json
```

Compare it with a diagnostics directory:

```bash
python3 host/fbr34kctl.py profile-check board.json hardware-diagnostics \
  --output compatibility.json
python3 host/fbr34kctl.py profile-report compatibility.json
```

The matrix uses `PASS`, `PARTIAL`, `UNSUPPORTED`, `NOT TESTED`, `LOCKED`, and
`FAIL`. A locked service can be structurally valid while remaining intentionally
unexercised by the probe image.

Profile fields cover expected exception level, console transport, interrupt
controller, timer source, optional framebuffer constraints, and required public
services. Unknown fields and unsupported values are rejected.
