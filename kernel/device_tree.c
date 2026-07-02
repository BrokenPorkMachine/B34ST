#include "fbr34ker/device_tree.h"
#include "fbr34ker/format.h"
#include "fbr34ker/string.h"

#define FDT_MAGIC 0xd00dfeedU
#define FDT_BEGIN_NODE 1U
#define FDT_END_NODE 2U
#define FDT_PROP 3U
#define FDT_NOP 4U
#define FDT_END 9U
#define FDT_HEADER_SIZE 40U
#define FDT_SUPPORTED_VERSION 17U
#define FDT_MAX_SIZE (4U * 1024U * 1024U)
#define FDT_MAX_DEPTH 64U
#define FDT_MAX_PATH 512U

// SPDX-License-Identifier: BSD-2-Clause
static const u8 *active_blob;
static usize active_size;
static const u8 *structure_block;
static usize structure_size;
static const char *strings_block;
static usize strings_size;
static u32 active_version;
static usize reservation_offset_active;
static usize reservation_end_active;

static u32 read_be32(const void *pointer)
{
    const u8 *bytes = (const u8 *)pointer;
    return ((u32)bytes[0] << 24U) | ((u32)bytes[1] << 16U) |
           ((u32)bytes[2] << 8U) | (u32)bytes[3];
}

static u64 read_be64(const void *pointer)
{
    const u8 *bytes = (const u8 *)pointer;
    u64 value = 0U;
    for (usize index = 0U; index < 8U; ++index) {
        value = (value << 8U) | bytes[index];
    }
    return value;
}

static bool range_valid(usize offset, usize size, usize total)
{
    return offset <= total && size <= total - offset;
}

static bool ranges_disjoint(usize first_offset, usize first_size,
                            usize second_offset, usize second_size)
{
    return first_offset + first_size <= second_offset ||
           second_offset + second_size <= first_offset;
}

static usize align4(usize value)
{
    return (value + 3U) & ~(usize)3U;
}

static void reset_active(void)
{
    active_blob = NULL;
    active_size = 0U;
    structure_block = NULL;
    structure_size = 0U;
    strings_block = NULL;
    strings_size = 0U;
    active_version = 0U;
    reservation_offset_active = 0U;
    reservation_end_active = 0U;
}

static bool reservation_map_valid(const u8 *bytes, usize total,
                                  usize offset, usize *map_end)
{
    if ((offset & 7U) != 0U || offset < FDT_HEADER_SIZE ||
        !range_valid(offset, 16U, total)) {
        return false;
    }
    usize cursor = offset;
    while (range_valid(cursor, 16U, total)) {
        const u64 address = read_be64(bytes + cursor);
        const u64 size = read_be64(bytes + cursor + 8U);
        cursor += 16U;
        if (address == 0U && size == 0U) {
            *map_end = cursor;
            return true;
        }
    }
    return false;
}

bool device_tree_looks_valid(const void *blob, usize available_size)
{
    if (blob == NULL ||
        (available_size != 0U && available_size < FDT_HEADER_SIZE)) {
        return false;
    }
    const u8 *bytes = (const u8 *)blob;
    if (read_be32(bytes) != FDT_MAGIC) {
        return false;
    }

    const usize total = read_be32(bytes + 4U);
    const usize structure_offset = read_be32(bytes + 8U);
    const usize strings_offset = read_be32(bytes + 12U);
    const usize reservation_offset = read_be32(bytes + 16U);
    const u32 version = read_be32(bytes + 20U);
    const u32 compatible_version = read_be32(bytes + 24U);
    const usize strings_length = read_be32(bytes + 32U);
    const usize structure_length = read_be32(bytes + 36U);

    if (total < FDT_HEADER_SIZE || total > FDT_MAX_SIZE ||
        (available_size != 0U && total > available_size) ||
        version < FDT_SUPPORTED_VERSION ||
        compatible_version > FDT_SUPPORTED_VERSION ||
        compatible_version > version ||
        structure_offset < FDT_HEADER_SIZE || (structure_offset & 3U) != 0U ||
        strings_offset < FDT_HEADER_SIZE ||
        !range_valid(structure_offset, structure_length, total) ||
        !range_valid(strings_offset, strings_length, total) ||
        structure_length < 12U ||
        !ranges_disjoint(structure_offset, structure_length,
                         strings_offset, strings_length)) {
        return false;
    }

    usize reservation_end = 0U;
    if (!reservation_map_valid(bytes, total, reservation_offset,
                               &reservation_end) ||
        !ranges_disjoint(reservation_offset,
                         reservation_end - reservation_offset,
                         structure_offset, structure_length) ||
        !ranges_disjoint(reservation_offset,
                         reservation_end - reservation_offset,
                         strings_offset, strings_length)) {
        return false;
    }
    return true;
}

