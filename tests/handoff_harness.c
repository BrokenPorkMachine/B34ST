#include "fbr34ker/handoff.h"
#include "fbr34ker/string.h"

// SPDX-License-Identifier: BSD-2-Clause
static void putc_stub(char value, void *context) { UNUSED(value); UNUSED(context); }
static int getc_stub(void *context) { UNUSED(context); return -1; }
static u64 timer_stub(void *context) { UNUSED(context); return 1000U; }
static void power_stub(void *context) { UNUSED(context); }
static usize write_stub(const char *data, usize size, void *context)
{
    UNUSED(data); UNUSED(context); return size;
}
static usize read_stub(char *data, usize size, void *context)
{
    UNUSED(data); UNUSED(size); UNUSED(context); return 0U;
}
static void flush_stub(void *context) { UNUSED(context); }
static u32 irq_ack_stub(void *context)
{
    UNUSED(context); return 0xffffffffU;
}
static void irq_complete_stub(u32 interrupt_id, void *context)
{
    UNUSED(interrupt_id); UNUSED(context);
}
static bool irq_enabled_stub(u32 interrupt_id, bool enabled, void *context)
{
    UNUSED(interrupt_id); UNUSED(enabled); UNUSED(context); return true;
}
static bool watchdog_configure_stub(u64 timeout_ms, void *context)
{
    UNUSED(timeout_ms); UNUSED(context); return true;
}
static void watchdog_kick_stub(void *context) { UNUSED(context); }

static fbr34ker_handoff_region_t test_regions[1];

static fbr34ker_handoff_t valid_v3(void)
{
    test_regions[0] = (fbr34ker_handoff_region_t){
        .base = 0x80000000ULL,
        .size = 0x01000000ULL,
        .type = FBR34KER_HANDOFF_REGION_USABLE,
        .attributes = 0U,
    };
    fbr34ker_handoff_t handoff;
    fm_memset(&handoff, 0, sizeof(handoff));
    handoff.magic = FBR34KER_HANDOFF_MAGIC;
    handoff.version = FBR34KER_HANDOFF_VERSION_3;
    handoff.structure_size = (u32)__builtin_offsetof(
        fbr34ker_handoff_t, platform_services);
    handoff.monitor_base = 0x80000000ULL;
    handoff.monitor_size = 0x00800000ULL;
    handoff.memory_regions = test_regions;
    handoff.memory_region_count = ARRAY_COUNT(test_regions);
    handoff.flags = FBR34KER_HANDOFF_FLAG_EARLY_CONSOLE_VALID |
                    FBR34KER_HANDOFF_FLAG_RUNTIME_IO_VALID |
                    FBR34KER_HANDOFF_FLAG_TIMER_VALID |
                    FBR34KER_HANDOFF_FLAG_POWER_VALID;
    handoff.early_putc = putc_stub;
    handoff.runtime_getc = getc_stub;
    handoff.timer_read = timer_stub;
    handoff.timer_frequency = timer_stub;
    handoff.reboot = power_stub;
    handoff.halt = power_stub;
    return handoff;
}

typedef struct ALIGNED(16) {
    u8 prefix[64];
    fbr34ker_handoff_region_t regions[2];
    fbr34ker_platform_services_t services;
    u8 payload[2048];
} v4_arena_t;

static v4_arena_t v4_arena;

static fbr34ker_handoff_t valid_v4(void)
{
    fm_memset(&v4_arena, 0, sizeof(v4_arena));
    u64 callback_min = (u64)(usize)putc_stub;
    u64 callback_max = callback_min;
#define TRACK_CALLBACK(callback) do { \
    const u64 address = (u64)(usize)(callback); \
    if (address < callback_min) callback_min = address; \
    if (address > callback_max) callback_max = address; \
} while (0)
    TRACK_CALLBACK(getc_stub); TRACK_CALLBACK(timer_stub); TRACK_CALLBACK(power_stub);
    TRACK_CALLBACK(write_stub); TRACK_CALLBACK(read_stub); TRACK_CALLBACK(flush_stub);
    TRACK_CALLBACK(irq_ack_stub); TRACK_CALLBACK(irq_complete_stub);
    TRACK_CALLBACK(irq_enabled_stub); TRACK_CALLBACK(watchdog_configure_stub);
    TRACK_CALLBACK(watchdog_kick_stub);
