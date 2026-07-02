#include "fbr34ker/timer.h"

// SPDX-License-Identifier: BSD-2-Clause
static u64 boot_ticks;

void timer_init(void)
{
    boot_ticks = timer_ticks();
}

u64 timer_ticks(void)
{
    u64 value;
    __asm__ volatile("mrs %0, cntvct_el0" : "=r"(value));
    return value;
}

u64 timer_frequency(void)
{
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
