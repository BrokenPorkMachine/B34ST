#include "fbr34ker/platform.h"
#include "fbr34ker/handoff.h"
#include "fbr34ker/string.h"
#include "fbr34ker/timer.h"
#include "fbr34ker/gic.h"
#include "fbr34ker/device_tree.h"
#include "fbr34ker/service_guard.h"

// SPDX-License-Identifier: BSD-2-Clause
static const fbr34ker_handoff_t *handoff;
static const fbr34ker_platform_services_t *services;
static memory_region_t regions[FBR34KER_HANDOFF_MAX_REGIONS + 1U];
static u64 region_count;
static volatile u32 *direct_pl011;
extern u8 __image_start[];
extern u8 __image_end[];

static bool service_available(u64 capability);


#define PL011_DR_OFFSET 0x00U
#define PL011_FR_OFFSET 0x18U
#define PL011_FR_RXFE (1U << 4)
#define PL011_FR_TXFF (1U << 5)
#define HANDOFF_TYPE_BIT(type) (1U << (type))

static bool handoff_console_callback_available(void)
{
    return service_available(FBR34KER_SERVICE_CONSOLE_WRITE) ||
        (handoff != NULL && handoff->early_putc != NULL &&
         (handoff->version == FBR34KER_HANDOFF_VERSION_1 ||
          (handoff->flags & FBR34KER_HANDOFF_FLAG_EARLY_CONSOLE_VALID) != 0U));
}

static void direct_pl011_initialize(void)
{
    direct_pl011 = NULL;
    if (handoff_console_callback_available() || handoff == NULL ||
        !device_tree_valid()) {
        return;
    }
    char path[DEVICE_TREE_MAX_STRING];
    device_tree_reg_t reg;
    if (!device_tree_stdout_path(path, sizeof(path)) ||
        (!device_tree_string_list_contains(path, "compatible", "arm,pl011") &&
         !device_tree_string_list_contains(path, "compatible", "arm,primecell")) ||
        !device_tree_get_reg(path, 0U, &reg) || reg.size < 0x1000U ||
        (reg.address & 3U) != 0U ||
        !fbr34ker_handoff_describes_range(
            handoff, reg.address, 0x1000U,
            HANDOFF_TYPE_BIT(FBR34KER_HANDOFF_REGION_MMIO),
            FBR34KER_REGION_ATTR_READ | FBR34KER_REGION_ATTR_WRITE |
                FBR34KER_REGION_ATTR_DEVICE)) {
        return;
    }
    direct_pl011 = (volatile u32 *)(usize)reg.address;
}

static bool direct_pl011_putc(char value)
{
    if (direct_pl011 == NULL) {
        return false;
    }
    for (u32 spins = 0U; spins < 1000000U; ++spins) {
        if ((direct_pl011[PL011_FR_OFFSET / 4U] & PL011_FR_TXFF) == 0U) {
            direct_pl011[PL011_DR_OFFSET / 4U] = (u32)(u8)value;
            return true;
        }
        __asm__ volatile("yield");
    }
    return false;
}

static memory_region_type_t translate_type(u32 type)
{
    switch (type) {
    case FBR34KER_HANDOFF_REGION_USABLE: return MEMORY_REGION_USABLE;
    case FBR34KER_HANDOFF_REGION_MMIO: return MEMORY_REGION_MMIO;
    case FBR34KER_HANDOFF_REGION_MONITOR: return MEMORY_REGION_MONITOR;
    case FBR34KER_HANDOFF_REGION_FRAMEBUFFER: return MEMORY_REGION_FRAMEBUFFER;
    default: return MEMORY_REGION_RESERVED;
    }
}

static bool service_available(u64 capability)
{
    return services != NULL && (services->capabilities & capability) != 0U;
}

void platform_prepare(const void *boot_context)
{
    UNUSED(boot_context);
    handoff = fbr34ker_handoff_active();
    services = handoff != NULL && handoff->version >= FBR34KER_HANDOFF_VERSION_4 &&
        (handoff->flags & FBR34KER_HANDOFF_FLAG_PLATFORM_SERVICES_VALID) != 0U
        ? handoff->platform_services : NULL;
    service_guard_init();
}

