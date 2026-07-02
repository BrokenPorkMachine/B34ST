#include "fbr34ker/platform.h"
#include "fbr34ker/timer.h"
#include "fbr34ker/watchdog.h"

// SPDX-License-Identifier: BSD-2-Clause
static u64 configured_timeout;
static u64 configure_count;
static u64 kicks;
static u64 now_ms;

u64 platform_features(void)
{
    return PLATFORM_FEATURE_WATCHDOG_CONFIGURE |
           PLATFORM_FEATURE_WATCHDOG_KICK;
}

bool platform_watchdog_configure(u64 timeout_ms)
{
    configured_timeout = timeout_ms;
    ++configure_count;
    return timeout_ms <= 600000U;
}

void platform_watchdog_kick(void)
{
    ++kicks;
}

u64 timer_uptime_ms(void)
{
    return now_ms;
}

int main(void)
{
    watchdog_init();
    watchdog_status_t status = watchdog_status();
    if (!status.configure_available || !status.kick_available || status.armed) return 1;
    now_ms = 10U;
    if (!watchdog_arm(1000U) || configured_timeout != 1000U || kicks != 1U) return 2;
    status = watchdog_status();
    if (!status.armed || status.timeout_ms != 1000U || status.kick_count != 1U) return 3;
    now_ms = 400U;
    watchdog_service();
    if (kicks != 2U) return 4;
    if (!watchdog_disarm() || configured_timeout != 0U) return 5;
    if (watchdog_status().armed) return 6;
    const u64 before = configure_count;
    if (!watchdog_self_test() || configure_count != before + 2U || configured_timeout != 0U) return 7;
    return 0;
}
