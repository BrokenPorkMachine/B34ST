#include "fbr34ker/architecture.h"
#include "fbr34ker/board.h"
#include "fbr34ker/bringup_report.h"
#include "fbr34ker/driver.h"
#include "fbr34ker/event.h"
#include "fbr34ker/fault.h"
#include "fbr34ker/hardware_probe.h"
#include "fbr34ker/log.h"
#include "fbr34ker/lifecycle.h"
#include "fbr34ker/mmio.h"
#include "fbr34ker/mmu.h"
#include "fbr34ker/physical_memory.h"
#include "fbr34ker/platform.h"
#include "fbr34ker/service_registry.h"
#include "fbr34ker/trace.h"

// SPDX-License-Identifier: BSD-2-Clause
static bool ready;

static bool start_trace(void)
{
    trace_init();
    return trace_ready();
}

static void stop_trace(void)
{
    trace_shutdown();
}

static fbr34ker_trace_category_t trace_category_for_event(fbr34ker_event_type_t type)
{
    switch (type) {
    case FBR34KER_EVENT_SERVICE_STATE: return FBR34KER_TRACE_SERVICE;
    case FBR34KER_EVENT_DRIVER_STATE: return FBR34KER_TRACE_DRIVER;
    case FBR34KER_EVENT_COMPONENT_STATE:
    case FBR34KER_EVENT_ROLLBACK: return FBR34KER_TRACE_LIFECYCLE;
    case FBR34KER_EVENT_VALIDATION: return FBR34KER_TRACE_VALIDATION;
    case FBR34KER_EVENT_BOOT:
    case FBR34KER_EVENT_BRINGUP_MODE:
    case FBR34KER_EVENT_MODULE_LOADED:
    case FBR34KER_EVENT_MODULE_EXECUTED:
    case FBR34KER_EVENT_MODULE_UNLOADED:
    case FBR34KER_EVENT_KERNEL_PATCH:
    case FBR34KER_EVENT_SECURE_BOOT_BYPASS:
    case FBR34KER_EVENT_PERSISTENCE:
    case FBR34KER_EVENT_EXPLOIT_CHAIN:
    case FBR34KER_EVENT_COUNT:
        return FBR34KER_TRACE_BOOT;
    }
    return FBR34KER_TRACE_BOOT;
}

static void trace_event(const fbr34ker_event_t *event, void *context)
{
    UNUSED(context);
    if (event == NULL) {
        return;
    }
    (void)trace_emit(trace_category_for_event(event->type), (u32)event->type, 0,
                     event->source, event->value0, event->value1);
}


static bool start_board_description(void)
{
    return board_init();
}

static void stop_board_description(void)
{
    board_shutdown();
}

static bool start_mmio_manager(void)
{
    mmio_init(hardware_probe_immutable());
    const fbr34ker_board_descriptor_t *board = board_active();
    if (board == NULL) return false;
    for (u32 index = 0U; index < board->device_count; ++index) {
        const fbr34ker_board_device_t *device = &board->devices[index];
        if (device->size == 0U ||
            (device->flags & (FBR34KER_DEVICE_FLAG_MMIO_READ |
                              FBR34KER_DEVICE_FLAG_MMIO_WRITE)) == 0U) continue;
        u32 permissions = 0U;
        if ((device->flags & FBR34KER_DEVICE_FLAG_MMIO_READ) != 0U)
            permissions |= FBR34KER_MMIO_READ;
        if ((device->flags & FBR34KER_DEVICE_FLAG_MMIO_WRITE) != 0U)
            permissions |= FBR34KER_MMIO_WRITE;
        if ((device->flags & FBR34KER_DEVICE_FLAG_PROBE_SAFE) != 0U)
            permissions |= FBR34KER_MMIO_PROBE_SAFE;
        if (!mmio_register_window(device->name, device->base, device->size,
                                  permissions, 0x0fU)) return false;
    }
    return mmio_healthy();
}

static void stop_mmio_manager(void)
{
    mmio_shutdown();
}

static bool start_physical_memory(void)
{
    physical_memory_init();
    return physical_memory_healthy();
}

