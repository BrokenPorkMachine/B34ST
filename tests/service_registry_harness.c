#include "fbr34ker/event.h"
#include "fbr34ker/fault.h"
#include "fbr34ker/service_registry.h"

// SPDX-License-Identifier: BSD-2-Clause
int main(void)
{
    fault_injection_init();
    event_bus_init();
    service_registry_init();
    if (service_registry_register("timer", "test", 2U, 4U,
                                  FBR34KER_SERVICE_DISCOVERED) < 0) return 1;
    if (service_registry_register("timer", "test", 2U, 4U,
                                  FBR34KER_SERVICE_DISCOVERED) >= 0) return 2;
    if (!service_registry_set_state("timer", FBR34KER_SERVICE_READY) ||
        !service_registry_service_compatible("timer", 2U, 4U) ||
        service_registry_service_compatible("timer", 3U, 4U) ||
        service_registry_service_compatible("timer", 2U, 8U)) return 3;
    fbr34ker_service_info_t information;
    if (!service_registry_find_compatible("timer", 1U, 4U, &information) ||
        information.transitions != 2U) return 4;
    service_registry_shutdown();
    return service_registry_ready() ? 5 : 0;
}