#undef TRACK_CALLBACK
    callback_min &= ~0xfffULL;
    callback_max = (callback_max + 0x1000ULL) & ~0xfffULL;
    const fbr34ker_handoff_region_t code_region = {
        .base = callback_min, .size = callback_max - callback_min,
        .type = FBR34KER_HANDOFF_REGION_RESERVED,
        .attributes = FBR34KER_REGION_ATTR_READ | FBR34KER_REGION_ATTR_EXECUTE,
    };
    const fbr34ker_handoff_region_t arena_region = {
        .base = (u64)(usize)&v4_arena, .size = sizeof(v4_arena),
        .type = FBR34KER_HANDOFF_REGION_MONITOR,
        .attributes = FBR34KER_REGION_ATTR_READ | FBR34KER_REGION_ATTR_WRITE |
                      FBR34KER_REGION_ATTR_EXECUTE,
    };
    if (code_region.base < arena_region.base) {
        v4_arena.regions[0] = code_region; v4_arena.regions[1] = arena_region;
    } else {
        v4_arena.regions[0] = arena_region; v4_arena.regions[1] = code_region;
    }
    v4_arena.services = (fbr34ker_platform_services_t){
        .version = FBR34KER_PLATFORM_SERVICES_VERSION_1,
        .structure_size = sizeof(fbr34ker_platform_services_t),
        .capabilities = FBR34KER_SERVICE_CONSOLE_WRITE |
                        FBR34KER_SERVICE_CONSOLE_READ |
                        FBR34KER_SERVICE_CONSOLE_FLUSH |
                        FBR34KER_SERVICE_INTERRUPT_CONTROLLER |
                        FBR34KER_SERVICE_WATCHDOG_CONFIGURE |
                        FBR34KER_SERVICE_WATCHDOG_KICK,
        .console_write = write_stub,
        .console_read = read_stub,
        .console_flush = flush_stub,
        .interrupt_ack = irq_ack_stub,
        .interrupt_complete = irq_complete_stub,
        .interrupt_set_enabled = irq_enabled_stub,
        .watchdog_configure = watchdog_configure_stub,
        .watchdog_kick = watchdog_kick_stub,
    };

    fbr34ker_handoff_t handoff;
    fm_memset(&handoff, 0, sizeof(handoff));
    handoff.magic = FBR34KER_HANDOFF_MAGIC;
    handoff.version = FBR34KER_HANDOFF_VERSION_4;
    handoff.structure_size = sizeof(handoff);
    handoff.monitor_base = (u64)(usize)&v4_arena;
    handoff.monitor_size = sizeof(v4_arena);
    handoff.memory_regions = v4_arena.regions;
    handoff.memory_region_count = ARRAY_COUNT(v4_arena.regions);
    handoff.flags = FBR34KER_HANDOFF_FLAG_PLATFORM_SERVICES_VALID |
                    FBR34KER_HANDOFF_FLAG_MODULE_POLICY_VALID;
    handoff.platform_services = &v4_arena.services;
    handoff.platform_services_size = sizeof(v4_arena.services);
    handoff.entry_exception_level = 1U;
    handoff.page_granule = FBR34KER_PAGE_GRANULE_4K;
    handoff.boot_cpu_id = 0U;
    handoff.module_capability_allow_mask = 0x0fU;
    handoff.module_slot_limit = 2U;
    handoff.module_instruction_budget_limit = 1024U;
    return handoff;
}

int main(void)
{
    fbr34ker_handoff_t handoff = valid_v3();
    if (!fbr34ker_handoff_valid(&handoff) ||
        !fbr34ker_handoff_covers_range(&handoff, 0x80001000ULL, 0x1000ULL) ||
        fbr34ker_handoff_covers_range(&handoff, 0x7ffff000ULL, 0x2000ULL)) {
        return 1;
    }

    handoff.flags &= ~FBR34KER_HANDOFF_FLAG_TIMER_VALID;
    if (fbr34ker_handoff_valid(&handoff)) return 2;
    handoff = valid_v3();
    test_regions[0].size = 0U;
    if (fbr34ker_handoff_valid(&handoff)) return 3;
    handoff = valid_v3();
    handoff.flags |= (1ULL << 63U);
    if (fbr34ker_handoff_valid(&handoff)) return 4;
    handoff = valid_v3();
    handoff.monitor_base = U64_MAX_VALUE - 10U;
    handoff.monitor_size = 100U;
    if (fbr34ker_handoff_valid(&handoff)) return 5;

    handoff = valid_v4();
    if (!fbr34ker_handoff_valid(&handoff) ||
        !fbr34ker_handoff_describes_range(
            &handoff, (u64)(usize)&v4_arena.services,
            sizeof(v4_arena.services),
            1U << FBR34KER_HANDOFF_REGION_MONITOR,
            FBR34KER_REGION_ATTR_READ)) {
        return 6;
    }
    handoff.page_granule = 8192U;
    if (fbr34ker_handoff_valid(&handoff)) return 7;
    handoff = valid_v4();
    v4_arena.services.interrupt_complete = NULL;
    if (fbr34ker_handoff_valid(&handoff)) return 8;
    handoff = valid_v4();
    handoff.module_capability_allow_mask = 1U << 31U;
    if (fbr34ker_handoff_valid(&handoff)) return 9;
    handoff = valid_v4();
    v4_arena.regions[0].attributes &= ~FBR34KER_REGION_ATTR_EXECUTE;
    if (fbr34ker_handoff_valid(&handoff)) return 10;

    /* A v4 loader may use the legacy-compatible runtime input field without
       also installing a legacy early character output callback. */
    handoff = valid_v4();
    handoff.runtime_getc = getc_stub;
    handoff.flags |= FBR34KER_HANDOFF_FLAG_RUNTIME_IO_VALID;
    if (!fbr34ker_handoff_valid(&handoff)) return 11;

    /* The v4 service table itself is optional for a headless/timer-only port. */
    handoff = valid_v4();
    handoff.flags &= ~FBR34KER_HANDOFF_FLAG_PLATFORM_SERVICES_VALID;
    handoff.platform_services = NULL;
    handoff.platform_services_size = 0U;
    if (!fbr34ker_handoff_valid(&handoff)) return 12;
    return 0;
}