static void stop_physical_memory(void)
{
    physical_memory_shutdown();
}

static bool start_mmu(void)
{
    if (!mmu_init()) {
        return false;
    }
    u64 root_addr = 0x41000000ULL;
    usize pool_size = MMU_PAGE_SIZE * 32U;
    if (!mmu_allocate_page_table_pool(root_addr, pool_size)) {
        log_warn("mmu: page table pool allocation at 0x%llx failed, using fallback", root_addr);
        mmu_shutdown();
        return true;
    }
    u64 identity_start = 0x40000000ULL;
    u64 identity_size = 0x1000000000ULL;
    if (!mmu_setup_identity_map(identity_start, identity_size)) {
        log_warn("mmu: identity map failed, MMU will not be enabled");
    }
    return true;
}

static void stop_mmu(void)
{
    mmu_shutdown();
}

static bool start_bringup_report(void)
{
    return bringup_report_run(false);
}

static void stop_bringup_report(void)
{
    bringup_report_init();
}

static bool start_event_bus(void)
{
    event_bus_init();
    const u64 all_events = (1ULL << (u32)FBR34KER_EVENT_COUNT) - 1ULL;
    return event_bus_ready() && event_bus_subscribe(all_events, trace_event, NULL);
}

static void stop_event_bus(void)
{
    event_bus_shutdown();
}

static bool start_service_registry(void)
{
    service_registry_init();
    return service_registry_ready();
}

static void stop_service_registry(void)
{
    service_registry_shutdown();
}

static bool start_driver_manager(void)
{
    driver_manager_init();
    return driver_manager_ready();
}

static void stop_driver_manager(void)
{
    driver_manager_shutdown();
}

static bool always_start(void)
{
    return true;
}

static const struct service_contract {
    const char *name;
    u32 version;
    u64 feature;
} service_contracts[] = {
    {"console.output", 1U, PLATFORM_FEATURE_CONSOLE_OUTPUT},
    {"console.input", 1U, PLATFORM_FEATURE_CONSOLE_INPUT},
    {"timer.monotonic", 1U, PLATFORM_FEATURE_TIMER},
    {"interrupt.controller", 1U, PLATFORM_FEATURE_INTERRUPTS},
    {"display.framebuffer", 1U, PLATFORM_FEATURE_FRAMEBUFFER},
    {"watchdog", 1U, PLATFORM_FEATURE_WATCHDOG_CONFIGURE},
    {"power.control", 1U, PLATFORM_FEATURE_POWER},
    {"console.semihosting", 1U, PLATFORM_FEATURE_SEMIHOSTING},
};

static const fbr34ker_driver_descriptor_t platform_drivers[] = {
    {
        .name = "console-output", .owner = "platform", .priority = 10U,
        .required_features = PLATFORM_FEATURE_CONSOLE_OUTPUT,
        .provided_service = "console.output", .start = always_start,
    },
    {
        .name = "timer", .owner = "platform", .priority = 20U,
        .required_features = PLATFORM_FEATURE_TIMER,
        .provided_service = "timer.monotonic", .start = always_start,
    },
    {
        .name = "interrupt-controller", .owner = "platform", .priority = 30U,
        .required_features = PLATFORM_FEATURE_INTERRUPTS,
        .provided_service = "interrupt.controller", .start = always_start,
    },
    {
        .name = "console-input", .owner = "platform", .priority = 40U,
        .required_features = PLATFORM_FEATURE_CONSOLE_INPUT,
        .dependency_service = "console.output", .dependency_min_version = 1U,
        .dependency_features = PLATFORM_FEATURE_CONSOLE_OUTPUT,
        .provided_service = "console.input", .start = always_start,
    },
    {
        .name = "framebuffer", .owner = "platform", .priority = 50U,
        .required_features = PLATFORM_FEATURE_FRAMEBUFFER,
        .provided_service = "display.framebuffer", .start = always_start,
    },
    {
        .name = "watchdog", .owner = "platform", .priority = 60U,
        .required_features = PLATFORM_FEATURE_WATCHDOG_CONFIGURE,
        .dependency_service = "timer.monotonic", .dependency_min_version = 1U,
        .dependency_features = PLATFORM_FEATURE_TIMER,
        .provided_service = "watchdog", .start = always_start,
    },
    {
        .name = "power-control", .owner = "platform", .priority = 70U,
        .required_features = PLATFORM_FEATURE_POWER,
        .provided_service = "power.control", .start = always_start,
    },
    {
        .name = "semihosting-console", .owner = "platform", .priority = 80U,
        .required_features = PLATFORM_FEATURE_SEMIHOSTING,
        .dependency_service = "console.output", .dependency_min_version = 1U,
        .dependency_features = PLATFORM_FEATURE_CONSOLE_OUTPUT,
        .provided_service = "console.semihosting", .start = always_start,
    },
};

