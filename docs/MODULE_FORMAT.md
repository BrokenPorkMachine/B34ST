# FMOD module container

FMOD is a little-endian transport envelope with a fixed 96-byte version-1 header
followed by a payload.

| Field | Size | Meaning |
|---|---:|---|
| magic | 4 | ASCII `FMOD` |
| format_version | 2 | `1` |
| header_size | 2 | `96` |
| image_size | 4 | exact payload length |
| flags | 4 | reserved; must be zero in 0.6.0_beta |
| name | 32 | non-empty validated ASCII identifier, NUL terminated |
| version | 16 | non-empty validated ASCII identifier, NUL terminated |
| sha256 | 32 | SHA-256 of the complete payload |

The monitor accepts containers up to 65,536 bytes including the header. Unknown or nonzero flags are rejected rather than silently ignored. The file
size must equal `header_size + image_size`; trailing bytes are rejected.

## Executable payload policy

FBR34KER 0.6.0_beta executes only FMBC bytecode versions 1 and 2. Opaque payloads
can be packed and inspected by `fbr34kctl`, but monitor upload rejects them as
executable modules.

Loaded modules occupy one of up to four fixed 64 KiB slots; handoff-v4 policy may expose fewer slots. A duplicate name is
rejected. Unload clears code, metadata, state, and the complete slot before reuse.

SHA-256 detects corruption and accidental modification. It does not authenticate
a publisher.

## Tooling

```sh
python3 host/fbr34kctl.py compile-module module.json module.fmod
python3 host/fbr34kctl.py inspect-module module.fmod
python3 host/fbr34kctl.py pack-module payload.bin module.fmod \
  --name data --version 1.0.0
```

See `BYTECODE.md` for the executable payload and JSON source format.
