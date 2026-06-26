#!/usr/bin/env python3
"""Validate FBR34KER's freestanding AArch64 ELF layout."""

from __future__ import annotations

import argparse
import pathlib
import struct

ELF_HEADER = struct.Struct("<16sHHIQQQIHHHHHH")
SECTION_HEADER = struct.Struct("<IIQQQQIIQQ")
EM_AARCH64 = 183
ET_EXEC = 2


class LayoutError(ValueError):
    pass


def read_c_string(table: bytes, offset: int) -> str:
    if offset >= len(table):
        raise LayoutError("section name offset is outside string table")
    end = table.find(b"\0", offset)
    if end < 0:
        raise LayoutError("unterminated section name")
    return table[offset:end].decode("ascii")


def verify(path: pathlib.Path, expected_entry: int, profile: str = "monitor") -> list[str]:
    data = path.read_bytes()
    if len(data) < ELF_HEADER.size:
        raise LayoutError("file is smaller than ELF header")
    header = ELF_HEADER.unpack_from(data)
    ident, elf_type, machine, _, entry, _, section_offset, _, _, _, _, section_size, section_count, string_index = header
    if ident[:4] != b"\x7fELF" or ident[4] != 2 or ident[5] != 1:
        raise LayoutError("expected a little-endian ELF64 image")
    if elf_type != ET_EXEC or machine != EM_AARCH64:
        raise LayoutError("expected an AArch64 ET_EXEC image")
    if entry != expected_entry:
        raise LayoutError(f"entry is 0x{entry:x}, expected 0x{expected_entry:x}")
    if section_size != SECTION_HEADER.size or string_index >= section_count:
        raise LayoutError("invalid section-header table")

    raw_sections = []
    for index in range(section_count):
        offset = section_offset + index * section_size
        if offset + section_size > len(data):
            raise LayoutError("truncated section-header table")
        raw_sections.append(SECTION_HEADER.unpack_from(data, offset))
    string_header = raw_sections[string_index]
    string_table = data[string_header[4]:string_header[4] + string_header[5]]
    sections: dict[str, tuple[int, int, int, int, int]] = {}
    for raw in raw_sections:
        name = read_c_string(string_table, raw[0])
        sections[name] = (raw[3], raw[5], raw[8], raw[1], raw[2])
        if name.startswith((".rel", ".rela")) and raw[5] != 0:
            raise LayoutError(f"linked image retains relocation section {name}")

    forbidden = {".dynamic", ".dynsym", ".dynstr", ".interp", ".got", ".plt"}
    present = sorted(forbidden.intersection(sections))
    if present:
        raise LayoutError("dynamic-link sections present: " + ", ".join(present))
    text_address, text_size, _, _, text_flags = sections.get(".text", (0, 0, 0, 0, 0))
    if not text_address <= entry < text_address + text_size or text_flags & 0x4 == 0:
        raise LayoutError("entry point is outside executable .text")

    if profile == "loader":
        required = {".text", ".bss", ".stack"}
        missing = sorted(required.difference(sections))
        if missing:
            raise LayoutError("missing required loader sections: " + ", ".join(missing))
        stack_address, stack_size, stack_alignment, _, _ = sections[".stack"]
        if stack_size != 32 * 1024 or stack_alignment < 4096 or stack_address % 4096 != 0:
            raise LayoutError("loader stack must be 32 KiB and page aligned")
        allocated = [
            (address, size) for address, size, _, _, flags in sections.values()
            if size != 0 and flags & 0x2 != 0
        ]
        image_end = max(address + size for address, size in allocated)
        if image_end > expected_entry + 512 * 1024:
            raise LayoutError("loader exceeds its 512 KiB reserved window")
        return [
            f"entry=0x{entry:016x}",
            f"text=0x{text_address:016x} size={text_size}",
            f"stack=0x{stack_address:016x} size={stack_size}",
            f"image_end=0x{image_end:016x}",
            "window=524288 bytes",
            "relocations=none",
        ]

    required = {
        ".text", ".vectors", ".fbr34ker_build", ".crashlog", ".boot_evidence", ".bss", ".stack_guard_low",
        ".stack", ".stack_guard_high", ".heap",
    }
    missing = sorted(required.difference(sections))
    if missing:
        raise LayoutError("missing required sections: " + ", ".join(missing))

    build_address, build_size, build_alignment, _, _ = sections[".fbr34ker_build"]
    if build_size < 148 or build_alignment < 16:
        raise LayoutError("embedded build metadata is missing or malformed")

    evidence_address, evidence_size, evidence_alignment, _, _ = sections[".boot_evidence"]
    if evidence_size != 56 or evidence_alignment < 16:
        raise LayoutError("persistent boot evidence must be a 56-byte aligned record")

    vector_address, vector_size, vector_alignment, _, vector_flags = sections[".vectors"]
    if vector_address % 2048 or vector_alignment < 2048 or vector_size != 2048 or vector_flags & 0x4 == 0:
        raise LayoutError("invalid exception-vector layout")

    low_address, low_size, low_alignment, _, _ = sections[".stack_guard_low"]
    stack_address, stack_size, stack_alignment, _, _ = sections[".stack"]
    high_address, high_size, high_alignment, _, _ = sections[".stack_guard_high"]
    heap_address, heap_size, heap_alignment, _, _ = sections[".heap"]
    if low_size != 4096 or high_size != 4096 or low_alignment < 4096 or high_alignment < 4096:
        raise LayoutError("stack guard bands must each be one aligned page")
    if stack_size != 64 * 1024 or stack_alignment < 4096:
        raise LayoutError("stack must be 64 KiB and page aligned")
    if high_address < stack_address + stack_size or stack_address < low_address + low_size:
        raise LayoutError("stack/guard sections overlap")
    if heap_size != 4 * 1024 * 1024 or heap_alignment < 4096 or heap_address < high_address + high_size:
        raise LayoutError("invalid heap layout")

    return [
        f"entry=0x{entry:016x}",
        f"vectors=0x{vector_address:016x} size={vector_size}",
        f"stack={stack_size} bytes with 2x4096-byte guards",
        f"heap={heap_size} bytes",
        f"build_info=0x{build_address:016x} size={build_size}",
        f"crashlog={sections['.crashlog'][1]} bytes",
        f"boot_evidence=0x{evidence_address:016x} size={evidence_size}",
        "relocations=none",
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("elf", type=pathlib.Path)
    parser.add_argument("--expected-entry", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--profile", choices=("monitor", "loader"), default="monitor")
    arguments = parser.parse_args()
    try:
        findings = verify(arguments.elf, arguments.expected_entry, arguments.profile)
    except (OSError, LayoutError) as exc:
        print(f"layout verification failed: {exc}")
        return 1
    print("layout verification passed")
    for finding in findings:
        print(f"  {finding}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
