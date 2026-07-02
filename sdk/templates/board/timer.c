#include "fbr34ker/timer.h"
// SPDX-License-Identifier: BSD-2-Clause
static u64 boot_ticks;
void timer_init(void) { boot_ticks = timer_ticks(); }
u64 timer_ticks(void) { u64 v; __asm__ volatile("mrs %0, cntpct_el0" : "=r"(v)); return v; }
u64 timer_frequency(void) { u64 v; __asm__ volatile("mrs %0, cntfrq_el0" : "=r"(v)); return v; }
u64 timer_uptime_ms(void) { u64 f=timer_frequency(), e=timer_ticks()-boot_ticks; return f ? (e*1000U)/f : 0U; }
