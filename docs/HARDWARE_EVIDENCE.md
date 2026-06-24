# Hardware bring-up evidence

A bring-up evidence ZIP contains deterministic JSON members:

- `summary.json`: device/profile/image match, placements, stage results, recovery state;
- `adapter-state.json`: bounded adapter transcript and current session state;
- `device.json`: public device identity;
- `profile.json`: selected recovery policy;
- `image.json`: FBRI identity and component table.

No payload bytes, device memory contents, authorization secret, or unrestricted USB transcript is included. Authorization IDs are stored only as SHA-256 values inside simulator state.

Compare two summaries or bundles with:

```sh
./fbr34ker evidence-compare first.zip second.zip
```
