#include "fbr34ker/service_guard.h"
// SPDX-License-Identifier: BSD-2-Clause
int main(void)
{
    service_guard_init();
    if (!service_guard_begin(SERVICE_GUARD_CONSOLE_WRITE)) return 1;
    if (service_guard_begin(SERVICE_GUARD_CONSOLE_WRITE)) return 2;
    service_guard_end(SERVICE_GUARD_CONSOLE_WRITE, false);
    if (!service_guard_begin(SERVICE_GUARD_CONSOLE_WRITE)) return 3;
    service_guard_end(SERVICE_GUARD_CONSOLE_WRITE, false);
    if (service_guard_available(SERVICE_GUARD_CONSOLE_WRITE)) return 4;
    service_guard_status_t status = service_guard_status(SERVICE_GUARD_CONSOLE_WRITE);
    if (!status.disabled || status.failures < 3U || status.recursive_denials != 1U) return 5;
    return 0;
}