bool device_tree_valid(void)
{
    return active_blob != NULL;
}

const void *device_tree_blob(void)
{
    return active_blob;
}

usize device_tree_size(void)
{
    return active_size;
}

static bool bounded_cstring(const char *text, usize maximum, usize *length)
{
    if (text == NULL) {
        return false;
    }
    for (usize index = 0U; index < maximum; ++index) {
        if (text[index] == '\0') {
            if (length != NULL) {
                *length = index;
            }
            return true;
        }
    }
    return false;
}

static const char *property_name(u32 offset)
{
    if ((usize)offset >= strings_size) {
        return NULL;
    }
    const char *name = strings_block + offset;
    usize length = 0U;
    return bounded_cstring(name, strings_size - offset, &length) && length != 0U
        ? name : NULL;
}

static bool text_contains(const char *text, const char *term)
{
    if (text == NULL || term == NULL || *term == '\0') {
        return false;
    }
    const usize term_length = fm_strlen(term);
    const usize text_length = fm_strlen(text);
    if (term_length > text_length) {
        return false;
    }
    for (usize index = 0U; index + term_length <= text_length; ++index) {
        if (fm_memcmp(text + index, term, term_length) == 0) {
            return true;
        }
    }
    return false;
}

typedef struct {
    usize cursor;
    u32 depth;
    usize path_length;
    usize restore_lengths[FDT_MAX_DEPTH];
    char path[FDT_MAX_PATH];
} fdt_walk_t;

static bool walk_begin(fdt_walk_t *walk)
{
    if (!device_tree_valid() || walk == NULL) {
        return false;
    }
    fm_memset(walk, 0, sizeof(*walk));
    return true;
}

static bool walk_next(fdt_walk_t *walk, u32 *token, const u8 **data,
                      usize *data_size, const char **name)
{
    if (walk == NULL || token == NULL || data == NULL || data_size == NULL ||
        name == NULL || walk->cursor > structure_size ||
        structure_size - walk->cursor < 4U) {
        return false;
    }
    const u32 value = read_be32(structure_block + walk->cursor);
    walk->cursor += 4U;
    *token = value;
    *data = NULL;
    *data_size = 0U;
    *name = NULL;

    if (value == FDT_BEGIN_NODE) {
        const char *node_name = (const char *)(structure_block + walk->cursor);
        usize length = 0U;
        if (!bounded_cstring(node_name, structure_size - walk->cursor, &length) ||
            walk->depth >= FDT_MAX_DEPTH) {
            return false;
        }
        walk->restore_lengths[walk->depth] = walk->path_length;
        if (walk->depth == 0U) {
            walk->path[0] = '/';
            walk->path[1] = '\0';
            walk->path_length = 1U;
        } else {
            const usize separator = walk->path_length == 1U ? 0U : 1U;
            if (walk->path_length + separator + length + 1U > FDT_MAX_PATH) {
                return false;
            }
            if (separator != 0U) {
                walk->path[walk->path_length++] = '/';
            }
            fm_memcpy(walk->path + walk->path_length, node_name, length);
            walk->path_length += length;
            walk->path[walk->path_length] = '\0';
        }
        walk->cursor = align4(walk->cursor + length + 1U);
        if (walk->cursor > structure_size) {
            return false;
        }
        *name = node_name;
        ++walk->depth;
        return true;
    }
    if (value == FDT_END_NODE) {
        if (walk->depth == 0U) {
            return false;
        }
        --walk->depth;
        walk->path_length = walk->restore_lengths[walk->depth];
        walk->path[walk->path_length] = '\0';
        return true;
    }
    if (value == FDT_PROP) {
        if (walk->depth == 0U || structure_size - walk->cursor < 8U) {
            return false;
        }
        const usize length = read_be32(structure_block + walk->cursor);
        const u32 name_offset = read_be32(structure_block + walk->cursor + 4U);
        walk->cursor += 8U;
        if (!range_valid(walk->cursor, length, structure_size)) {
            return false;
        }
        const char *property = property_name(name_offset);
        if (property == NULL) {
            return false;
        }
        *name = property;
        *data = structure_block + walk->cursor;
        *data_size = length;
        walk->cursor = align4(walk->cursor + length);
        return walk->cursor <= structure_size;
    }
    return value == FDT_NOP || value == FDT_END;
}

