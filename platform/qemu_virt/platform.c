#include "fbr34ker/platform.h"
#include "fbr34ker/handoff.h"
#include "fbr34ker/timer.h"
#include "fbr34ker/gic.h"

extern void qemu_uart_init(void);
extern u8 __image_start[];
extern u8 __image_end[];

static memory_region_t regions[5];

static u64 psci_hvc(u64 function_id)
{
    register u64 x0 __asm__("x0") = function_id;
    __asm__ volatile("hvc #0" : "+r"(x0) :: "memory");
    return x0;
}

void platform_prepare(const void *boot_context)
{
    UNUSED(boot_context);
}

void platform_init(void)
{
    qemu_uart_init();
    timer_init();
    (void)gic_initialize_v3(0x08000000ULL, 0x080A0000ULL);

    const u64 ram_base = 0x40000000ULL;
    const u64 ram_end = ram_base + 256ULL * 1024ULL * 1024ULL;
    const u64 image_base = (u64)(usize)__image_start;
    const u64 image_end = (u64)(usize)__image_end;

    regions[0] = (memory_region_t){
        .base = 0x08000000ULL,
        .size = 0x01000000ULL,
        .type = MEMORY_REGION_MMIO,
        .attributes = FBR34KER_REGION_ATTR_READ |
                      FBR34KER_REGION_ATTR_WRITE |
                      FBR34KER_REGION_ATTR_DEVICE,
        .name = "QEMU virt GIC/MMIO",
    };
    regions[1] = (memory_region_t){
        .base = 0x09000000ULL,
        .size = 0x1000ULL,
        .type = MEMORY_REGION_MMIO,
        .attributes = FBR34KER_REGION_ATTR_READ |
                      FBR34KER_REGION_ATTR_WRITE |
                      FBR34KER_REGION_ATTR_DEVICE,
        .name = "PL011 UART",
    };
    regions[2] = (memory_region_t){
        .base = ram_base,
        .size = image_base - ram_base,
        .type = MEMORY_REGION_USABLE,
        .attributes = FBR34KER_REGION_ATTR_READ |
                      FBR34KER_REGION_ATTR_WRITE,
        .name = "QEMU RAM before monitor",
    };
    regions[3] = (memory_region_t){
        .base = image_base,
        .size = image_end - image_base,
        .type = MEMORY_REGION_MONITOR,
        .attributes = FBR34KER_REGION_ATTR_READ |
                      FBR34KER_REGION_ATTR_WRITE |
                      FBR34KER_REGION_ATTR_EXECUTE,
        .name = "FBR34KER image/stack/heap",
    };
    regions[4] = (memory_region_t){
        .base = image_end,
        .size = ram_end - image_end,
        .type = MEMORY_REGION_USABLE,
        .attributes = FBR34KER_REGION_ATTR_READ |
                      FBR34KER_REGION_ATTR_WRITE,
        .name = "QEMU RAM after monitor",
    };
}

const char *platform_name(void)
{
    return "QEMU virt (AArch64)";
}

const char *platform_console_transport_name(void)
{
    return "direct QEMU PL011";
}

u64 platform_features(void)
{
    return PLATFORM_FEATURE_CONSOLE_OUTPUT |
           PLATFORM_FEATURE_CONSOLE_INPUT |
           PLATFORM_FEATURE_TIMER |
           PLATFORM_FEATURE_POWER |
           PLATFORM_FEATURE_MEMORY_CONSOLE |
           PLATFORM_FEATURE_DIRECT_PL011 |
           (platform_semihosting_available() ? PLATFORM_FEATURE_SEMIHOSTING : 0U) |
           (gic_available() ? (PLATFORM_FEATURE_INTERRUPTS | PLATFORM_FEATURE_DIRECT_GIC) : 0U);
}

void platform_console_flush(void)
{
}

u64 platform_memory_regions(const memory_region_t **out_regions)
{
    if (out_regions != NULL) {
        *out_regions = regions;
    }
    return ARRAY_COUNT(regions);
}

bool platform_framebuffer_info(platform_framebuffer_t *framebuffer)
{
    UNUSED(framebuffer);
    return false;
}

bool platform_framebuffer_clear(u32 color)
{
    UNUSED(color);
    return false;
}

bool platform_framebuffer_flush(void)
{
    return false;
}

u32 platform_interrupt_ack(void)
{
    return gic_acknowledge();
}

void platform_interrupt_complete(u32 interrupt_id)
{
    gic_complete(interrupt_id);
}

bool platform_interrupt_set_enabled(u32 interrupt_id, bool enabled)
{
    return gic_set_enabled(interrupt_id, enabled);
}

bool platform_interrupt_self_test(void)
{
    return gic_self_test();
}

const char *platform_interrupt_controller_name(void)
{
    return gic_kind_name(gic_info().kind);
}

bool platform_watchdog_configure(u64 timeout_ms)
{
    UNUSED(timeout_ms);
    return false;
}

void platform_watchdog_kick(void)
{
}

NORETURN void platform_reboot(void)
{
    (void)psci_hvc(0x84000009ULL);
    for (;;) {
        __asm__ volatile("wfe");
    }
}

NORETURN void platform_halt(void)
{
    (void)psci_hvc(0x84000008ULL);
    for (;;) {
        __asm__ volatile("wfe");
    }
}
