# Framebuffer diagnostic console

The loader may grant a framebuffer through handoff ABI v4. Validation requires a nonzero base/size, supported geometry, sufficient stride, a matching readable/writable memory region, and one of:

- XRGB8888
- ARGB8888
- BGRA8888
- RGB565

The console uses a built-in 5x7 glyph set in 6x8 cells, line wrapping, scrolling, clear, and bounded cursor state. It is disabled by default and can be enabled with `display-console on`.

Commands:

```text
display-info
display-clear <RRGGBB>
display-console <status|on|off>
display-test
```

Unhandled exceptions render a high-contrast panic screen when the framebuffer is valid. This is a diagnostic fallback, not a full display stack. Rotation and hardware-specific cache maintenance remain loader responsibilities; an optional framebuffer-flush callback is invoked after updates.
