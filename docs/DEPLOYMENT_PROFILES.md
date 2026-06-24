# Deployment profiles

Deployment profiles are schema-versioned JSON documents. The release profile is
`profiles/qemu-virt-deployment.json`.

Required fields:

- `schema_version`: `1`;
- `name`: stable ASCII profile identifier;
- `board_compatible`: 1–16 compatibility strings;
- `deployment_regions`: 1–16 non-overlapping regions.

Optional bounded fields:

- `max_artifact_size`;
- `max_total_size`;
- `entry_alignment`, a power of two no greater than 65536.

Each region contains `name`, `base`, `size`, and `artifact_kinds`. Supported
kinds are `loader`, `monitor`, `dtb`, `module`, and `configuration`.

The host and target both reject:

- unknown fields;
- integer overflow;
- overlapping regions or artifacts;
- ranges outside exactly one permitted region;
- unsupported kinds;
- misaligned addresses;
- zero-length or oversized artifacts;
- duplicate names;
- plans without exactly one monitor.
