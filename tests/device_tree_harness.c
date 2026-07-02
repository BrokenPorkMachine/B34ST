#include "fbr34ker/device_tree.h"
#include "fbr34ker/string.h"
#include "fbr34ker/types.h"
#include <stdarg.h>

// SPDX-License-Identifier: BSD-2-Clause
int fm_printf(const char *format, ...)
{
    (void)format;
    return 0;
}

static void put_be32(u8 *buffer, usize offset, u32 value)
{
    buffer[offset] = (u8)(value >> 24U);
    buffer[offset + 1U] = (u8)(value >> 16U);
    buffer[offset + 2U] = (u8)(value >> 8U);
    buffer[offset + 3U] = (u8)value;
}

static void put_be64(u8 *buffer, usize offset, u64 value)
{
    for (u32 index = 0U; index < 8U; ++index) {
        buffer[offset + index] = (u8)(value >> ((7U - index) * 8U));
    }
}

static usize append_u32(u8 *buffer, usize offset, u32 value)
{
    put_be32(buffer, offset, value);
    return offset + 4U;
}

static usize append_raw(u8 *buffer, usize offset, const void *source,
                        usize length)
{
    const u8 *bytes = (const u8 *)source;
    for (usize index = 0U; index < length; ++index) {
        buffer[offset++] = bytes[index];
    }
    while ((offset & 3U) != 0U) buffer[offset++] = 0U;
    return offset;
}

static usize append_text(u8 *buffer, usize offset, const char *text)
{
    usize length = 0U;
    while (text[length] != '\0') ++length;
    return append_raw(buffer, offset, text, length + 1U);
}

static u32 string_offset(const char *strings, const char *name)
{
    u32 offset = 0U;
    while (strings[offset] != '\0') {
        const char *candidate = strings + offset;
        usize index = 0U;
        while (candidate[index] == name[index] && name[index] != '\0') ++index;
        if (candidate[index] == '\0' && name[index] == '\0') return offset;
        while (strings[offset] != '\0') ++offset;
        ++offset;
    }
    return 0xffffffffU;
}

static usize append_property(u8 *blob, usize cursor, const char *strings,
                             const char *name, const void *data, usize size)
{
    cursor = append_u32(blob, cursor, 3U);
    cursor = append_u32(blob, cursor, (u32)size);
    cursor = append_u32(blob, cursor, string_offset(strings, name));
    return append_raw(blob, cursor, data, size);
}

static usize append_property_u32(u8 *blob, usize cursor, const char *strings,
                                 const char *name, u32 value)
{
    u8 bytes[4];
    put_be32(bytes, 0U, value);
    return append_property(blob, cursor, strings, name, bytes, sizeof(bytes));
}

