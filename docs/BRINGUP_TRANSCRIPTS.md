# Bring-up transcript recorder

`probe-record` captures a bounded boot transcript and then requests only
read-only metadata through the framed protocol.

```bash
python3 host/fbr34kctl.py probe-record \
  --device /dev/cu.example --baud 115200 \
  --duration 30 --profile board.json \
  --output hardware-probe-session
```

UNIX and TCP endpoints are supported with `--unix` and `--tcp`. The output
contains raw and decoded boot transcripts, one text file per diagnostic command,
a summary, an optional compatibility matrix, and a deterministic ZIP archive.

The recorder does not request arbitrary addresses or physical-memory contents.
It does not run IRQ self-tests, arm a watchdog, write the framebuffer, load a
module, reboot, or halt the target.
