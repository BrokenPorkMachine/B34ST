# Physical device integration preview

Version 0.5.0b prepares FBR34KER for an authorized, user-owned A12/A12X/A12Z/A13 test device without embedding an exploit, signature bypass, or stock-iBoot patch.

## Workflow

1. Query a device with `fbr34ker device list` or an offline device record.
2. Select an exact product-group profile when available.
3. Inspect the FBRI image and adapter-reported memory map.
4. Start an operator-supplied bridge that implements bridge protocol v1.
5. Authorize the current session generation.
6. Upload the image in bounded chunks and verify its complete SHA-256.
7. Start only after a separate unsigned-code acknowledgement.
8. Collect console, stage, trace, boot, and crash evidence.
9. On failure, reset once, invalidate authorization, and require reauthorization.

## Exact product profiles

- `profiles/apple-a12-iphone-recovery.json`
- `profiles/apple-a12-ipad-recovery.json`
- `profiles/apple-a12x-ipad-recovery.json`
- `profiles/apple-a13-iphone-recovery.json`
- `profiles/apple-a13-ipad-recovery.json`

These profiles constrain CPID and product type but deliberately do not invent physical load regions. A real adapter must report the current target map. External sessions reject broad family profiles by default.

## Evidence bundle

Every 0.5.0b session ZIP contains:

- `session.json` and compatibility alias `summary.json`
- `device.json`
- `profile.json`
- `image-manifest.json`
- `transfer.log`
- `console.log`
- `boot-evidence.json`
- `trace.json`
- `crash-report.json`
- `checksums.sha256`

Use `fbr34ker session inspect`, `session replay`, `crash decode`, and `trace timeline` without reconnecting a device.

## Evidence boundary

The included release evidence proves the host bridge, chunking, authorization, product matching, session capture, failure injection, reset, and recovery logic against the deterministic simulator. It does not prove physical execution, stock-iBoot acceptance, or compatibility with a particular third-party first stage.
