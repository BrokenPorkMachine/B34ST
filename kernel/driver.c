#include "fbr34ker/driver.h"
#include "fbr34ker/event.h"
#include "fbr34ker/fault.h"
#include "fbr34ker/service_registry.h"
#include "fbr34ker/string.h"

typedef struct {
    const fbr34ker_driver_descriptor_t *descriptor;
    fbr34ker_driver_info_t information;
} driver_entry_t;

static driver_entry_t drivers[FBR34KER_DRIVER_CAPACITY];
static usize driver_total;
static bool initialized;
static u64 active_features;

void driver_manager_init(void)
{
    fm_memset(drivers, 0, sizeof(drivers));
    driver_total = 0U;
    active_features = 0U;
    initialized = true;
}

void driver_manager_shutdown(void)
{
    driver_stop_all();
    initialized = false;
}

bool driver_manager_ready(void)
{
    return initialized;
}

static void set_state(driver_entry_t *entry, fbr34ker_driver_state_t state)
{
    if (entry->information.state == state) {
        return;
    }
    entry->information.state = state;
    ++entry->information.transitions;
    (void)event_bus_publish(FBR34KER_EVENT_DRIVER_STATE,
                            entry->information.name, state,
                            entry->information.transitions);
}

bool driver_register(const fbr34ker_driver_descriptor_t *descriptor)
{
    if (!initialized || descriptor == NULL || descriptor->name == NULL ||
        descriptor->owner == NULL || *descriptor->name == '\0' ||
        *descriptor->owner == '\0' || driver_total >= ARRAY_COUNT(drivers)) {
        return false;
    }
    for (usize index = 0U; index < driver_total; ++index) {
        if (fm_strcmp(drivers[index].information.name, descriptor->name) == 0) {
            return false;
        }
    }
    driver_entry_t *entry = &drivers[driver_total++];
    entry->descriptor = descriptor;
    fm_strlcpy(entry->information.name, descriptor->name,
               sizeof(entry->information.name));
    fm_strlcpy(entry->information.owner, descriptor->owner,
               sizeof(entry->information.owner));
    if (descriptor->dependency_service != NULL) {
        fm_strlcpy(entry->information.dependency_service,
                   descriptor->dependency_service,
                   sizeof(entry->information.dependency_service));
    }
    if (descriptor->provided_service != NULL) {
        fm_strlcpy(entry->information.provided_service,
                   descriptor->provided_service,
                   sizeof(entry->information.provided_service));
    }
    entry->information.priority = descriptor->priority;
    entry->information.required_features = descriptor->required_features;
    entry->information.dependency_min_version = descriptor->dependency_min_version;
    entry->information.dependency_features = descriptor->dependency_features;
    entry->information.state = FBR34KER_DRIVER_REGISTERED;
    entry->information.transitions = 1U;
    (void)event_bus_publish(FBR34KER_EVENT_DRIVER_STATE,
                            entry->information.name,
                            FBR34KER_DRIVER_REGISTERED, 1U);
    return true;
}

static bool dependency_ready(const driver_entry_t *entry)
{
    const char *dependency = entry->descriptor->dependency_service;
    if (dependency == NULL || *dependency == '\0') {
        return true;
    }
    const u32 version = entry->descriptor->dependency_min_version == 0U
        ? 1U : entry->descriptor->dependency_min_version;
    return service_registry_service_compatible(
        dependency, version, entry->descriptor->dependency_features);
}

static driver_entry_t *next_startable(u64 features)
{
    driver_entry_t *best = NULL;
    for (usize index = 0U; index < driver_total; ++index) {
        driver_entry_t *entry = &drivers[index];
        if (entry->information.state != FBR34KER_DRIVER_REGISTERED ||
            (entry->information.required_features & ~features) != 0U ||
            !dependency_ready(entry)) {
            continue;
        }
        if (best == NULL || entry->information.priority < best->information.priority) {
            best = entry;
        }
    }
    return best;
}

