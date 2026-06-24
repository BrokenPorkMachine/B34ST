# Console transports

Console output is transport-independent at the kernel layer.

- **Platform serial/callback:** PL011 for direct QEMU or loader callbacks for generic boots.
- **Memory history ring:** the most recent 4 KiB of console text is always retained.
- **Semihosting mirror:** optional direct-QEMU output through AArch64 semihosting.
- **Framebuffer console:** optional validated diagnostic text output.

Use `console-transports` to inspect availability. `console-semihosting on` is accepted only by a platform that explicitly supports it. The serial/callback stream remains the authoritative shell and framed-protocol channel.

The memory ring contains console text only; it does not expose arbitrary RAM.
