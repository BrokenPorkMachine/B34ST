# Persistent first-stage bridge protocol v1

FBR34KER 0.4.5b adds a persistent bridge for an operator-controlled first-stage environment. It is a bounded transport contract, not a device-entry mechanism.

Each message is one UTF-8 JSON object followed by `\n`. Requests contain `schema_version`, a strictly increasing `sequence`, `operation`, and `arguments`. Responses echo the sequence and contain `ok` with either `result` or `error`.

Limits:

- protocol version: 1;
- maximum line: 1 MiB;
- maximum chunk: 128 KiB;
- maximum messages per process: 4096;
- host timeout: 0–300 seconds;
- image size: 64 MiB in the reference bridge.

The reference operations are:

- `identify`
- `authorize`
- `upload-begin`
- `upload-chunk`
- `upload-commit`
- `start`
- `probe-stage`
- `console-read`
- `collect`
- `reset`
- `close`

The bridge must report actual writable/executable regions before upload. The host validates every explicit FBRI component placement against those regions. Reset increments the session generation and invalidates authorization. The host never automatically retries `start` or an execution command.

The reference implementation is `host/reference_bridge.py`. It uses the deterministic simulator and cannot access USB, physical memory, or Apple boot services. The public bounds are also frozen in `include/fbr34ker/bridge_protocol.h` and `schemas/bridge-protocol-v1.json`.
