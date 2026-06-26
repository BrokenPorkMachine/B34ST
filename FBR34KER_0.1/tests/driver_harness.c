#include "fbr34ker/driver.h"
#include "fbr34ker/event.h"
#include "fbr34ker/fault.h"
#include "fbr34ker/service_registry.h"

static bool ok(void) { return true; }

int main(void)
{
    static const fbr34ker_driver_descriptor_t root = {
        .name = "root", .owner = "test", .priority = 10U,
        .required_features = 1ULL, .provided_service = "root.service",
        .start = ok,
    };
    static const fbr34ker_driver_descriptor_t child = {
        .name = "child", .owner = "test", .priority = 20U,
        .required_features = 2ULL, .dependency_service = "root.service",
        .dependency_min_version = 2U, .dependency_features = 1ULL,
        .provided_service = "child.service", .start = ok,
    };
    fault_injection_init();
    event_bus_init();
    service_registry_init();
    driver_manager_init();
    if (service_registry_register("root.service", "test", 2U, 1U,
                                  FBR34KER_SERVICE_DISCOVERED) < 0 ||
        service_registry_register("child.service", "test", 1U, 2U,
                                  FBR34KER_SERVICE_DISCOVERED) < 0) return 1;
    if (!driver_register(&child) || !driver_register(&root) ||
        !driver_start_all(3U)) return 2;
    if (!service_registry_service_compatible("root.service", 2U, 1U) ||
        !service_registry_service_ready("child.service")) return 3;
    driver_manager_shutdown();
    if (driver_manager_ready()) return 4;
    return 0;
}