void platform_init(void)
{
    region_count = 0U;
    bool monitor_described = false;
    const u64 image_base = (u64)(usize)__image_start;
    const u64 image_size = (u64)(usize)(__image_end - __image_start);
    if (handoff != NULL) {
        for (u32 index = 0U; index < handoff->memory_region_count; ++index) {
            const fbr34ker_handoff_region_t *source = &handoff->memory_regions[index];
            regions[region_count++] = (memory_region_t){
                .base = source->base,
                .size = source->size,
                .type = translate_type(source->type),
                .attributes = source->attributes,
                .name = "loader-provided region",
            };
            if (source->type == FBR34KER_HANDOFF_REGION_MONITOR &&
                image_base >= source->base &&
                image_base + image_size <= source->base + source->size) {
                monitor_described = true;
            }
        }
    }
    if (!monitor_described) {
        regions[region_count++] = (memory_region_t){
            .base = image_base,
            .size = image_size,
            .type = MEMORY_REGION_MONITOR,
            .attributes = FBR34KER_REGION_ATTR_READ |
                          FBR34KER_REGION_ATTR_WRITE |
                          FBR34KER_REGION_ATTR_EXECUTE,
            .name = "FBR34KER image/stack/heap",
        };
    }
    timer_init();
    direct_pl011_initialize();
    if (!service_available(FBR34KER_SERVICE_INTERRUPT_CONTROLLER)) {
        (void)gic_initialize_from_fdt();
    }
}

const char *platform_name(void)
{
    return "Generic ARM64 handoff";
}

const char *platform_console_transport_name(void)
{
    if (service_available(FBR34KER_SERVICE_CONSOLE_WRITE)) return "loader service callback";
    if (handoff != NULL && handoff->early_putc != NULL) return "loader early callback";
    if (direct_pl011 != NULL) return "validated FDT PL011";
    return "memory diagnostic ring only";
}

u64 platform_features(void)
{
    u64 features = 0U;
    if (service_available(FBR34KER_SERVICE_CONSOLE_WRITE) ||
        (handoff != NULL && handoff->early_putc != NULL) || direct_pl011 != NULL) {
        features |= PLATFORM_FEATURE_CONSOLE_OUTPUT;
    }
    if (service_available(FBR34KER_SERVICE_CONSOLE_READ) ||
        (handoff != NULL && handoff->runtime_getc != NULL) || direct_pl011 != NULL) {
        features |= PLATFORM_FEATURE_CONSOLE_INPUT;
    }
    if (service_available(FBR34KER_SERVICE_CONSOLE_FLUSH)) {
        features |= PLATFORM_FEATURE_CONSOLE_FLUSH;
    }
    /* Generic ARM64 always has the architectural counter fallback. */
    features |= PLATFORM_FEATURE_TIMER;
    if (handoff != NULL && handoff->version >= FBR34KER_HANDOFF_VERSION_3 &&
        (handoff->flags & FBR34KER_HANDOFF_FLAG_POWER_VALID) != 0U) {
        features |= PLATFORM_FEATURE_POWER;
    }
    if (handoff != NULL &&
        (handoff->flags & FBR34KER_HANDOFF_FLAG_FRAMEBUFFER_VALID) != 0U) {
        features |= PLATFORM_FEATURE_FRAMEBUFFER;
    }
    if (service_available(FBR34KER_SERVICE_FRAMEBUFFER_FLUSH)) {
        features |= PLATFORM_FEATURE_FRAMEBUFFER_FLUSH;
    }
    if (service_available(FBR34KER_SERVICE_INTERRUPT_CONTROLLER) || gic_available()) {
        features |= PLATFORM_FEATURE_INTERRUPTS;
    }
    if (gic_available()) {
        features |= PLATFORM_FEATURE_DIRECT_GIC;
    }
    if (direct_pl011 != NULL) {
        features |= PLATFORM_FEATURE_DIRECT_PL011;
    }
    features |= PLATFORM_FEATURE_MEMORY_CONSOLE;
    if (service_available(FBR34KER_SERVICE_WATCHDOG_CONFIGURE)) {
        features |= PLATFORM_FEATURE_WATCHDOG_CONFIGURE;
    }
    if (service_available(FBR34KER_SERVICE_WATCHDOG_KICK)) {
        features |= PLATFORM_FEATURE_WATCHDOG_KICK;
    }
    return features;
}

void platform_uart_putc(char value)
{
    if (service_available(FBR34KER_SERVICE_CONSOLE_WRITE) &&
        service_guard_begin(SERVICE_GUARD_CONSOLE_WRITE)) {
        const usize written = services->console_write(&value, 1U, services->console_context);
        service_guard_end(SERVICE_GUARD_CONSOLE_WRITE, written == 1U);
        if (written == 1U) return;
    }
    if (handoff == NULL || handoff->early_putc == NULL) {
        (void)direct_pl011_putc(value);
        return;
    }
    if (handoff->version == FBR34KER_HANDOFF_VERSION_1 ||
        (handoff->flags & FBR34KER_HANDOFF_FLAG_EARLY_CONSOLE_VALID) != 0U) {
        handoff->early_putc(value, handoff->early_console_context);
    }
}