static bool active_structure_valid(void)
{
    fdt_walk_t walk;
    if (!walk_begin(&walk)) {
        return false;
    }
    bool saw_root = false;
    bool root_closed = false;
    for (;;) {
        u32 token;
        const u8 *data;
        usize data_size;
        const char *name;
        if (!walk_next(&walk, &token, &data, &data_size, &name)) {
            return false;
        }
        UNUSED(data);
        UNUSED(data_size);
        if (token == FDT_BEGIN_NODE) {
            if (!saw_root) {
                if (name == NULL || name[0] != '\0' || walk.depth != 1U) {
                    return false;
                }
                saw_root = true;
            } else if (root_closed) {
                return false;
            }
        } else if (token == FDT_END_NODE && walk.depth == 0U) {
            if (!saw_root || root_closed) {
                return false;
            }
            root_closed = true;
        } else if (token == FDT_PROP && root_closed) {
            return false;
        } else if (token == FDT_END) {
            if (!saw_root || !root_closed || walk.depth != 0U) {
                return false;
            }
            while (walk.cursor < structure_size) {
                if (structure_block[walk.cursor++] != 0U) {
                    return false;
                }
            }
            return true;
        }
    }
}

bool device_tree_init(const void *blob, usize available_size)
{
    reset_active();
    if (!device_tree_looks_valid(blob, available_size)) {
        return false;
    }
    const u8 *bytes = (const u8 *)blob;
    active_size = read_be32(bytes + 4U);
    active_blob = bytes;
    structure_block = bytes + read_be32(bytes + 8U);
    strings_block = (const char *)(bytes + read_be32(bytes + 12U));
    active_version = read_be32(bytes + 20U);
    reservation_offset_active = read_be32(bytes + 16U);
    if (!reservation_map_valid(bytes, active_size, reservation_offset_active,
                               &reservation_end_active)) {
        reset_active();
        return false;
    }
    strings_size = read_be32(bytes + 32U);
    structure_size = read_be32(bytes + 36U);
    if (!active_structure_valid()) {
        reset_active();
        return false;
    }
    return true;
}

static bool valid_path(const char *path)
{
    if (path == NULL || path[0] != '/') {
        return false;
    }
    const usize length = fm_strlen(path);
    return length != 0U && length < FDT_MAX_PATH &&
           (length == 1U || path[length - 1U] != '/');
}

bool device_tree_summary(device_tree_summary_t *summary)
{
    if (summary == NULL || !device_tree_valid()) {
        return false;
    }
    fdt_walk_t walk;
    if (!walk_begin(&walk)) {
        return false;
    }
    u32 nodes = 0U;
    u32 properties = 0U;
    for (;;) {
        u32 token;
        const u8 *data;
        usize data_size;
        const char *name;
        if (!walk_next(&walk, &token, &data, &data_size, &name)) {
            return false;
        }
        UNUSED(data);
        UNUSED(data_size);
        UNUSED(name);
        if (token == FDT_BEGIN_NODE) {
            ++nodes;
        } else if (token == FDT_PROP) {
            ++properties;
        } else if (token == FDT_END) {
            break;
        }
    }
    *summary = (device_tree_summary_t){
        .total_size = (u32)active_size,
        .structure_size = (u32)structure_size,
        .strings_size = (u32)strings_size,
        .version = active_version,
        .node_count = nodes,
        .property_count = properties,
    };
    return true;
}

