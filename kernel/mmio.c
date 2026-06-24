#include "fbr34ker/mmio.h"
#include "fbr34ker/string.h"

static fbr34ker_mmio_window_t windows[FBR34KER_MMIO_MAX_WINDOWS];
static fbr34ker_mmio_stats_t statistics;
static fbr34ker_mmio_backend_read_t backend_read;
static fbr34ker_mmio_backend_write_t backend_write;
static void *backend_context;
static volatile bool probe_active;
static volatile bool probe_faulted;
static volatile u64 probe_address;

static void copy_text(char *destination, usize capacity, const char *source)
{
    usize index = 0U;
    if (destination == NULL || capacity == 0U) return;
    if (source != NULL) {
        while (index + 1U < capacity && source[index] != '\0') {
            destination[index] = source[index];
            ++index;
        }
    }
    destination[index] = '\0';
}

static u32 width_bit(u32 width)
{
    switch (width) {
    case 1U: return 1U << 0;
    case 2U: return 1U << 1;
    case 4U: return 1U << 2;
    case 8U: return 1U << 3;
    default: return 0U;
    }
}

static void read_barrier(void)
{
#if defined(__aarch64__)
    __asm__ volatile("dmb oshld" ::: "memory");
#else
    __asm__ volatile("" ::: "memory");
#endif
}

static void write_barrier(void)
{
#if defined(__aarch64__)
    __asm__ volatile("dmb oshst" ::: "memory");
#else
    __asm__ volatile("" ::: "memory");
#endif
}

static bool direct_read(u64 address, u32 width, u64 *value, void *context)
{
    UNUSED(context);
    if (value == NULL) return false;
    read_barrier();
    switch (width) {
    case 1U: *value = *(volatile const u8 *)(usize)address; break;
    case 2U: *value = *(volatile const u16 *)(usize)address; break;
    case 4U: *value = *(volatile const u32 *)(usize)address; break;
    case 8U: *value = *(volatile const u64 *)(usize)address; break;
    default: return false;
    }
    read_barrier();
    return true;
}

static bool direct_write(u64 address, u32 width, u64 value, void *context)
{
    UNUSED(context);
    write_barrier();
    switch (width) {
    case 1U: *(volatile u8 *)(usize)address = (u8)value; break;
    case 2U: *(volatile u16 *)(usize)address = (u16)value; break;
    case 4U: *(volatile u32 *)(usize)address = (u32)value; break;
    case 8U: *(volatile u64 *)(usize)address = value; break;
    default: return false;
    }
    write_barrier();
    return true;
}

void mmio_init(bool immutable)
{
    fm_memset(windows, 0, sizeof(windows));
    fm_memset(&statistics, 0, sizeof(statistics));
    statistics.immutable = immutable;
    statistics.initialized = true;
    backend_read = direct_read;
    backend_write = direct_write;
    backend_context = NULL;
    probe_active = false;
    probe_faulted = false;
    probe_address = 0U;
}

void mmio_shutdown(void)
{
    fm_memset(windows, 0, sizeof(windows));
    fm_memset(&statistics, 0, sizeof(statistics));
    backend_read = NULL;
    backend_write = NULL;
    backend_context = NULL;
    probe_active = false;
    probe_faulted = false;
    probe_address = 0U;
}

bool mmio_ready(void) { return statistics.initialized; }

bool mmio_healthy(void)
{
    if (!statistics.initialized || statistics.window_count > FBR34KER_MMIO_MAX_WINDOWS) return false;
    for (u32 index = 0U; index < statistics.window_count; ++index) {
        if (windows[index].size == 0U ||
            windows[index].base > U64_MAX_VALUE - windows[index].size ||
            windows[index].access_width_mask == 0U) return false;
    }
    return true;
}

bool mmio_register_window(const char *name, u64 base, u64 size,
                          u32 permissions, u32 access_width_mask)
{
    if (!statistics.initialized || name == NULL || *name == '\0' || size == 0U ||
        base > U64_MAX_VALUE - size || statistics.window_count >= FBR34KER_MMIO_MAX_WINDOWS ||
        (permissions & (FBR34KER_MMIO_READ | FBR34KER_MMIO_WRITE)) == 0U ||
        (access_width_mask & 0x0fU) == 0U) return false;
    const u64 end = base + size;
    for (u32 index = 0U; index < statistics.window_count; ++index) {
        const u64 other_end = windows[index].base + windows[index].size;
        if (base < other_end && windows[index].base < end) return false;
    }
    fbr34ker_mmio_window_t *window = &windows[statistics.window_count++];
    fm_memset(window, 0, sizeof(*window));
    copy_text(window->name, sizeof(window->name), name);
    window->base = base;
    window->size = size;
    window->permissions = permissions;
    window->access_width_mask = access_width_mask & 0x0fU;
    return true;
}