static bool service_mutation_locked(u64 feature)
{
    if (!hardware_probe_immutable()) {
        return false;
    }
    const u64 mutation = PLATFORM_FEATURE_FRAMEBUFFER |
                         PLATFORM_FEATURE_INTERRUPTS |
                         PLATFORM_FEATURE_WATCHDOG_CONFIGURE |
                         PLATFORM_FEATURE_WATCHDOG_KICK |
                         PLATFORM_FEATURE_POWER;
    return (feature & mutation) != 0U;
}

static bool start_platform_catalog(void)
{
    const u64 features = platform_features();
    u64 effective = features;
    if (hardware_probe_immutable()) {
        effective &= ~(PLATFORM_FEATURE_FRAMEBUFFER |
                       PLATFORM_FEATURE_INTERRUPTS |
                       PLATFORM_FEATURE_WATCHDOG_CONFIGURE |
                       PLATFORM_FEATURE_WATCHDOG_KICK |
                       PLATFORM_FEATURE_POWER);
    }
    for (usize index = 0U; index < ARRAY_COUNT(service_contracts); ++index) {
        fbr34ker_service_state_t initial = FBR34KER_SERVICE_ABSENT;
        if ((features & service_contracts[index].feature) != 0U) {
            initial = service_mutation_locked(service_contracts[index].feature)
                ? FBR34KER_SERVICE_DISABLED : FBR34KER_SERVICE_DISCOVERED;
        }
        if (service_registry_register(service_contracts[index].name, "platform",
                                      service_contracts[index].version,
                                      service_contracts[index].feature,
                                      initial) < 0) {
            return false;
        }
    }
    for (usize index = 0U; index < ARRAY_COUNT(platform_drivers); ++index) {
        if (!driver_register(&platform_drivers[index])) {
            return false;
        }
    }
    return driver_start_all(effective);
}

static void stop_platform_catalog(void)
{
    driver_stop_all();
}