bool device_tree_has_node(const char *path)
{
    if (!valid_path(path) || !device_tree_valid()) {
        return false;
    }
    fdt_walk_t walk;
    if (!walk_begin(&walk)) {
        return false;
    }
    for (;;) {
        u32 token;
        const u8 *data;
        usize size;
        const char *name;
        if (!walk_next(&walk, &token, &data, &size, &name)) {
            return false;
        }
        UNUSED(data);
        UNUSED(size);
        UNUSED(name);
        if (token == FDT_BEGIN_NODE && fm_strcmp(walk.path, path) == 0) {
            return true;
        }
        if (token == FDT_END) {
            return false;
        }
    }
}

static bool find_property(const char *path, const char *property,
                          const u8 **data, usize *size)
{
    if (!valid_path(path) || property == NULL || *property == '\0' ||
        data == NULL || size == NULL || !device_tree_valid()) {
        return false;
    }
    fdt_walk_t walk;
    if (!walk_begin(&walk)) {
        return false;
    }
    for (;;) {
        u32 token;
        const u8 *item_data;
        usize item_size;
        const char *name;
        if (!walk_next(&walk, &token, &item_data, &item_size, &name)) {
            return false;
        }
        if (token == FDT_PROP && fm_strcmp(walk.path, path) == 0 &&
            fm_strcmp(name, property) == 0) {
            *data = item_data;
            *size = item_size;
            return true;
        }
        if (token == FDT_END) {
            return false;
        }
    }
}

bool device_tree_get_property(const char *path, const char *property,
                              const void **data, usize *size)
{
    const u8 *bytes = NULL;
    usize amount = 0U;
    if (data == NULL || size == NULL ||
        !find_property(path, property, &bytes, &amount)) {
        return false;
    }
    *data = bytes;
    *size = amount;
    return true;
}

bool device_tree_get_u32(const char *path, const char *property, u32 *value)
{
    const u8 *data = NULL;
    usize size = 0U;
    if (value == NULL || !find_property(path, property, &data, &size) ||
        size < 4U) {
        return false;
    }
    *value = read_be32(data);
    return true;
}

bool device_tree_get_u64(const char *path, const char *property, u64 *value)
{
    const u8 *data = NULL;
    usize size = 0U;
    if (value == NULL || !find_property(path, property, &data, &size) ||
        size < 8U) {
        return false;
    }
    *value = read_be64(data);
    return true;
}

bool device_tree_get_string(const char *path, const char *property,
                            char *output, usize capacity)
{
    const u8 *data = NULL;
    usize size = 0U;
    usize length = 0U;
    if (output == NULL || capacity == 0U ||
        !find_property(path, property, &data, &size) || size == 0U ||
        !bounded_cstring((const char *)data, size, &length) ||
        length + 1U > capacity) {
        return false;
    }
    fm_memcpy(output, data, length);
    output[length] = '\0';
    return true;
}

bool device_tree_string_list_contains(const char *path, const char *property,
                                      const char *value)
{
    const u8 *data = NULL;
    usize size = 0U;
    if (value == NULL || *value == '\0' ||
        !find_property(path, property, &data, &size) || size == 0U) {
        return false;
    }
    usize offset = 0U;
    while (offset < size) {
        usize length = 0U;
        if (!bounded_cstring((const char *)data + offset, size - offset,
                             &length)) {
            return false;
        }
        if (fm_strcmp((const char *)data + offset, value) == 0) {
            return true;
        }
        offset += length + 1U;
    }
    return false;
}

