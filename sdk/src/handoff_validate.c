#include "fbr34ker_sdk.h"

// SPDX-License-Identifier: BSD-2-Clause
static bool valid_range(uint64_t base, uint64_t size) {
    return size != 0U && base <= UINT64_MAX - size;
}
static bool aligned_pointer(const void *pointer, uintptr_t alignment) {
    return pointer == NULL || (((uintptr_t)pointer & (alignment - 1U)) == 0U);
}
static bool aligned_callback(const void *callback) {
    return callback == NULL || (((uintptr_t)callback & 3U) == 0U);
}
static bool callback_match(uint64_t caps, uint64_t flag, const void *callback) {
    return ((caps & flag) != 0U) == (callback != NULL);
}
static bool region_covers(const fbr34ker_handoff_t *h, uint64_t base,
                          uint64_t size, uint32_t types,
                          uint32_t required_attributes) {
    if (!valid_range(base, size)) return false;
    const uint64_t end = base + size;
    for (uint32_t i = 0; i < h->memory_region_count; ++i) {
        const fbr34ker_handoff_region_t *r = &h->memory_regions[i];
        if (r->type < 32U && (types & (1U << r->type)) != 0U &&
            (r->attributes & required_attributes) == required_attributes &&
            base >= r->base && end <= r->base + r->size) return true;
    }
    return false;
}
static bool framebuffer_valid(const fbr34ker_handoff_t *h) {
    const bool flagged = (h->flags & FBR34KER_HANDOFF_FLAG_FRAMEBUFFER_VALID) != 0U;
    const bool present = h->framebuffer.base != 0U || h->framebuffer.width != 0U ||
        h->framebuffer.height != 0U || h->framebuffer.pixels_per_row != 0U ||
        h->framebuffer_size != 0U || h->framebuffer_bytes_per_pixel != 0U;
    if (flagged != present) return false;
    if (!flagged) return h->framebuffer_rotation == 0U;
    if (h->framebuffer.base == 0U || h->framebuffer.width == 0U ||
        h->framebuffer.height == 0U ||
        h->framebuffer.pixels_per_row < h->framebuffer.width ||
        h->framebuffer_size == 0U) return false;
    const uint32_t bpp = h->framebuffer_bytes_per_pixel;
    const bool format_matches =
        (h->framebuffer.pixel_format == FBR34KER_PIXEL_FORMAT_RGB565 && bpp == 2U) ||
        ((h->framebuffer.pixel_format == FBR34KER_PIXEL_FORMAT_XRGB8888 ||
          h->framebuffer.pixel_format == FBR34KER_PIXEL_FORMAT_ARGB8888 ||
          h->framebuffer.pixel_format == FBR34KER_PIXEL_FORMAT_BGRA8888) && bpp == 4U);
    if (!format_matches ||
        (h->framebuffer_rotation != 0U && h->framebuffer_rotation != 90U &&
         h->framebuffer_rotation != 180U && h->framebuffer_rotation != 270U)) return false;
    if (h->framebuffer.pixels_per_row > UINT64_MAX / bpp) return false;
    const uint64_t row_bytes = (uint64_t)h->framebuffer.pixels_per_row * bpp;
    if (h->framebuffer.height > UINT64_MAX / row_bytes ||
        row_bytes * h->framebuffer.height > h->framebuffer_size) return false;
    const uint32_t types = (1U << FBR34KER_HANDOFF_REGION_RESERVED) |
        (1U << FBR34KER_HANDOFF_REGION_MMIO) |
        (1U << FBR34KER_HANDOFF_REGION_FRAMEBUFFER);
    return region_covers(h, h->framebuffer.base, h->framebuffer_size, types,
        FBR34KER_REGION_ATTR_READ | FBR34KER_REGION_ATTR_WRITE);
}
static bool service_table_valid(const fbr34ker_handoff_t *h) {
    const bool flagged = (h->flags & FBR34KER_HANDOFF_FLAG_PLATFORM_SERVICES_VALID) != 0U;
    const bool present = h->platform_services != NULL || h->platform_services_size != 0U;
    if (flagged != present) return false;
    if (!flagged) return true;
    const fbr34ker_platform_services_t *s = h->platform_services;
    if (s == NULL || !aligned_pointer(s, 8U) || h->platform_services_size < sizeof(*s) ||
        s->version != FBR34KER_PLATFORM_SERVICES_VERSION_1 ||
        s->structure_size < sizeof(*s) || s->structure_size > h->platform_services_size ||
        s->reserved != 0U || (s->capabilities & ~FBR34KER_SERVICE_FLAGS_SUPPORTED) != 0U)
        return false;
    if (!callback_match(s->capabilities, FBR34KER_SERVICE_CONSOLE_WRITE, (const void *)s->console_write) ||
        !callback_match(s->capabilities, FBR34KER_SERVICE_CONSOLE_READ, (const void *)s->console_read) ||
        !callback_match(s->capabilities, FBR34KER_SERVICE_CONSOLE_FLUSH, (const void *)s->console_flush) ||
        !callback_match(s->capabilities, FBR34KER_SERVICE_FRAMEBUFFER_FLUSH, (const void *)s->framebuffer_flush) ||
        !callback_match(s->capabilities, FBR34KER_SERVICE_WATCHDOG_CONFIGURE, (const void *)s->watchdog_configure) ||
        !callback_match(s->capabilities, FBR34KER_SERVICE_WATCHDOG_KICK, (const void *)s->watchdog_kick))
        return false;
    const bool irq_cap = (s->capabilities & FBR34KER_SERVICE_INTERRUPT_CONTROLLER) != 0U;
    const bool irq_any = s->interrupt_ack != NULL || s->interrupt_complete != NULL ||
        s->interrupt_set_enabled != NULL;
    if (irq_cap != irq_any || (irq_cap && (s->interrupt_ack == NULL ||
        s->interrupt_complete == NULL || s->interrupt_set_enabled == NULL))) return false;
    if (!aligned_callback((const void *)s->console_write) ||
        !aligned_callback((const void *)s->console_read) ||
        !aligned_callback((const void *)s->console_flush) ||
        !aligned_callback((const void *)s->framebuffer_flush) ||
        !aligned_callback((const void *)s->interrupt_ack) ||
        !aligned_callback((const void *)s->interrupt_complete) ||
        !aligned_callback((const void *)s->interrupt_set_enabled) ||
        !aligned_callback((const void *)s->watchdog_configure) ||
        !aligned_callback((const void *)s->watchdog_kick)) return false;
    if ((s->capabilities & FBR34KER_SERVICE_FRAMEBUFFER_FLUSH) != 0U &&
        (h->flags & FBR34KER_HANDOFF_FLAG_FRAMEBUFFER_VALID) == 0U) return false;
    return true;
}

