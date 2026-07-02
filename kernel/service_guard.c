#include "fbr34ker/service_guard.h"
#include "fbr34ker/string.h"

#define FAILURE_LIMIT 3U

// SPDX-License-Identifier: BSD-2-Clause
typedef struct {
    service_guard_status_t public;
    u64 start_ticks;
    u32 budget_ms;
} guard_slot_t;

static guard_slot_t slots[SERVICE_GUARD_COUNT];
static const u32 budgets_ms[SERVICE_GUARD_COUNT] = {
    50U, 10U, 50U, 100U, 5U, 5U, 10U, 20U, 10U, 10U, 10U, 10U, 1000U, 1000U
};
static const char *const names[SERVICE_GUARD_COUNT] = {
    "console-write", "console-read", "console-flush", "framebuffer-flush",
    "interrupt-ack", "interrupt-complete", "interrupt-enable",
    "watchdog-configure", "watchdog-kick", "runtime-input", "timer-read",
    "timer-frequency", "reboot", "halt"
};

static u64 counter_read(void)
{
#if defined(__aarch64__)
    u64 value;
    __asm__ volatile("mrs %0, cntpct_el0" : "=r"(value));
    return value;
#else
    static u64 synthetic;
    return ++synthetic;
#endif
}

static u64 counter_frequency(void)
{
#if defined(__aarch64__)
    u64 value;
    __asm__ volatile("mrs %0, cntfrq_el0" : "=r"(value));
    return value;
#else
    return 1000U;
#endif
}

void service_guard_init(void)
{
    fm_memset(slots, 0, sizeof(slots));
    for (u32 index = 0U; index < SERVICE_GUARD_COUNT; ++index) {
        slots[index].budget_ms = budgets_ms[index];
    }
}

bool service_guard_begin(service_guard_id_t id)
{
    if ((u32)id >= SERVICE_GUARD_COUNT || slots[id].public.disabled) {
        return false;
    }
    if (slots[id].public.active) {
        ++slots[id].public.recursive_denials;
        ++slots[id].public.failures;
        ++slots[id].public.consecutive_failures;
        if (slots[id].public.consecutive_failures >= FAILURE_LIMIT) {
            slots[id].public.disabled = true;
        }
        return false;
    }
    slots[id].public.active = true;
    slots[id].start_ticks = counter_read();
    return true;
}

void service_guard_end(service_guard_id_t id, bool success)
{
    if ((u32)id >= SERVICE_GUARD_COUNT || !slots[id].public.active) {
        return;
    }
    const u64 end = counter_read();
    const u64 elapsed = end - slots[id].start_ticks;
    const u64 frequency = counter_frequency();
    slots[id].public.active = false;
    slots[id].public.last_duration_ticks = elapsed;
    ++slots[id].public.calls;
    bool overrun = false;
    if (frequency != 0U) {
        const u64 budget_ticks = (frequency / 1000U) * slots[id].budget_ms;
        overrun = budget_ticks != 0U && elapsed > budget_ticks;
    }
    if (overrun) {
        ++slots[id].public.overruns;
    }
    if (!success || overrun) {
        ++slots[id].public.failures;
        ++slots[id].public.consecutive_failures;
        if (slots[id].public.consecutive_failures >= FAILURE_LIMIT) {
            slots[id].public.disabled = true;
        }
    } else {
        slots[id].public.consecutive_failures = 0U;
    }
}

bool service_guard_available(service_guard_id_t id)
{
    return (u32)id < SERVICE_GUARD_COUNT && !slots[id].public.disabled;
}

service_guard_status_t service_guard_status(service_guard_id_t id)
{
    if ((u32)id >= SERVICE_GUARD_COUNT) {
        service_guard_status_t empty;
        fm_memset(&empty, 0, sizeof(empty));
        empty.disabled = true;
        return empty;
    }
    return slots[id].public;
}

const char *service_guard_name(service_guard_id_t id)
{
    return (u32)id < SERVICE_GUARD_COUNT ? names[id] : "unknown";
}
