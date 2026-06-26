# Platform services

`fbr34ker_platform_services_t` is a versioned callback table supplied by a handoff-v4 loader. Capability bits are authoritative: callbacks are ignored unless the matching capability is set, and validation rejects capabilities missing required callbacks.

## Console

- `console_write`: bounded bulk output
- `console_read`: nonblocking input
- `console_flush`: optional output drain

The monitor falls back to legacy `early_putc` and `runtime_getc` where appropriate. A separate in-monitor ring preserves recent console text.

## Timer and power

Timer and reboot/halt callbacks remain in the v3-compatible handoff fields. Without timer callbacks, generic ARM64 uses the architectural counter. Power actions without callbacks enter a low-power wait loop.

## Framebuffer

The loader supplies base, size, geometry, stride, format, bytes per pixel, and rotation. The described range must be readable and writable. `framebuffer_flush` is optional for coherent or scanout-visible memory.

## Interrupt controller

The callback set contains acknowledge, complete, and enable/disable operations. If absent, the generic platform may initialize a validated GICv2/GICv3 from the FDT. IRQ delivery starts masked.

## Watchdog

Configure and kick are separate capabilities. A configured watchdog is serviced from bounded monitor wait loops. For `watchdog-disarm` and `watchdog-test`, a configure timeout of `0` means disable. Loaders that cannot guarantee this behavior should omit the configure capability and expose watchdog state as unsupported.

## Callback rules

- callbacks and contexts remain resident for the monitor lifetime;
- callbacks are valid at the actual entry exception level;
- console/watchdog callbacks are nonblocking or tightly bounded;
- callbacks do not retain transient monitor pointers;
- interrupt callbacks follow the loader's documented reentrancy contract.
