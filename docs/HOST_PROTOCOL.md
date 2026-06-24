# Framed host protocol

FBR34KER RC 0.1 multiplexes a binary request/response protocol with the normal
text shell on the same byte-clean serial stream. `fbr34kctl` supports UNIX
sockets, TCP sockets, and local serial devices.

## Frame format

Every integer is little-endian. The header is 20 bytes:

| Offset | Size | Meaning |
|---:|---:|---|
| `0` | 4 | magic bytes `1e 46 4d 33` |
| `4` | 1 | protocol version, currently `1` |
| `5` | 1 | message type; response sets bit `0x80` |
| `6` | 2 | flags |
| `8` | 4 | request sequence number |
| `12` | 4 | payload length |
| `16` | 4 | CRC-32 |
| `20` | N | payload |

The CRC-32 covers header bytes `0..15` followed by the payload. Maximum request
payload is 65,536 bytes; maximum response payload is 16,384 bytes.

Flags:

- `0x0001`: ACK
- `0x0002`: error
- `0x0004`: event/reserved asynchronous indication

## Message types

| Type | Request payload | Response |
|---:|---|---|
| `01` ping | arbitrary bounded bytes | same bytes |
| `02` hello | empty | version/platform limits |
| `03` command | one printable ASCII shell line | captured command output |
| `04` module put | complete FMOD container | load result/name |
| `05` module run | module name | module output/result |
| `06` module unload | module name | result |
| `07` log get | empty | text log ring |
| `08` crash get | empty | preserved/live crash report |
| `09` event get | empty | structured module host events |
| `0a` reboot | empty | acknowledgement, then power action |
| `0b` halt | empty | acknowledgement, then power action |

## Sequencing, retries, and duplicate suppression

`fbr34kctl` chooses a nonzero sequence number and validates type, version, flags,
length, and CRC. Console/banner bytes before a valid magic sequence are ignored.
On timeout or a corrupt response it retries using the **same** type and sequence.
The monitor replays its cached serialized response only when message type, sequence
number, and the original request CRC all match. This prevents a lost acknowledgement
from repeating the last successful operation while rejecting same-sequence payload
changes as a new request.

This is one-entry duplicate suppression, not a durable transaction journal.
After a different request, an old sequence may no longer be recognized.

## Crash-mode service

After a fatal exception the monitor accepts only ping, crash retrieval, reboot,
and halt. Commands and module operations return errors.

## Legacy v0.2 mode

`fbr34kctl --legacy` uses text commands terminated by LF and the original raw
module upload exchange:

1. send `module-load <decimal-size>\n`;
2. wait for `FMOD-READY`;
3. send exactly that many raw bytes;
4. read `FMOD-RESULT` and the normal prompt.

Legacy mode exists for compatibility and should not be used for new clients.

## Security properties

Framing, sequence numbers, and CRC-32 detect accidental corruption and support
safe retries. They do not encrypt or authenticate the serial peer. Run the
protocol only over a trusted local path or add an independently reviewed secure
transport outside the monitor.
