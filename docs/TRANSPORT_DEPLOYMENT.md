# Transport and deployment architecture

FBR34KER 0.6.0_beta separates deployment into four boundaries:

1. **Framing** — `host/wire_protocol.py` encodes and validates FBDP frames.
2. **Transport** — `host/deployment_transport.py` carries complete frames over a
   simulator, socket, or raw POSIX serial stream.
3. **Target policy** — `host/deployment_target.py` validates the deployment
   profile and persists only approved artifact state.
4. **Orchestration** — `host/deployment.py` negotiates, retries, resumes,
   commits, starts, and writes evidence.

No layer is allowed to infer a load region from an artifact path. The selected
profile is the only source of address and artifact-kind policy.

## Host workflow

The client performs the following bounded sequence:

1. Validate every local artifact and the complete non-overlapping plan.
2. Read `HELLO` and require the selected profile name.
3. Read `CAPABILITIES` and negotiate the smaller chunk limit.
4. Recover a matching interrupted session or begin a new authorized session.
5. Query the current contiguous offset for each artifact.
6. Transfer chunks in increasing offset order.
7. Commit each artifact after target-side SHA-256 verification.
8. Start only after every artifact is committed and exactly one is a monitor.
9. Read evidence and write a deterministic evidence bundle.

Retries reuse the same sequence and request bytes. The target returns its cached
response if the first response was lost. This makes chunk and commit retries
idempotent.

## Transport adapters

`SimulatorTransport` is the primary release-validation adapter. It can inject
request loss, response loss, response corruption, disconnects, and delay.

`FramedStreamTransport` works with:

- `SocketEndpoint.tcp()`;
- `SocketEndpoint.unix()`;
- `PosixSerialEndpoint` configured as raw 8N1.

These stream adapters assume a receiver already implements FBDP. They do not
create a privileged execution state or perform a device-specific boot action.

## Cancellation and time bounds

Each exchange has a positive timeout and at most 10 retries. Backoff is bounded
at 500 ms. A transport that closes or makes no progress raises an error. The
client never retries forever.
