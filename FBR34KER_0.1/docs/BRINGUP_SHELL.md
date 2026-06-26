# Restricted bring-up shell

When FBR34KER accepts a valid external handoff, it starts in restricted bring-up mode. This prevents an unreviewed loader contract from immediately exposing module execution or mutating controls.

The prompt is:

```text
fbr34ker(bringup)>
```

Allowed commands are read-only or bounded diagnostics: version/platform/handoff information, owned-memory checks, FDT inspection, service availability, console transports/history, timer sampling, reversible IRQ/watchdog self-tests, framebuffer rendering tests, logs, and crash records.

`irq-test` only asks a loader-provided interrupt service to toggle an explicitly named interrupt. `irq-selftest` uses a reversible SPI enable/disable operation. `watchdog-test` requires a loader service that supports timeout `0` as disable. `timer-test` has bounded duration and overflow checks. Framebuffer commands reject invalid or uncovered buffers. No command reads arbitrary physical memory.

After reviewing the handoff and service results, the operator can type:

```text
bringup-exit unlock
```

The explicit token is intentional. A bare `bringup-exit` is rejected. The shell can be restricted again with `bringup-enter`.
