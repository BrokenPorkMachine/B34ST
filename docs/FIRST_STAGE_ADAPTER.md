# First-stage adapter and bridge contracts

The first-stage boundary connects FBR34KER host tooling to a separately established, authorized loader environment. FBR34KER does not establish that environment.

## One-shot adapter ABI v1

The compatibility adapter accepts one JSON request on standard input and returns one bounded JSON response. It supports `identify`, `authorize`, `upload`, `start`, `probe-stage`, `console-read`, `collect`, and `reset`. Output is capped at 1 MiB.

## Persistent bridge protocol v1

For physical integration, the preferred interface is the sequence-checked JSON-lines bridge described in `docs/BRIDGE_PROTOCOL.md`. It keeps one session alive for capability discovery, bounded chunk transfer, console polling, diagnostics, and reset.

Mandatory behavior:

- report the real device identity and session generation;
- report non-overlapping writable/executable memory regions;
- authorize only the current generation;
- validate complete image size and SHA-256;
- reject out-of-order or oversized chunks;
- reject entry points outside executable regions;
- fail `start` unless the image is committed and the session is authorized;
- never retry execution automatically;
- increment generation and invalidate authorization on reset;
- bound console, trace, and evidence output.

The reference simulator stores only an authorization hash, copies a verified FBRI image, records deterministic console and stage events, and supports injected failures. It cannot access a physical device.
