#pragma once
// SPDX-License-Identifier: BSD-2-Clause
#include "fbr34ker/types.h"

void timer_init(void);
u64 timer_ticks(void);
u64 timer_frequency(void);
u64 timer_uptime_ms(void);