int platform_uart_getc_nonblocking(void)
{
    if (service_available(FBR34KER_SERVICE_CONSOLE_READ) &&
        service_guard_begin(SERVICE_GUARD_CONSOLE_READ)) {
        char value = 0;
        const usize count = services->console_read(&value, 1U, services->console_context);
        service_guard_end(SERVICE_GUARD_CONSOLE_READ, count <= 1U);
        return count == 1U ? (int)(u8)value : -1;
    }
    if (handoff != NULL && handoff->version >= FBR34KER_HANDOFF_VERSION_3 &&
        (handoff->flags & FBR34KER_HANDOFF_FLAG_RUNTIME_IO_VALID) != 0U &&
        handoff->runtime_getc != NULL &&
        service_guard_begin(SERVICE_GUARD_RUNTIME_INPUT)) {
        const int value = handoff->runtime_getc(handoff->runtime_io_context);
        service_guard_end(SERVICE_GUARD_RUNTIME_INPUT, value >= -1 && value <= 255);
        return value;
    }
    if (direct_pl011 != NULL &&
        (direct_pl011[PL011_FR_OFFSET / 4U] & PL011_FR_RXFE) == 0U) {
        return (int)(u8)direct_pl011[PL011_DR_OFFSET / 4U];
    }
    return -1;
}

void platform_console_flush(void)
{
    if (service_available(FBR34KER_SERVICE_CONSOLE_FLUSH) &&
        service_guard_begin(SERVICE_GUARD_CONSOLE_FLUSH)) {
        services->console_flush(services->console_context);
        service_guard_end(SERVICE_GUARD_CONSOLE_FLUSH, true);
    }
}

u64 platform_memory_regions(const memory_region_t **out_regions)
{
    if (out_regions != NULL) {
        *out_regions = regions;
    }
    return region_count;
}

bool platform_framebuffer_info(platform_framebuffer_t *framebuffer)
{
    if (framebuffer == NULL || handoff == NULL ||
        handoff->version < FBR34KER_HANDOFF_VERSION_4 ||
        (handoff->flags & FBR34KER_HANDOFF_FLAG_FRAMEBUFFER_VALID) == 0U) {
        return false;
    }
    *framebuffer = (platform_framebuffer_t){
        .base = handoff->framebuffer.base,
        .size = handoff->framebuffer_size,
        .width = handoff->framebuffer.width,
        .height = handoff->framebuffer.height,
        .pixels_per_row = handoff->framebuffer.pixels_per_row,
        .pixel_format = handoff->framebuffer.pixel_format,
        .bytes_per_pixel = handoff->framebuffer_bytes_per_pixel,
        .rotation = handoff->framebuffer_rotation,
    };
    return true;
}

bool platform_framebuffer_clear(u32 color)
{
    platform_framebuffer_t framebuffer;
    if (!platform_framebuffer_info(&framebuffer)) {
        return false;
    }
    const u8 red = (u8)(color >> 16U);
    const u8 green = (u8)(color >> 8U);
    const u8 blue = (u8)color;
    u8 *pixels = (u8 *)(usize)framebuffer.base;
    const u64 row_bytes = (u64)framebuffer.pixels_per_row *
                          framebuffer.bytes_per_pixel;
    for (u32 y = 0U; y < framebuffer.height; ++y) {
        u8 *row = pixels + (usize)((u64)y * row_bytes);
        for (u32 x = 0U; x < framebuffer.width; ++x) {
            u8 *pixel = row + (usize)((u64)x * framebuffer.bytes_per_pixel);
            if (framebuffer.pixel_format == FBR34KER_PIXEL_FORMAT_RGB565) {
                const u16 value = (u16)(((u16)(red >> 3U) << 11U) |
                                        ((u16)(green >> 2U) << 5U) |
                                        (u16)(blue >> 3U));
                pixel[0] = (u8)value;
                pixel[1] = (u8)(value >> 8U);
            } else if (framebuffer.pixel_format == FBR34KER_PIXEL_FORMAT_BGRA8888) {
                pixel[0] = red;
                pixel[1] = green;
                pixel[2] = blue;
                pixel[3] = 0xffU;
            } else {
                pixel[0] = blue;
                pixel[1] = green;
                pixel[2] = red;
                pixel[3] = framebuffer.pixel_format == FBR34KER_PIXEL_FORMAT_ARGB8888
                    ? 0xffU : 0U;
            }
        }
    }
    return platform_framebuffer_flush();
}

