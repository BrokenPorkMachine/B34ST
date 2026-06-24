#include "fbr34ker/board.h"
#include "fbr34ker/device_tree.h"
#include "fbr34ker/format.h"
#include "fbr34ker/platform.h"
#include "fbr34ker/string.h"
#include <stdarg.h>

static fbr34ker_board_descriptor_t active_board;
static bool initialized;

static void copy_text(char *destination, usize capacity, const char *source)
{
    if (destination == NULL || capacity == 0U) return;
    destination[0] = '\0';
    if (source == NULL) return;
    usize index = 0U;
    while (index + 1U < capacity && source[index] != '\0') {
        destination[index] = source[index];
        ++index;
    }
    destination[index] = '\0';
}

static bool contains(const char *text, const char *term)
{
    if (text == NULL || term == NULL || *term == '\0') return false;
    const usize text_length = fm_strlen(text);
    const usize term_length = fm_strlen(term);
    if (term_length > text_length) return false;
    for (usize index = 0U; index + term_length <= text_length; ++index) {
        if (fm_memcmp(text + index, term, term_length) == 0) return true;
    }
    return false;
}

static bool add_device(const char *name, const char *compatible,
                       fbr34ker_device_type_t type, u32 flags,
                       u64 base, u64 size, u64 clock_hz, u32 interrupt)
{
    if (active_board.device_count >= FBR34KER_BOARD_MAX_DEVICES ||
        type >= FBR34KER_DEVICE_COUNT ||
        (size != 0U && base > U64_MAX_VALUE - size)) {
        return false;
    }
    fbr34ker_board_device_t *device =
        &active_board.devices[active_board.device_count++];
    fm_memset(device, 0, sizeof(*device));
    copy_text(device->name, sizeof(device->name), name);
    copy_text(device->compatible, sizeof(device->compatible), compatible);
    device->type = type;
    device->flags = flags;
    device->base = base;
    device->size = size;
    device->clock_hz = clock_hz;
    device->interrupt = interrupt;
    return true;
}

static void select_memory(void)
{
    const memory_region_t *regions = NULL;
    const u64 count = platform_memory_regions(&regions);
    u64 largest = 0U;
    for (u64 index = 0U; index < count; ++index) {
        if (regions[index].type == MEMORY_REGION_USABLE &&
            regions[index].size > largest) {
            active_board.memory_base = regions[index].base;
            active_board.memory_size = regions[index].size;
            largest = regions[index].size;
        }
    }
}

static bool add_dtb_device(const char *compatible,
                           fbr34ker_device_type_t type,
                           const char *name, u32 flags)
{
    char path[DEVICE_TREE_MAX_STRING];
    device_tree_reg_t reg;
    if (!device_tree_find_compatible_path(compatible, path, sizeof(path)) ||
        !device_tree_get_reg(path, 0U, &reg) || reg.size == 0U) {
        return false;
    }
    u64 clock_hz = 0U;
    (void)device_tree_get_clock_frequency(path, &clock_hz);
    u32 interrupt = 0xffffffffU;
    u32 cells[8];
    u32 cell_count = 0U;
    if (device_tree_get_cells(path, "interrupts", cells, ARRAY_COUNT(cells),
                              &cell_count) && cell_count != 0U) {
        interrupt = cells[cell_count >= 2U ? 1U : 0U];
    }
    return add_device(name, compatible, type,
                      flags | FBR34KER_DEVICE_FLAG_FROM_DTB,
                      reg.address, reg.size, clock_hz, interrupt);
}

static void select_qemu_virt(void)
{
    copy_text(active_board.identifier, sizeof(active_board.identifier),
              "qemu-virt-arm64");
    copy_text(active_board.name, sizeof(active_board.name),
              "QEMU Arm virt");
    copy_text(active_board.compatible, sizeof(active_board.compatible),
              "linux,dummy-virt");
    active_board.source = FBR34KER_BOARD_SOURCE_BUILTIN;
    active_board.matched = true;
    (void)add_device("pl011-uart", "arm,pl011", FBR34KER_DEVICE_UART,
                     FBR34KER_DEVICE_FLAG_MMIO_READ |
                     FBR34KER_DEVICE_FLAG_MMIO_WRITE |
                     FBR34KER_DEVICE_FLAG_REQUIRED,
                     0x09000000ULL, 0x1000ULL, 24000000ULL, 33U);
    (void)add_device("architectural-timer", "arm,armv8-timer",
                     FBR34KER_DEVICE_TIMER,
                     FBR34KER_DEVICE_FLAG_ARCHITECTURAL |
                     FBR34KER_DEVICE_FLAG_REQUIRED,
                     0U, 0U, 0U, 27U);
    (void)add_device("gicv3-distributor", "arm,gic-v3",
                     FBR34KER_DEVICE_INTERRUPT_CONTROLLER,
                     FBR34KER_DEVICE_FLAG_MMIO_READ |
                     FBR34KER_DEVICE_FLAG_MMIO_WRITE |
                     FBR34KER_DEVICE_FLAG_PROBE_SAFE,
                     0x08000000ULL, 0x10000ULL, 0U, 0xffffffffU);
    (void)add_device("virt-power-control", "qemu,virt-power",
                     FBR34KER_DEVICE_POWER,
                     FBR34KER_DEVICE_FLAG_MMIO_WRITE,
                     0x09020000ULL, 0x1000ULL, 0U, 0xffffffffU);
}