fbr34ker_sdk_result_t fbr34ker_handoff_validate_sdk(const fbr34ker_handoff_t *h) {
    if (h == NULL) return FBR34KER_SDK_ERR_ARGUMENT;
    if (h->magic != FBR34KER_HANDOFF_MAGIC || h->version != FBR34KER_HANDOFF_VERSION_4 ||
        h->structure_size < sizeof(*h) || (h->flags & ~FBR34KER_HANDOFF_FLAGS_SUPPORTED) != 0U ||
        h->reserved != 0U || h->reserved_v2 != 0U || h->reserved_v4_small != 0U ||
        h->reserved_v4[0] != 0U || h->reserved_v4[1] != 0U) return FBR34KER_SDK_ERR_ABI;
    if (!valid_range(h->monitor_base, h->monitor_size) || h->memory_region_count == 0U ||
        h->memory_region_count > FBR34KER_HANDOFF_MAX_REGIONS || h->memory_regions == NULL ||
        !aligned_pointer(h->memory_regions, 8U)) return FBR34KER_SDK_ERR_RANGE;
    uint64_t previous_end = 0U;
    bool monitor_covered = false;
    for (uint32_t index = 0; index < h->memory_region_count; ++index) {
        const fbr34ker_handoff_region_t *r = &h->memory_regions[index];
        if (!valid_range(r->base, r->size)) return FBR34KER_SDK_ERR_RANGE;
        if (index != 0U && r->base < previous_end) return FBR34KER_SDK_ERR_OVERLAP;
        previous_end = r->base + r->size;
        if (r->type < FBR34KER_HANDOFF_REGION_USABLE ||
            r->type > FBR34KER_HANDOFF_REGION_FRAMEBUFFER ||
            (r->attributes & ~FBR34KER_REGION_ATTR_SUPPORTED) != 0U)
            return FBR34KER_SDK_ERR_PERMISSIONS;
        if (r->type == FBR34KER_HANDOFF_REGION_MMIO &&
            (r->attributes & FBR34KER_REGION_ATTR_DEVICE) == 0U)
            return FBR34KER_SDK_ERR_PERMISSIONS;
        if (r->type == FBR34KER_HANDOFF_REGION_FRAMEBUFFER &&
            (r->attributes & (FBR34KER_REGION_ATTR_READ | FBR34KER_REGION_ATTR_WRITE)) !=
            (FBR34KER_REGION_ATTR_READ | FBR34KER_REGION_ATTR_WRITE))
            return FBR34KER_SDK_ERR_PERMISSIONS;
        if (r->type == FBR34KER_HANDOFF_REGION_MONITOR && h->monitor_base >= r->base &&
            h->monitor_base + h->monitor_size <= r->base + r->size &&
            (r->attributes & (FBR34KER_REGION_ATTR_READ | FBR34KER_REGION_ATTR_WRITE |
             FBR34KER_REGION_ATTR_EXECUTE)) == (FBR34KER_REGION_ATTR_READ |
             FBR34KER_REGION_ATTR_WRITE | FBR34KER_REGION_ATTR_EXECUTE)) monitor_covered = true;
    }
    if (!monitor_covered) return FBR34KER_SDK_ERR_PERMISSIONS;
    if (h->entry_exception_level < 1U || h->entry_exception_level > 3U ||
        (h->page_granule != FBR34KER_PAGE_GRANULE_4K &&
         h->page_granule != FBR34KER_PAGE_GRANULE_16K &&
         h->page_granule != FBR34KER_PAGE_GRANULE_64K)) return FBR34KER_SDK_ERR_ABI;

    const bool early = h->early_putc != NULL;
    const bool runtime = h->runtime_getc != NULL;
    const bool timer_any = h->timer_read != NULL || h->timer_frequency != NULL;
    const bool power_any = h->reboot != NULL || h->halt != NULL;
    const bool dt_any = h->device_tree != NULL || h->device_tree_size != 0U;
    if (((h->flags & FBR34KER_HANDOFF_FLAG_EARLY_CONSOLE_VALID) != 0U) != early ||
        ((h->flags & FBR34KER_HANDOFF_FLAG_RUNTIME_IO_VALID) != 0U) != runtime ||
        ((h->flags & FBR34KER_HANDOFF_FLAG_TIMER_VALID) != 0U) != timer_any ||
        ((h->flags & FBR34KER_HANDOFF_FLAG_POWER_VALID) != 0U) != power_any ||
        ((h->flags & FBR34KER_HANDOFF_FLAG_DEVICE_TREE_VALID) != 0U) != dt_any)
        return FBR34KER_SDK_ERR_CALLBACK;
    if ((timer_any && (h->timer_read == NULL || h->timer_frequency == NULL)) ||
        (power_any && (h->reboot == NULL || h->halt == NULL)) ||
        (dt_any && (h->device_tree == NULL || !aligned_pointer(h->device_tree, 4U) ||
         h->device_tree_size == 0U || h->device_tree_size > FBR34KER_HANDOFF_MAX_DEVICE_TREE_SIZE)) ||
        !aligned_callback((const void *)h->early_putc) ||
        !aligned_callback((const void *)h->runtime_getc) ||
        !aligned_callback((const void *)h->timer_read) ||
        !aligned_callback((const void *)h->timer_frequency) ||
        !aligned_callback((const void *)h->reboot) ||
        !aligned_callback((const void *)h->halt)) return FBR34KER_SDK_ERR_CALLBACK;

    if (h->boot_module_count > FBR34KER_HANDOFF_MAX_BOOT_MODULES ||
        (h->boot_module_count != 0U && (h->boot_modules == NULL ||
         !aligned_pointer(h->boot_modules, 8U)))) return FBR34KER_SDK_ERR_RANGE;
    for (uint32_t i = 0U; i < h->boot_module_count; ++i) {
        const fbr34ker_handoff_boot_module_t *m = &h->boot_modules[i];
        if (m->base == NULL || m->size == 0U ||
            (m->type == FBR34KER_BOOT_MODULE_TYPE_FMOD &&
             m->size > FBR34KER_BOOT_MODULE_MAX_FMOD_SIZE)) return FBR34KER_SDK_ERR_RANGE;
    }
    if (!service_table_valid(h) || !framebuffer_valid(h)) return FBR34KER_SDK_ERR_CALLBACK;

    const bool policy_present = h->module_capability_allow_mask != 0U ||
        h->module_slot_limit != 0U || h->module_instruction_budget_limit != 0U;
    if (((h->flags & FBR34KER_HANDOFF_FLAG_MODULE_POLICY_VALID) != 0U) != policy_present ||
        (h->module_capability_allow_mask & ~FBR34KER_HANDOFF_MODULE_CAP_MASK_SUPPORTED) != 0U ||
        h->module_slot_limit > FBR34KER_HANDOFF_MAX_MODULE_SLOTS ||
        (h->module_slot_limit != 0U && (h->module_instruction_budget_limit == 0U ||
         h->module_instruction_budget_limit > FBR34KER_HANDOFF_MAX_INSTRUCTION_BUDGET)))
        return FBR34KER_SDK_ERR_POLICY;
    return FBR34KER_SDK_OK;
}

const char *fbr34ker_sdk_result_string(fbr34ker_sdk_result_t result) {
    static const char *const names[] = {"ok","argument","abi","range","overlap","permissions","callback","policy","capacity"};
    return (unsigned)result < sizeof(names)/sizeof(names[0]) ? names[result] : "unknown";
}