bool platform_framebuffer_flush(void)
{
    if (service_available(FBR34KER_SERVICE_FRAMEBUFFER_FLUSH) &&
        service_guard_begin(SERVICE_GUARD_FRAMEBUFFER_FLUSH)) {
        const bool result = services->framebuffer_flush(services->framebuffer_context);
        service_guard_end(SERVICE_GUARD_FRAMEBUFFER_FLUSH, result);
        return result;
    }
    return (platform_features() & PLATFORM_FEATURE_FRAMEBUFFER) != 0U;
}

u32 platform_interrupt_ack(void)
{
    if (service_available(FBR34KER_SERVICE_INTERRUPT_CONTROLLER) &&
        service_guard_begin(SERVICE_GUARD_INTERRUPT_ACK)) {
        const u32 result = services->interrupt_ack(services->interrupt_context);
        service_guard_end(SERVICE_GUARD_INTERRUPT_ACK, true);
        return result;
    }
    return gic_acknowledge();
}

void platform_interrupt_complete(u32 interrupt_id)
{
    if (service_available(FBR34KER_SERVICE_INTERRUPT_CONTROLLER) &&
        service_guard_begin(SERVICE_GUARD_INTERRUPT_COMPLETE)) {
        services->interrupt_complete(interrupt_id, services->interrupt_context);
        service_guard_end(SERVICE_GUARD_INTERRUPT_COMPLETE, true);
    } else {
        gic_complete(interrupt_id);
    }
}

bool platform_interrupt_set_enabled(u32 interrupt_id, bool enabled)
{
    if (service_available(FBR34KER_SERVICE_INTERRUPT_CONTROLLER) &&
        service_guard_begin(SERVICE_GUARD_INTERRUPT_ENABLE)) {
        const bool result = services->interrupt_set_enabled(
            interrupt_id, enabled, services->interrupt_context);
        service_guard_end(SERVICE_GUARD_INTERRUPT_ENABLE, result);
        return result;
    }
    return gic_set_enabled(interrupt_id, enabled);
}

bool platform_interrupt_self_test(void)
{
    if (service_available(FBR34KER_SERVICE_INTERRUPT_CONTROLLER)) {
        const u32 probe = 32U;
        return platform_interrupt_set_enabled(probe, true) &&
               platform_interrupt_set_enabled(probe, false);
    }
    return gic_self_test();
}

const char *platform_interrupt_controller_name(void)
{
    if (service_available(FBR34KER_SERVICE_INTERRUPT_CONTROLLER)) {
        return "loader callbacks";
    }
    return gic_available() ? gic_kind_name(gic_info().kind) : "polling-only";
}

bool platform_semihosting_available(void)
{
    return false;
}

bool platform_semihosting_putc(char value)
{
    UNUSED(value);
    return false;
}

bool platform_watchdog_configure(u64 timeout_ms)
{
    if (!service_available(FBR34KER_SERVICE_WATCHDOG_CONFIGURE) ||
        !service_guard_begin(SERVICE_GUARD_WATCHDOG_CONFIGURE)) return false;
    const bool result = services->watchdog_configure(timeout_ms, services->watchdog_context);
    service_guard_end(SERVICE_GUARD_WATCHDOG_CONFIGURE, result);
    return result;
}

void platform_watchdog_kick(void)
{
    if (service_available(FBR34KER_SERVICE_WATCHDOG_KICK) &&
        service_guard_begin(SERVICE_GUARD_WATCHDOG_KICK)) {
        services->watchdog_kick(services->watchdog_context);
        service_guard_end(SERVICE_GUARD_WATCHDOG_KICK, true);
    }
}

NORETURN void platform_reboot(void)
{
    if (handoff != NULL && handoff->version >= FBR34KER_HANDOFF_VERSION_3 &&
        (handoff->flags & FBR34KER_HANDOFF_FLAG_POWER_VALID) != 0U &&
        handoff->reboot != NULL && service_guard_begin(SERVICE_GUARD_REBOOT)) {
        handoff->reboot(handoff->power_context);
        service_guard_end(SERVICE_GUARD_REBOOT, false);
    }
    for (;;) {
        __asm__ volatile("wfe");
    }
}

NORETURN void platform_halt(void)
{
    if (handoff != NULL && handoff->version >= FBR34KER_HANDOFF_VERSION_3 &&
        (handoff->flags & FBR34KER_HANDOFF_FLAG_POWER_VALID) != 0U &&
        handoff->halt != NULL && service_guard_begin(SERVICE_GUARD_HALT)) {
        handoff->halt(handoff->power_context);
        service_guard_end(SERVICE_GUARD_HALT, false);
    }
    for (;;) {
        __asm__ volatile("wfe");
    }
}