static bool parent_path(const char *path, char *output, usize capacity)
{
    if (!valid_path(path) || output == NULL || capacity < 2U ||
        fm_strcmp(path, "/") == 0) {
        return false;
    }
    const usize length = fm_strlen(path);
    usize split = length;
    while (split > 0U && path[split - 1U] != '/') {
        --split;
    }
    const usize parent_length = split <= 1U ? 1U : split - 1U;
    if (parent_length + 1U > capacity) {
        return false;
    }
    fm_memcpy(output, path, parent_length);
    output[parent_length] = '\0';
    return true;
}

static bool read_cells(const u8 *data, u32 cell_count, u64 *value)
{
    if (data == NULL || value == NULL || cell_count > 2U) {
        return false;
    }
    u64 result = 0U;
    for (u32 index = 0U; index < cell_count; ++index) {
        result = (result << 32U) | read_be32(data + index * 4U);
    }
    *value = result;
    return true;
}

bool device_tree_get_reg(const char *path, u32 index, device_tree_reg_t *reg)
{
    if (reg == NULL) {
        return false;
    }
    char parent[FDT_MAX_PATH];
    if (!parent_path(path, parent, sizeof(parent))) {
        return false;
    }
    u32 address_cells = 2U;
    u32 size_cells = 1U;
    (void)device_tree_get_u32(parent, "#address-cells", &address_cells);
    (void)device_tree_get_u32(parent, "#size-cells", &size_cells);
    if (address_cells == 0U || address_cells > 2U || size_cells > 2U) {
        return false;
    }
    const u8 *data = NULL;
    usize size = 0U;
    if (!find_property(path, "reg", &data, &size)) {
        return false;
    }
    const u32 entry_cells = address_cells + size_cells;
    const usize entry_size = (usize)entry_cells * 4U;
    if (entry_size == 0U || size % entry_size != 0U ||
        (usize)index >= size / entry_size) {
        return false;
    }
    const u8 *entry = data + (usize)index * entry_size;
    u64 address = 0U;
    u64 amount = 0U;
    if (!read_cells(entry, address_cells, &address) ||
        !read_cells(entry + address_cells * 4U, size_cells, &amount)) {
        return false;
    }
    *reg = (device_tree_reg_t){
        .address = address,
        .size = amount,
        .address_cells = address_cells,
        .size_cells = size_cells,
    };
    return true;
}

bool device_tree_resolve_alias(const char *alias, char *output, usize capacity)
{
    if (alias == NULL || *alias == '\0' || output == NULL || capacity == 0U) {
        return false;
    }
    char value[DEVICE_TREE_MAX_STRING];
    if (!device_tree_get_string("/aliases", alias, value, sizeof(value))) {
        return false;
    }
    const usize length = fm_strlen(value);
    if (length + 1U > capacity || value[0] != '/') {
        return false;
    }
    fm_memcpy(output, value, length + 1U);
    return true;
}

bool device_tree_stdout_path(char *output, usize capacity)
{
    if (output == NULL || capacity == 0U) {
        return false;
    }
    char value[DEVICE_TREE_MAX_STRING];
    if (!device_tree_get_string("/chosen", "stdout-path", value,
                                sizeof(value)) &&
        !device_tree_get_string("/chosen", "linux,stdout-path", value,
                                sizeof(value))) {
        return false;
    }
    usize length = 0U;
    while (value[length] != '\0' && value[length] != ':') {
        ++length;
    }
    value[length] = '\0';
    if (value[0] == '/') {
        if (length + 1U > capacity) {
            return false;
        }
        fm_memcpy(output, value, length + 1U);
        return true;
    }
    return device_tree_resolve_alias(value, output, capacity);
}

