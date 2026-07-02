#include "fbr34ker/watchdog.h"
#include "fbr34ker/platform.h"
#include "fbr34ker/string.h"
#include "fbr34ker/timer.h"

#define WATCHDOG_MIN_TIMEOUT_MS 100U
#define WATCHDOG_MAX_TIMEOUT_MS (10U * 60U * 1000U)

// SPDX-License-Identifier: BSD-2-Clause
static watchdog_status_t status;

void watchdog_init(void)
{
    fm_memset(&status, 0, sizeof(status));
    const u64 features = platform_features();
    status.configure_available =
        (features & PLATFORM_FEATURE_WATCHDOG_CONFIGURE) != 0U;
    status.kick_available =
        (features & PLATFORM_FEATURE_WATCHDOG_KICK) != 0U;
}

bool watchdog_arm(u64 timeout_ms)
{
    if (!status.configure_available || !status.kick_available ||
        timeout_ms < WATCHDOG_MIN_TIMEOUT_MS ||
        timeout_ms > WATCHDOG_MAX_TIMEOUT_MS ||
        !platform_watchdog_configure(timeout_ms)) {
        return false;
    }
    status.armed = true;
    status.timeout_ms = timeout_ms;
    return watchdog_kick();
}

bool watchdog_kick(void)
{
    if (!status.kick_available) {
        return false;
    }
    platform_watchdog_kick();
    status.last_kick_ms = timer_uptime_ms();
    ++status.kick_count;
    return true;
}


bool watchdog_disarm(void)
{
    if (!status.configure_available || !platform_watchdog_configure(0U)) {
        return false;
    }
    status.armed = false;
    status.timeout_ms = 0U;
    return true;
}

bool watchdog_self_test(void)
{
    if (!status.configure_available || !status.kick_available) {
        return false;
    }
    const bool armed = watchdog_arm(1000U);
    const bool kicked = armed && watchdog_kick();
    const bool disarmed = watchdog_disarm();
    return armed && kicked && disarmed;
}

void watchdog_service(void)
{
    if (!status.armed || status.timeout_ms == 0U) {
        return;
    }
    const u64 now = timer_uptime_ms();
    const u64 interval = status.timeout_ms / 3U;
    if (now - status.last_kick_ms >= (interval == 0U ? 1U : interval)) {
        (void)watchdog_kick();
    }
}

watchdog_status_t watchdog_status(void)
{
    return status;
}
