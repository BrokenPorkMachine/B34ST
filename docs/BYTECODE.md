# FMBC bytecode

FMBC is FBR34KER's bounded external-module format. It is interpreted data,
not native code. FBR34KER 0.4.5b accepts FMBC v1 and v2; `fbr34kctl` emits v2.

## Version 2 header

The packed 56-byte little-endian header is followed immediately by `code_size`
bytes.

| Field | Size | Meaning |
|---|---:|---|
| magic | 4 | ASCII `FBC0` |
| bytecode_version | 2 | `2` |
| header_size | 2 | `56` |
| code_size | 4 | exact instruction-stream length |
| required_capabilities | 4 | capability mask |
| state_slots | 2 | keyed state quota, `0..8` |
| reserved | 2 | zero |
| command | 32 | optional validated shell alias |
| instruction_budget | 4 | `1..4096` |

FMBC v1 uses its original 20-byte header and is interpreted with no state,
command alias, or extended capability fields.

## Capabilities

| Bit | Name | Permitted operations |
|---:|---|---|
| `1` | `console` | text and integer output |
| `2` | `log` | text and structured key/value log entries |
| `4` | `time` | monotonic uptime |
| `8` | `dt` | read-only FDT node/property queries |
| `16` | `state` | bounded keyed `u64` state |
| `32` | `host` | append a bounded host-event record |

A program is rejected when an instruction uses a capability it did not declare.
The JSON compiler infers capabilities unless an explicit superset is provided.

## Instruction set

All integer values are unsigned 64-bit values. Inline text/path/key operands use
a `u16` byte length followed by bytes validated by the compiler and monitor.

| JSON operation | Opcode | Stack effect |
|---|---:|---|
| `halt` | `00` | none; terminal |
| `push` | `01` + `u64` | push value |
| `print` | `02` + text | none |
| `log` | `03` + text | none |
| `uptime` | `04` | push uptime ms |
| `add` | `05` | pop 2, push sum |
| `sub` | `06` | pop 2, push difference |
| `print_u64` | `07` | pop and print |
| `dup` | `08` | duplicate top |
| `mul` | `09` | pop 2, push product |
| `and` | `0a` | pop 2, push bitwise AND |
| `or` | `0b` | pop 2, push bitwise OR |
| `xor` | `0c` | pop 2, push bitwise XOR |
| `eq` | `0d` | pop 2, push `1` or `0` |
| `drop` | `0e` | pop |
| `swap` | `0f` | exchange top two |
| `state_set` | `10` + key | pop and store |
| `state_get` | `11` + key | push value, default `0` |
| `dt_has_node` | `12` + path | push `1` or `0` |
| `dt_get_u32` | `13` + path + property | push big-endian FDT cell or `0` |
| `log_kv` | `14` + key | pop and log key/value |
| `event` | `15` + text | append host event |

Validation rejects unknown opcodes, malformed operands, disallowed control bytes,
invalid paths/keys, stack underflow or overflow, instructions after `halt`,
unsupported capabilities, state quota violations, and programs beyond the
instruction budget. Execution revalidates the stored program and uses a
16-value stack.

## JSON source example

```json
{
  "name": "counter",
  "version": "1.0.0",
  "command": "counter-run",
  "state_slots": 2,
  "instruction_budget": 128,
  "program": [
    {"op": "state_get", "key": "runs"},
    {"op": "push", "value": 1},
    {"op": "add"},
    {"op": "dup"},
    {"op": "state_set", "key": "runs"},
    {"op": "print", "text": "run count: "},
    {"op": "print_u64"},
    {"op": "print", "text": "\n"},
    {"op": "event", "text": "counter module ran"},
    {"op": "halt"}
  ]
}
```

State persists only while the module remains loaded. Unloading clears it.


Handoff-v4 module policy may reduce the accepted capability mask, dynamic slot count, or instruction budget below these format maxima.
