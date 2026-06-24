# Binary handoff design format (FBHB)

`FBHB` is a deterministic, address-neutral serialization used for loader design,
review, and conformance testing. It is not copied directly into live memory.

```sh
python3 host/fbr34kctl.py handoff-build handoff.json handoff.fbhb
python3 host/fbr34kctl.py handoff-inspect handoff.fbhb
python3 host/fbr34kctl.py handoff-roundtrip handoff.fbhb
```

The container includes:

- format and ABI versions;
- canonical normalized JSON;
- a 284-byte handoff-v4 record;
- a packed region table;
- callback declaration masks;
- section offsets and sizes;
- SHA-256 over the payload.

Pointers in the embedded record are file-relative offsets. Callback addresses,
DTB storage, service tables, and module payload pointers must be resolved by the
runtime loader into its final memory map. `runtime_ready` is therefore false
when unresolved callbacks are declared.

A round trip rebuilds the binary from its normalized design and requires exact
byte equality. This detects noncanonical or damaged inputs without pretending
the file itself is an executable loader image.