u32 mmio_window_count(void) { return statistics.initialized ? statistics.window_count : 0U; }

bool mmio_window_at(u32 index, fbr34ker_mmio_window_t *window)
{
    if (!statistics.initialized || window == NULL || index >= statistics.window_count) return false;
    *window = windows[index];
    return true;
}

bool mmio_address_allowed(u64 address, u32 width, bool write,
                          bool require_probe_safe)
{
    const u32 bit = width_bit(width);
    if (!statistics.initialized || bit == 0U || (address & (u64)(width - 1U)) != 0U ||
        address > U64_MAX_VALUE - width || (write && statistics.immutable)) return false;
    const u64 end = address + width;
    for (u32 index = 0U; index < statistics.window_count; ++index) {
        const fbr34ker_mmio_window_t *window = &windows[index];
        const u32 permission = write ? FBR34KER_MMIO_WRITE : FBR34KER_MMIO_READ;
        if (address >= window->base && end <= window->base + window->size &&
            (window->permissions & permission) != 0U &&
            (window->access_width_mask & bit) != 0U &&
            (!require_probe_safe ||
             (window->permissions & FBR34KER_MMIO_PROBE_SAFE) != 0U)) return true;
    }
    return false;
}

void mmio_set_backend(fbr34ker_mmio_backend_read_t read_backend,
                      fbr34ker_mmio_backend_write_t write_backend,
                      void *context)
{
    if (!statistics.initialized) return;
    backend_read = read_backend != NULL ? read_backend : direct_read;
    backend_write = write_backend != NULL ? write_backend : direct_write;
    backend_context = context;
}

static bool read_value(u64 address, u32 width, u64 *value)
{
    if (value == NULL || !mmio_address_allowed(address, width, false, false)) {
        ++statistics.rejected;
        return false;
    }
    if (backend_read == NULL || !backend_read(address, width, value, backend_context)) {
        ++statistics.backend_failures;
        return false;
    }
    ++statistics.reads;
    return true;
}

static bool write_value(u64 address, u32 width, u64 value)
{
    if (!mmio_address_allowed(address, width, true, false)) {
        ++statistics.rejected;
        return false;
    }
    if (backend_write == NULL || !backend_write(address, width, value, backend_context)) {
        ++statistics.backend_failures;
        return false;
    }
    ++statistics.writes;
    return true;
}

bool mmio_read8(u64 address, u8 *value) { u64 wide; if (!read_value(address, 1U, &wide) || value == NULL) return false; *value = (u8)wide; return true; }
bool mmio_read16(u64 address, u16 *value) { u64 wide; if (!read_value(address, 2U, &wide) || value == NULL) return false; *value = (u16)wide; return true; }
bool mmio_read32(u64 address, u32 *value) { u64 wide; if (!read_value(address, 4U, &wide) || value == NULL) return false; *value = (u32)wide; return true; }

bool mmio_probe_read32(u64 address, u32 *value)
{
    if (value == NULL || !mmio_address_allowed(address, 4U, false, true)) {
        ++statistics.rejected;
        return false;
    }
    u64 wide = 0U;
    probe_address = address;
    probe_faulted = false;
    probe_active = backend_read == direct_read;
    const bool backend_ok = backend_read != NULL &&
        backend_read(address, 4U, &wide, backend_context);
    probe_active = false;
    if (!backend_ok || probe_faulted) {
        ++statistics.backend_failures;
        return false;
    }
    ++statistics.reads;
    *value = (u32)wide;
    return true;
}

bool mmio_handle_fault(u64 esr, u64 far, u64 *return_address)
{
    const u64 exception_class = (esr >> 26U) & 0x3fU;
    if (!probe_active || return_address == NULL ||
        (exception_class != 0x24U && exception_class != 0x25U) ||
        (far != 0U && (far < probe_address || far >= probe_address + 4U))) {
        return false;
    }
    probe_faulted = true;
    probe_active = false;
    *return_address += 4U;
    ++statistics.contained_faults;
    return true;
}
bool mmio_read64(u64 address, u64 *value) { return read_value(address, 8U, value); }
bool mmio_write8(u64 address, u8 value) { return write_value(address, 1U, value); }
bool mmio_write16(u64 address, u16 value) { return write_value(address, 2U, value); }
bool mmio_write32(u64 address, u32 value) { return write_value(address, 4U, value); }
bool mmio_write64(u64 address, u64 value) { return write_value(address, 8U, value); }

bool mmio_update32(u64 address, u32 clear_mask, u32 set_mask, u32 *result)
{
    u32 value;
    if (!mmio_read32(address, &value)) return false;
    value = (value & ~clear_mask) | set_mask;
    if (!mmio_write32(address, value)) return false;
    if (result != NULL) *result = value;
    return true;
}

fbr34ker_mmio_stats_t mmio_stats(void) { return statistics; }
