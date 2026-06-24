# Real-hardware adapter boundary

FBR34KER 0.2.3 does not include a device-specific boot or exploit adapter. An
authorized loader port may expose FBDP only after it has established its own
legitimate development execution environment.

A production adapter must:

- authenticate and authorize the host independently of the FBDP session token;
- bind the selected deployment profile to an immutable board identity;
- keep deployment regions separate from protected and persistent storage;
- validate every chunk before copying it to target memory;
- verify the complete SHA-256 digest before marking an artifact executable;
- invalidate partial executable pages on failure;
- preserve previous crash evidence before resetting a session;
- provide a bounded watchdog and cancellation path;
- refuse unsupported protocol versions and capabilities;
- emit a reproducible board, loader, monitor, and artifact evidence record.

The generic `FramedStreamTransport` can carry FBDP over serial or sockets, but it
does not provide USB enumeration, ROM interaction, reset timing, privileged
entry, or hardware-specific memory writes.
