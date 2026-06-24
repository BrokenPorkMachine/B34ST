# FBDP v1 deployment protocol

## Header

All fields are little-endian.

| Field | Size | Meaning |
|---|---:|---|
| magic | 4 | ASCII `FBDP` |
| version | 1 | `1` |
| message type | 1 | request type; responses set bit 7 |
| flags | 2 | ACK, ERROR, EVENT |
| sequence | 4 | non-zero client sequence |
| payload size | 4 | at most 65536 |
| CRC-32 | 4 | CRC over the first 16 header bytes and payload |

The public C constants and packed header are in
`include/fbr34ker/deployment_protocol.h`.

## Messages

| Request | Value | Purpose |
|---|---:|---|
| PING | `0x01` | transport round trip |
| HELLO | `0x02` | target and selected profile identity |
| CAPABILITIES | `0x03` | protocol versions, chunk limit, regions |
| BEGIN_DEPLOY | `0x10` | authorize and submit complete manifest |
| QUERY_PROGRESS | `0x11` | read contiguous artifact offset |
| PUT_CHUNK | `0x12` | append a bounded chunk |
| COMMIT_ARTIFACT | `0x13` | verify size and SHA-256 |
| START | `0x14` | controlled start after all commits |
| EVIDENCE_GET | `0x20` | retrieve boot/deployment evidence |
| RESET_SESSION | `0x21` | discard partial artifacts, preserve evidence |
| RECOVER_SESSION | `0x22` | retrieve resumable session state |

## Chunk payload

`PUT_CHUNK` begins with `<HQQI>`:

- 16-bit artifact index;
- 64-bit session authorization token;
- 64-bit byte offset;
- 32-bit chunk size;
- chunk bytes.

The offset must equal the target's recorded contiguous length. Sparse or
out-of-order writes are rejected.

## Duplicate handling

The reference target retains 32 recent responses. A duplicate sequence with the
same message, flags, and payload receives the cached response. The same sequence
with different request bytes receives an error.