bool driver_start_all(u64 features)
{
    if (!initialized) {
        return false;
    }
    active_features = features;
    for (;;) {
        driver_entry_t *entry = next_startable(features);
        if (entry == NULL) {
            break;
        }
        set_state(entry, FBR34KER_DRIVER_MATCHED);
        const bool probe_failed = fault_injection_should_fail(
            FBR34KER_FAULT_DRIVER_PROBE, entry->information.name) ||
            (entry->descriptor->probe != NULL && !entry->descriptor->probe());
        if (probe_failed) {
            set_state(entry, FBR34KER_DRIVER_FAILED);
            if (entry->information.provided_service[0] != '\0') {
                (void)service_registry_set_state(
                    entry->information.provided_service, FBR34KER_SERVICE_FAILED);
            }
            continue;
        }
        set_state(entry, FBR34KER_DRIVER_PROBED);
        const bool start_failed = fault_injection_should_fail(
            FBR34KER_FAULT_DRIVER_START, entry->information.name) ||
            (entry->descriptor->start != NULL && !entry->descriptor->start());
        if (start_failed) {
            set_state(entry, FBR34KER_DRIVER_FAILED);
            if (entry->information.provided_service[0] != '\0') {
                (void)service_registry_set_state(
                    entry->information.provided_service, FBR34KER_SERVICE_FAILED);
            }
            continue;
        }
        set_state(entry, FBR34KER_DRIVER_ACTIVE);
        if (entry->information.provided_service[0] != '\0') {
            (void)service_registry_set_state(entry->information.provided_service,
                                             FBR34KER_SERVICE_READY);
        }
    }
    for (usize index = 0U; index < driver_total; ++index) {
        if (drivers[index].information.state == FBR34KER_DRIVER_REGISTERED) {
            set_state(&drivers[index], FBR34KER_DRIVER_BLOCKED);
        }
    }
    return driver_manager_healthy();
}

void driver_stop_all(void)
{
    if (!initialized) {
        return;
    }
    for (usize offset = driver_total; offset > 0U; --offset) {
        driver_entry_t *entry = &drivers[offset - 1U];
        if (entry->information.state != FBR34KER_DRIVER_ACTIVE) {
            continue;
        }
        if (entry->descriptor->stop != NULL) {
            entry->descriptor->stop();
        }
        set_state(entry, FBR34KER_DRIVER_STOPPED);
        if (entry->information.provided_service[0] != '\0') {
            (void)service_registry_set_state(entry->information.provided_service,
                                             FBR34KER_SERVICE_DISABLED);
        }
    }
}

u64 driver_count(void)
{
    return (u64)driver_total;
}

bool driver_at(u64 index, fbr34ker_driver_info_t *information)
{
    if (information == NULL || index >= driver_total) {
        return false;
    }
    *information = drivers[(usize)index].information;
    return true;
}

bool driver_manager_healthy(void)
{
    if (!initialized) {
        return false;
    }
    for (usize index = 0U; index < driver_total; ++index) {
        const fbr34ker_driver_info_t *information = &drivers[index].information;
        if (information->state == FBR34KER_DRIVER_FAILED) {
            return false;
        }
        if (information->state == FBR34KER_DRIVER_BLOCKED &&
            (information->required_features & ~active_features) == 0U) {
            return false;
        }
    }
    return true;
}

const char *driver_state_name(fbr34ker_driver_state_t state)
{
    switch (state) {
    case FBR34KER_DRIVER_REGISTERED: return "registered";
    case FBR34KER_DRIVER_MATCHED: return "matched";
    case FBR34KER_DRIVER_PROBED: return "probed";
    case FBR34KER_DRIVER_ACTIVE: return "active";
    case FBR34KER_DRIVER_BLOCKED: return "blocked";
    case FBR34KER_DRIVER_FAILED: return "failed";
    case FBR34KER_DRIVER_STOPPED: return "stopped";
    default: return "unknown";
    }
}
