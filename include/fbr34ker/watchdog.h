#pragma once
// SPDX-License-Identifier: BSD-2-Clause
#include "fbr34ker/types.h"

typedef struct {
    bool configure_available;
    bool kick_available;
    bool armed;
    u64 timeout_ms;
    u64 kick_count;
    u64 last_kick_ms;
} watchdog_status_t;

void watchdog_init(void);
bool watchdog_arm(u64 timeout_ms);
bool watchdog_kick(void);
bool watchdog_disarm(void);
bool watchdog_self_test(void);
void watchdog_service(void);
watchdog_status_t watchdog_status(void);