static void select_generic(void)
{
    copy_text(active_board.identifier, sizeof(active_board.identifier),
              "generic-arm64");
    copy_text(active_board.name, sizeof(active_board.name),
              "Generic ARM64 board");
    copy_text(active_board.compatible, sizeof(active_board.compatible),
              "generic,arm64");
    active_board.source = contains(platform_name(), "handoff")
        ? FBR34KER_BOARD_SOURCE_HANDOFF : FBR34KER_BOARD_SOURCE_FALLBACK;
    active_board.matched = active_board.source == FBR34KER_BOARD_SOURCE_HANDOFF;
    (void)add_device("architectural-timer", "arm,armv8-timer",
                     FBR34KER_DEVICE_TIMER,
                     FBR34KER_DEVICE_FLAG_ARCHITECTURAL |
                     FBR34KER_DEVICE_FLAG_REQUIRED,
                     0U, 0U, 0U, 0xffffffffU);
}

static void apply_device_tree(void)
{
    if (!device_tree_valid()) return;
    char root_compatible[FBR34KER_BOARD_COMPAT_CAPACITY];
    if (device_tree_get_string("/", "compatible", root_compatible,
                               sizeof(root_compatible))) {
        copy_text(active_board.compatible, sizeof(active_board.compatible),
                  root_compatible);
        active_board.device_tree_applied = true;
        if (contains(root_compatible, "virt") ||
            device_tree_string_list_contains("/", "compatible",
                                             "linux,dummy-virt")) {
            active_board.source = FBR34KER_BOARD_SOURCE_DEVICE_TREE;
            active_board.matched = true;
        }
    }

    bool has_uart = board_find_device(FBR34KER_DEVICE_UART, 0U) != NULL;
    if (!has_uart) {
        has_uart = add_dtb_device("arm,pl011", FBR34KER_DEVICE_UART,
                                 "dtb-pl011-uart",
                                 FBR34KER_DEVICE_FLAG_MMIO_READ |
                                 FBR34KER_DEVICE_FLAG_MMIO_WRITE);
    }
    if (board_find_device(FBR34KER_DEVICE_INTERRUPT_CONTROLLER, 0U) == NULL) {
        if (!add_dtb_device("arm,gic-v3",
                            FBR34KER_DEVICE_INTERRUPT_CONTROLLER,
                            "dtb-gicv3",
                            FBR34KER_DEVICE_FLAG_MMIO_READ |
                            FBR34KER_DEVICE_FLAG_MMIO_WRITE)) {
            (void)add_dtb_device("arm,gic-400",
                                 FBR34KER_DEVICE_INTERRUPT_CONTROLLER,
                                 "dtb-gicv2",
                                 FBR34KER_DEVICE_FLAG_MMIO_READ |
                                 FBR34KER_DEVICE_FLAG_MMIO_WRITE);
        }
    }
    if (board_find_device(FBR34KER_DEVICE_WATCHDOG, 0U) == NULL) {
        (void)add_dtb_device("arm,sp805", FBR34KER_DEVICE_WATCHDOG,
                             "dtb-sp805-watchdog",
                             FBR34KER_DEVICE_FLAG_MMIO_READ |
                             FBR34KER_DEVICE_FLAG_MMIO_WRITE);
    }
    UNUSED(has_uart);
}

bool board_init(void)
{
    fm_memset(&active_board, 0, sizeof(active_board));
    initialized = false;
    if (contains(platform_name(), "QEMU")) select_qemu_virt();
    else select_generic();
    select_memory();
    apply_device_tree();
    active_board.features = platform_features();
    initialized = active_board.identifier[0] != '\0' &&
                  active_board.device_count <= FBR34KER_BOARD_MAX_DEVICES;
    return initialized;
}