int device_tree_find_compatible(const char *compatible)
{
    if (compatible == NULL || *compatible == '\0' || !device_tree_valid()) {
        return -1;
    }
    fdt_walk_t walk;
    if (!walk_begin(&walk)) {
        return -1;
    }
    int count = 0;
    for (;;) {
        u32 token;
        const u8 *data;
        usize size;
        const char *name;
        if (!walk_next(&walk, &token, &data, &size, &name)) {
            return -1;
        }
        if (token == FDT_PROP && fm_strcmp(name, "compatible") == 0) {
            usize offset = 0U;
            bool matched = false;
            while (offset < size) {
                usize length = 0U;
                if (!bounded_cstring((const char *)data + offset,
                                     size - offset, &length)) {
                    return -1;
                }
                if (fm_strcmp((const char *)data + offset, compatible) == 0) {
                    matched = true;
                    break;
                }
                offset += length + 1U;
            }
            if (matched) {
                fm_printf("%s\n", walk.path);
                ++count;
            }
        } else if (token == FDT_END) {
            return count;
        }
    }
}

int device_tree_print_node(const char *path)
{
    if (!valid_path(path) || !device_tree_valid()) {
        return -1;
    }
    fdt_walk_t walk;
    if (!walk_begin(&walk)) {
        return -1;
    }
    bool found = false;
    u32 target_open_depth = 0U;
    int shown = 0;
    for (;;) {
        const u32 depth_before = walk.depth;
        u32 token;
        const u8 *data;
        usize size;
        const char *name;
        if (!walk_next(&walk, &token, &data, &size, &name)) {
            return -1;
        }
        UNUSED(data);
        if (token == FDT_BEGIN_NODE) {
            if (!found && fm_strcmp(walk.path, path) == 0) {
                found = true;
                target_open_depth = walk.depth;
                fm_printf("Node %s\n", walk.path);
            } else if (found && depth_before == target_open_depth) {
                fm_printf("  node  %s\n", name);
                ++shown;
            }
        } else if (token == FDT_PROP && found &&
                   walk.depth == target_open_depth) {
            fm_printf("  prop  %s (%llu bytes)\n", name, (u64)size);
            ++shown;
        } else if (token == FDT_END_NODE && found &&
                   walk.depth < target_open_depth) {
            return shown;
        } else if (token == FDT_END) {
            return found ? shown : -1;
        }
    }
}

int device_tree_find(const char *term)
{
    if (term == NULL || *term == '\0' || !device_tree_valid()) {
        return -1;
    }
    fdt_walk_t walk;
    if (!walk_begin(&walk)) {
        return -1;
    }
    int count = 0;
    for (;;) {
        u32 token;
        const u8 *data;
        usize size;
        const char *name;
        if (!walk_next(&walk, &token, &data, &size, &name)) {
            return -1;
        }
        UNUSED(data);
        UNUSED(size);
        if (token == FDT_BEGIN_NODE && text_contains(walk.path, term)) {
            fm_printf("%s\n", walk.path);
            ++count;
        } else if (token == FDT_PROP && text_contains(name, term)) {
            fm_printf("%s:%s\n", walk.path, name);
            ++count;
        } else if (token == FDT_END) {
            return count;
        }
    }
}

static bool printable_string_list(const u8 *data, usize size)
{
    if (size < 2U || data[size - 1U] != 0U) {
        return false;
    }
    bool segment_has_text = false;
    for (usize index = 0U; index < size; ++index) {
        const u8 value = data[index];
        if (value == 0U) {
            if (!segment_has_text) {
                return false;
            }
            segment_has_text = false;
        } else {
            if (value < 0x20U || value > 0x7eU) {
                return false;
            }
            segment_has_text = true;
        }
    }
    return !segment_has_text;
}

int device_tree_print_property(const char *path, const char *property)
{
    const u8 *data = NULL;
    usize size = 0U;
    if (!find_property(path, property, &data, &size)) {
        return -1;
    }
    fm_printf("%s:%s (%llu bytes) = ", path, property, (u64)size);
    if (printable_string_list(data, size)) {
        usize offset = 0U;
        while (offset < size) {
            const char *text = (const char *)(data + offset);
            const usize length = fm_strlen(text);
            fm_printf("%s\"%s\"", offset == 0U ? "" : ", ", text);
            offset += length + 1U;
        }
        fm_printf("\n");
        return 0;
    }
    if (size != 0U && (size % 4U) == 0U && size <= 64U) {
        for (usize offset = 0U; offset < size; offset += 4U) {
            fm_printf("%s0x%08x", offset == 0U ? "" : " ",
                      read_be32(data + offset));
        }
        fm_printf("\n");
        return 0;
    }
    const usize shown = size < 64U ? size : 64U;
    for (usize index = 0U; index < shown; ++index) {
        fm_printf("%s%02x", index == 0U ? "" : " ", data[index]);
    }
    if (shown < size) {
        fm_printf(" ...");
    }
    fm_printf("\n");
    return 0;
}

