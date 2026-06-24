#include "fbr34ker/driver.h"
#include "fbr34ker/event.h"
#include "fbr34ker/fault.h"
#include "fbr34ker/service_registry.h"
#include "fbr34ker/trace.h"

static bool start_ok(void) { return true; }

int main(void)
{
    trace_init();
    fault_injection_init();
    event_bus_init();

    if (!fault_injection_arm(FBR34KER_FAULT_EVENT_PUBLISH, "drop", 0U, 1U)) return 1;
    if (event_bus_publish(FBR34KER_EVENT_VALIDATION, "drop", 0U, 0U)) return 2;
    if (event_bus_stats().injected_failures != 1U) return 3;

    service_registry_init();
    if (!fault_injection_arm(FBR34KER_FAULT_SERVICE_REGISTER, "injected", 0U, 1U)) return 4;
    if (service_registry_register("injected", "test", 1U, 0U,
                                  FBR34KER_SERVICE_DISCOVERED) >= 0) return 5;
    for (u32 index = 0U; index < FBR34KER_SERVICE_CAPACITY; ++index) {
        char name[16] = "service-00";
        name[8] = (char)('0' + (index / 10U));
        name[9] = (char)('0' + (index % 10U));
        if (service_registry_register(name, "test", 1U, 0U,
                                      FBR34KER_SERVICE_DISCOVERED) < 0) return 6;
    }
    if (service_registry_register("overflow", "test", 1U, 0U,
                                  FBR34KER_SERVICE_DISCOVERED) >= 0) return 7;

    event_bus_init();
    service_registry_init();
    driver_manager_init();
    if (service_registry_register("cycle.a", "test", 1U, 1U,
                                  FBR34KER_SERVICE_DISCOVERED) < 0 ||
        service_registry_register("cycle.b", "test", 1U, 2U,
                                  FBR34KER_SERVICE_DISCOVERED) < 0) return 8;
    static const fbr34ker_driver_descriptor_t a = {
        .name = "cycle-a", .owner = "test", .priority = 10U,
        .required_features = 1U, .dependency_service = "cycle.b",
        .dependency_min_version = 1U, .provided_service = "cycle.a",
        .start = start_ok,
    };
    static const fbr34ker_driver_descriptor_t b = {
        .name = "cycle-b", .owner = "test", .priority = 20U,
        .required_features = 2U, .dependency_service = "cycle.a",
        .dependency_min_version = 1U, .provided_service = "cycle.b",
        .start = start_ok,
    };
    if (!driver_register(&a) || !driver_register(&b)) return 9;
    if (driver_start_all(3U) || driver_manager_healthy()) return 10;

    if (!fault_injection_arm(FBR34KER_FAULT_TIMEOUT, "validation", 0U, 1U)) return 11;
    if (!fault_injection_should_fail(FBR34KER_FAULT_TIMEOUT, "validation")) return 12;
    if (fault_injection_should_fail(FBR34KER_FAULT_TIMEOUT, "validation")) return 13;
    return 0;
}