void board_shutdown(void)
{
    fm_memset(&active_board, 0, sizeof(active_board));
    initialized = false;
}

bool board_ready(void) { return initialized; }

bool board_healthy(void)
{
    if (!initialized || active_board.identifier[0] == '\0' ||
        active_board.device_count > FBR34KER_BOARD_MAX_DEVICES) return false;
    for (u32 index = 0U; index < active_board.device_count; ++index) {
        const fbr34ker_board_device_t *device = &active_board.devices[index];
        if (device->type >= FBR34KER_DEVICE_COUNT || device->name[0] == '\0' ||
            (device->size != 0U && device->base > U64_MAX_VALUE - device->size)) {
            return false;
        }
    }
    return true;
}

const fbr34ker_board_descriptor_t *board_active(void)
{
    return initialized ? &active_board : NULL;
}

u32 board_device_count(void) { return initialized ? active_board.device_count : 0U; }

bool board_device_at(u32 index, fbr34ker_board_device_t *device)
{
    if (!initialized || device == NULL || index >= active_board.device_count) return false;
    *device = active_board.devices[index];
    return true;
}

const fbr34ker_board_device_t *board_find_device(fbr34ker_device_type_t type,
                                                  u32 occurrence)
{
    if (type >= FBR34KER_DEVICE_COUNT) return NULL;
    for (u32 index = 0U; index < active_board.device_count; ++index) {
        if (active_board.devices[index].type == type) {
            if (occurrence == 0U) return &active_board.devices[index];
            --occurrence;
        }
    }
    return NULL;
}

const char *board_source_name(fbr34ker_board_source_t source)
{
    switch (source) {
    case FBR34KER_BOARD_SOURCE_FALLBACK: return "fallback";
    case FBR34KER_BOARD_SOURCE_BUILTIN: return "built-in";
    case FBR34KER_BOARD_SOURCE_DEVICE_TREE: return "device-tree";
    case FBR34KER_BOARD_SOURCE_HANDOFF: return "loader-handoff";
    default: return "unknown";
    }
}

const char *board_device_type_name(fbr34ker_device_type_t type)
{
    switch (type) {
    case FBR34KER_DEVICE_UART: return "uart";
    case FBR34KER_DEVICE_TIMER: return "timer";
    case FBR34KER_DEVICE_INTERRUPT_CONTROLLER: return "interrupt-controller";
    case FBR34KER_DEVICE_WATCHDOG: return "watchdog";
    case FBR34KER_DEVICE_POWER: return "power";
    case FBR34KER_DEVICE_FRAMEBUFFER: return "framebuffer";
    default: return "unknown";
    }
}

static usize append(char *buffer, usize capacity, usize offset,
                    const char *format, ...)
{
    if (buffer == NULL || capacity == 0U || offset >= capacity) return offset;
    va_list arguments;
    va_start(arguments, format);
    const int count = fm_vsnprintf(buffer + offset, capacity - offset,
                                   format, arguments);
    va_end(arguments);
    if (count <= 0) return offset;
    return (usize)count >= capacity - offset ? capacity - 1U
                                             : offset + (usize)count;
}

usize board_export_json(char *buffer, usize capacity)
{
    if (buffer == NULL || capacity == 0U) return 0U;
    if (!initialized) return (usize)fm_snprintf(buffer, capacity,
        "{\"schema\":1,\"available\":false}\n");
    usize offset = append(buffer, capacity, 0U,
        "{\"schema\":1,\"available\":true,\"id\":\"%s\","
        "\"name\":\"%s\",\"compatible\":\"%s\",\"source\":\"%s\","
        "\"matched\":%s,\"memory_base\":%llu,\"memory_size\":%llu,"
        "\"devices\":[",
        active_board.identifier, active_board.name, active_board.compatible,
        board_source_name(active_board.source),
        active_board.matched ? "true" : "false",
        active_board.memory_base, active_board.memory_size);
    for (u32 index = 0U; index < active_board.device_count; ++index) {
        const fbr34ker_board_device_t *device = &active_board.devices[index];
        offset = append(buffer, capacity, offset,
            "%s{\"name\":\"%s\",\"type\":\"%s\",\"compatible\":\"%s\","
            "\"base\":%llu,\"size\":%llu,\"irq\":%u,\"flags\":%u}",
            index == 0U ? "" : ",", device->name,
            board_device_type_name(device->type), device->compatible,
            device->base, device->size, device->interrupt, device->flags);
    }
    return append(buffer, capacity, offset, "]}\n");
}
