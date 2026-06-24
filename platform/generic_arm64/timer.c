#include "fbr34ker/timer.h"
#include "fbr34ker/handoff.h"
#include "fbr34ker/service_guard.h"

static u64 boot_ticks;

static const fbr34ker_handoff_t *active(void)
{
    const fbr34ker_handoff_t *handoff = fbr34ker_handoff_active();
    return handoff != NULL && handoff->version >= FBR34KER_HANDOFF_VERSION_3
        ? handoff : NULL;
}

void timer_init(void)
{
    boot_ticks = timer_ticks();
}

u64 timer_ticks(void)
{
    const fbr34ker_handoff_t *handoff = active();
    if (handoff != NULL &&
        (handoff->flags & FBR34KER_HANDOFF_FLAG_TIMER_VALID) != 0U &&
        handoff->timer_read != NULL && service_guard_begin(SERVICE_GUARD_TIMER_READ)) {
        const u64 value = handoff->timer_read(handoff->timer_context);
        service_guard_end(SERVICE_GUARD_TIMER_READ, true);
        return value;
    }
    u64 value;
    __asm__ volatile("mrs %0, cntpct_el0" : "=r"(value));
    return value;
}

u64 timer_frequency(void)
{
    const fbr34ker_handoff_t *handoff = active();
    if (handoff != NULL &&
        (handoff->flags & FBR34KER_HANDOFF_FLAG_TIMER_VALID) != 0U &&
        handoff->timer_frequency != NULL && service_guard_begin(SERVICE_GUARD_TIMER_FREQUENCY)) {
        const u64 value = handoff->timer_frequency(handoff->timer_context);
        service_guard_end(SERVICE_GUARD_TIMER_FREQUENCY, value != 0U);
        return value;
    }
    u64 value;
    __asm__ volatile("mrs %0, cntfrq_el0" : "=r"(value));
    return value;
}

u64 timer_uptime_ms(void)
{
    const u64 frequency = timer_frequency();
    const u64 elapsed = timer_ticks() - boot_ticks;
    if (frequency == 0U) {
        return 0U;
    }
    return ((elapsed / frequency) * 1000U) +
           (((elapsed % frequency) * 1000U) / frequency);
}