static const fbr34ker_component_descriptor_t components[] = {
    {
        .name = "trace", .phase = FBR34KER_PHASE_EARLY,
        .provides = FBR34KER_ARCH_CAP_TRACE,
        .start = start_trace, .stop = stop_trace, .health = trace_ready,
    },
    {
        .name = "board-description", .phase = FBR34KER_PHASE_EARLY,
        .requires = FBR34KER_ARCH_CAP_TRACE,
        .provides = FBR34KER_ARCH_CAP_BOARD_DESCRIPTION,
        .start = start_board_description, .stop = stop_board_description,
        .health = board_healthy,
    },
    {
        .name = "event-bus", .phase = FBR34KER_PHASE_CORE,
        .requires = FBR34KER_ARCH_CAP_TRACE,
        .provides = FBR34KER_ARCH_CAP_EVENT_BUS,
        .start = start_event_bus, .stop = stop_event_bus,
        .health = event_bus_ready,
    },
    {
        .name = "mmio-manager", .phase = FBR34KER_PHASE_CORE,
        .requires = FBR34KER_ARCH_CAP_BOARD_DESCRIPTION,
        .provides = FBR34KER_ARCH_CAP_MMIO_MANAGER,
        .start = start_mmio_manager, .stop = stop_mmio_manager,
        .health = mmio_healthy,
    },
    {
        .name = "mmu", .phase = FBR34KER_PHASE_CORE,
        .requires = FBR34KER_ARCH_CAP_BOARD_DESCRIPTION | FBR34KER_ARCH_CAP_MMIO_MANAGER,
        .provides = FBR34KER_ARCH_CAP_MMU,
        .start = start_mmu, .stop = stop_mmu,
        .health = mmu_healthy,
    },
    {
        .name = "service-registry", .phase = FBR34KER_PHASE_CORE,
        .requires = FBR34KER_ARCH_CAP_TRACE | FBR34KER_ARCH_CAP_EVENT_BUS,
        .provides = FBR34KER_ARCH_CAP_SERVICE_REGISTRY,
        .start = start_service_registry, .stop = stop_service_registry,
        .health = service_registry_healthy,
    },
    {
        .name = "physical-memory", .phase = FBR34KER_PHASE_PLATFORM,
        .requires = FBR34KER_ARCH_CAP_BOARD_DESCRIPTION,
        .provides = FBR34KER_ARCH_CAP_PHYSICAL_MEMORY,
        .start = start_physical_memory, .stop = stop_physical_memory,
        .health = physical_memory_healthy,
    },
    {
        .name = "driver-manager", .phase = FBR34KER_PHASE_PLATFORM,
        .requires = FBR34KER_ARCH_CAP_EVENT_BUS |
                    FBR34KER_ARCH_CAP_SERVICE_REGISTRY,
        .provides = FBR34KER_ARCH_CAP_DRIVER_MANAGER,
        .start = start_driver_manager, .stop = stop_driver_manager,
        .health = driver_manager_healthy,
    },
    {
        .name = "platform-catalog", .phase = FBR34KER_PHASE_SERVICES,
        .requires = FBR34KER_ARCH_CAP_DRIVER_MANAGER |
                    FBR34KER_ARCH_CAP_SERVICE_REGISTRY,
        .provides = FBR34KER_ARCH_CAP_PLATFORM_CATALOG,
        .start = start_platform_catalog, .stop = stop_platform_catalog,
        .health = driver_manager_healthy,
    },
    {
        .name = "bringup-report", .phase = FBR34KER_PHASE_EXTENSIONS,
        .requires = FBR34KER_ARCH_CAP_BOARD_DESCRIPTION |
                    FBR34KER_ARCH_CAP_MMIO_MANAGER |
                    FBR34KER_ARCH_CAP_PHYSICAL_MEMORY |
                    FBR34KER_ARCH_CAP_PLATFORM_CATALOG,
        .provides = FBR34KER_ARCH_CAP_BRINGUP_REPORT,
        .start = start_bringup_report, .stop = stop_bringup_report,
        .health = physical_memory_healthy,
    },
};

bool architecture_init(void)
{
    ready = false;
    fault_injection_init();
    lifecycle_init();
    for (usize index = 0U; index < ARRAY_COUNT(components); ++index) {
        if (!lifecycle_register(&components[index])) {
            return false;
        }
    }
    ready = lifecycle_start();
    if (event_bus_ready()) {
        for (u64 index = 0U; index < lifecycle_component_count(); ++index) {
            fbr34ker_component_info_t information;
            if (lifecycle_component_info(index, &information)) {
                (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE,
                                        information.name, information.state,
                                        information.provides);
            }
        }
        (void)event_bus_publish(FBR34KER_EVENT_BOOT, "architecture",
                                ready ? 1U : 0U,
                                lifecycle_provided_capabilities());
    }
    return ready;
}

void architecture_shutdown(void)
{
    lifecycle_stop();
    ready = false;
}

bool architecture_restart(void)
{
    architecture_shutdown();
    return architecture_init();
}

bool architecture_ready(void)
{
    return ready;
}

bool architecture_healthy(void)
{
    return ready && lifecycle_healthy() && service_registry_healthy() &&
           driver_manager_healthy() && trace_ready() && board_healthy() &&
           mmio_healthy() && physical_memory_healthy();
}