bool device_tree_get_cells(const char *path, const char *property,
                           u32 *values, u32 capacity, u32 *count)
{
    const u8 *data = NULL;
    usize size = 0U;
    if (count == NULL || !find_property(path, property, &data, &size) ||
        (size % 4U) != 0U || size / 4U > 0xffffffffU) {
        return false;
    }
    const u32 cells = (u32)(size / 4U);
    *count = cells;
    if (values == NULL) {
        return capacity == 0U;
    }
    if (cells > capacity) {
        return false;
    }
    for (u32 index = 0U; index < cells; ++index) {
        values[index] = read_be32(data + (usize)index * 4U);
    }
    return true;
}

bool device_tree_get_clock_frequency(const char *path, u64 *frequency)
{
    const u8 *data = NULL;
    usize size = 0U;
    if (frequency == NULL ||
        !find_property(path, "clock-frequency", &data, &size)) {
        return false;
    }
    if (size == 4U) {
        *frequency = read_be32(data);
        return true;
    }
    if (size == 8U) {
        *frequency = read_be64(data);
        return true;
    }
    return false;
}

bool device_tree_find_compatible_path(const char *compatible,
                                      char *output, usize capacity)
{
    if (compatible == NULL || *compatible == '\0' || output == NULL ||
        capacity == 0U || !device_tree_valid()) {
        return false;
    }
    fdt_walk_t walk;
    if (!walk_begin(&walk)) {
        return false;
    }
    for (;;) {
        u32 token;
        const u8 *data;
        usize size;
        const char *name;
        if (!walk_next(&walk, &token, &data, &size, &name)) {
            return false;
        }
        if (token == FDT_PROP && fm_strcmp(name, "compatible") == 0) {
            usize offset = 0U;
            while (offset < size) {
                usize length = 0U;
                if (!bounded_cstring((const char *)data + offset,
                                     size - offset, &length)) {
                    return false;
                }
                if (fm_strcmp((const char *)data + offset, compatible) == 0) {
                    const usize path_length = fm_strlen(walk.path);
                    if (path_length + 1U > capacity) {
                        return false;
                    }
                    fm_memcpy(output, walk.path, path_length + 1U);
                    return true;
                }
                offset += length + 1U;
            }
        } else if (token == FDT_END) {
            return false;
        }
    }
}


u32 device_tree_reservation_count(void)
{
    if (!device_tree_valid() || reservation_end_active <= reservation_offset_active) {
        return 0U;
    }
    u32 count = 0U;
    for (usize cursor = reservation_offset_active;
         cursor + 16U <= reservation_end_active; cursor += 16U) {
        const u64 address = read_be64(active_blob + cursor);
        const u64 size = read_be64(active_blob + cursor + 8U);
        if (address == 0U && size == 0U) break;
        ++count;
    }
    return count;
}

bool device_tree_reservation_at(u32 index, u64 *address, u64 *size)
{
    if (!device_tree_valid() || address == NULL || size == NULL) return false;
    u32 occurrence = 0U;
    for (usize cursor = reservation_offset_active;
         cursor + 16U <= reservation_end_active; cursor += 16U) {
        const u64 entry_address = read_be64(active_blob + cursor);
        const u64 entry_size = read_be64(active_blob + cursor + 8U);
        if (entry_address == 0U && entry_size == 0U) break;
        if (occurrence++ == index) {
            *address = entry_address;
            *size = entry_size;
            return true;
        }
    }
    return false;
}