int main(void)
{
    static const char strings[] =
        "compatible\0#address-cells\0#size-cells\0test-u64\0serial0\0"
        "stdout-path\0reg\0clock-frequency\0interrupts\0clocks\0";
    u8 blob[1024] = {0U};
    const usize structure_offset = 72U;
    put_be64(blob, 40U, 0x81000000ULL);
    put_be64(blob, 48U, 0x2000ULL);
    put_be64(blob, 56U, 0U);
    put_be64(blob, 64U, 0U);
    usize cursor = structure_offset;

    cursor = append_u32(blob, cursor, 1U);
    cursor = append_text(blob, cursor, "");
    static const char root_compatible[] = "fbr34ker,test\0generic,arm64\0";
    cursor = append_property(blob, cursor, strings, "compatible",
                             root_compatible, sizeof(root_compatible));
    cursor = append_property_u32(blob, cursor, strings, "#address-cells", 2U);
    cursor = append_property_u32(blob, cursor, strings, "#size-cells", 2U);
    const u8 u64_data[8] = {0x11,0x22,0x33,0x44,0x55,0x66,0x77,0x88};
    cursor = append_property(blob, cursor, strings, "test-u64",
                             u64_data, sizeof(u64_data));

    cursor = append_u32(blob, cursor, 1U);
    cursor = append_text(blob, cursor, "aliases");
    static const char serial_path[] = "/uart@9000000";
    cursor = append_property(blob, cursor, strings, "serial0",
                             serial_path, sizeof(serial_path));
    cursor = append_u32(blob, cursor, 2U);

    cursor = append_u32(blob, cursor, 1U);
    cursor = append_text(blob, cursor, "chosen");
    static const char stdout_path[] = "serial0:115200n8";
    cursor = append_property(blob, cursor, strings, "stdout-path",
                             stdout_path, sizeof(stdout_path));
    cursor = append_u32(blob, cursor, 2U);

    cursor = append_u32(blob, cursor, 1U);
    cursor = append_text(blob, cursor, "uart@9000000");
    static const char uart_compatible[] = "arm,pl011\0arm,primecell\0";
    cursor = append_property(blob, cursor, strings, "compatible",
                             uart_compatible, sizeof(uart_compatible));
    const u8 reg_data[16] = {
        0,0,0,0, 0x09,0,0,0,
        0,0,0,0, 0,0,0x10,0,
    };
    cursor = append_property(blob, cursor, strings, "reg",
                             reg_data, sizeof(reg_data));
    cursor = append_property_u32(blob, cursor, strings,
                                 "clock-frequency", 24000000U);
    const u8 interrupt_data[12] = {0,0,0,0, 0,0,0,33, 0,0,0,4};
    cursor = append_property(blob, cursor, strings, "interrupts",
                             interrupt_data, sizeof(interrupt_data));
    const u8 clock_data[8] = {0,0,0,1, 0,0,0,2};
    cursor = append_property(blob, cursor, strings, "clocks",
                             clock_data, sizeof(clock_data));
    cursor = append_u32(blob, cursor, 2U);

    cursor = append_u32(blob, cursor, 2U);
    cursor = append_u32(blob, cursor, 9U);
    const usize structure_size = cursor - structure_offset;
    const usize strings_offset = cursor;
    for (usize index = 0U; index < sizeof(strings); ++index) {
        blob[cursor++] = (u8)strings[index];
    }

    put_be32(blob, 0U, 0xd00dfeedU);
    put_be32(blob, 4U, (u32)cursor);
    put_be32(blob, 8U, (u32)structure_offset);
    put_be32(blob, 12U, (u32)strings_offset);
    put_be32(blob, 16U, 40U);
    put_be32(blob, 20U, 17U);
    put_be32(blob, 24U, 16U);
    put_be32(blob, 28U, 0U);
    put_be32(blob, 32U, (u32)sizeof(strings));
    put_be32(blob, 36U, (u32)structure_size);

    if (!device_tree_init(blob, cursor)) return 1;
    if (!device_tree_has_node("/uart@9000000")) return 2;
    u32 frequency = 0U;
    if (!device_tree_get_u32("/uart@9000000", "clock-frequency", &frequency) ||
        frequency != 24000000U) return 3;
    char text[64];
    if (!device_tree_get_string("/", "compatible", text, sizeof(text)) ||
        text[0] != 'f') return 4;
    if (!device_tree_string_list_contains("/uart@9000000", "compatible",
                                          "arm,pl011")) return 5;
    if (!device_tree_resolve_alias("serial0", text, sizeof(text)) ||
        text[0] != '/' || text[1] != 'u') return 6;
    if (!device_tree_stdout_path(text, sizeof(text)) || text[1] != 'u') return 7;
    device_tree_reg_t reg;
    if (!device_tree_get_reg("/uart@9000000", 0U, &reg) ||
        reg.address != 0x09000000ULL || reg.size != 0x1000ULL ||
        reg.address_cells != 2U || reg.size_cells != 2U) return 8;
    u64 wide = 0U;
    if (!device_tree_get_u64("/", "test-u64", &wide) ||
        wide != 0x1122334455667788ULL) return 9;
    if (device_tree_find_compatible("arm,pl011") != 1) return 10;
    if (!device_tree_find_compatible_path("arm,pl011", text, sizeof(text)) ||
        fm_strcmp(text, "/uart@9000000") != 0) return 13;
    u64 clock = 0U;
    if (!device_tree_get_clock_frequency("/uart@9000000", &clock) ||
        clock != 24000000U) return 14;
    u32 cells[4];
    u32 cell_count = 0U;
    if (!device_tree_get_cells("/uart@9000000", "reg", cells,
                               ARRAY_COUNT(cells), &cell_count) ||
        cell_count != 4U || cells[1] != 0x09000000U || cells[3] != 0x1000U) return 15;
    if (!device_tree_get_cells("/uart@9000000", "interrupts", cells,
                               ARRAY_COUNT(cells), &cell_count) ||
        cell_count != 3U || cells[1] != 33U || cells[2] != 4U) return 16;
    if (!device_tree_get_cells("/uart@9000000", "clocks", cells,
                               ARRAY_COUNT(cells), &cell_count) ||
        cell_count != 2U || cells[0] != 1U || cells[1] != 2U) return 17;
    device_tree_summary_t summary;
    if (!device_tree_summary(&summary)) return 11;
    if (summary.node_count != 4U || summary.property_count != 11U) return 12;
    if (device_tree_reservation_count() != 1U) return 18;
    u64 reserved_base = 0U;
    u64 reserved_size = 0U;
    if (!device_tree_reservation_at(0U, &reserved_base, &reserved_size) ||
        reserved_base != 0x81000000ULL || reserved_size != 0x2000ULL) return 19;
    return 0;
}
