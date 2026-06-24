# Persistent boot evidence

The linker reserves a NOLOAD `.boot_evidence` section before BSS. The 56-byte
record contains a magic/version/size/checksum header and:

- boot count;
- previous stage and clean-shutdown flag;
- current stage and clean-shutdown flag;
- last error code/value; and
- monotonic stage sequence.

Stages are reset, context, platform, runtime, architecture, interactive,
shutdown, and fault. Exception capture marks the record faulted before storing
the crash record. The `reboot` and `halt` commands mark a clean shutdown before
calling platform power control.

Use `boot-evidence` or `boot-evidence-json` in the monitor. A raw 56-byte memory
dump can be decoded with:

```bash
python3 scripts/decode_boot_evidence.py evidence.bin --pretty
```
