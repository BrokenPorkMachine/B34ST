#include "fbr34ker/service_registry.h"
#include "fbr34ker/event.h"
#include "fbr34ker/fault.h"
#include "fbr34ker/string.h"

static fbr34ker_service_info_t services[FBR34KER_SERVICE_CAPACITY];
static usize service_count;
static bool initialized;

void service_registry_init(void)
{
    fm_memset(services, 0, sizeof(services));
    service_count = 0U;
    initialized = true;
}

void service_registry_shutdown(void)
{
    initialized = false;
}

bool service_registry_ready(void)
{
    return initialized;
}

static isize find_index(const char *name)
{
    if (name == NULL) {
        return -1;
    }
    for (usize index = 0U; index < service_count; ++index) {
        if (fm_strcmp(services[index].name, name) == 0) {
            return (isize)index;
        }
    }
    return -1;
}

int service_registry_register(const char *name, const char *owner, u32 version,
                              u64 feature, fbr34ker_service_state_t initial)
{
    if (!initialized || name == NULL || owner == NULL || *name == '\0' ||
        *owner == '\0' || version == 0U || initial > FBR34KER_SERVICE_DISABLED ||
        service_count >= ARRAY_COUNT(services) || find_index(name) >= 0 ||
        fault_injection_should_fail(FBR34KER_FAULT_SERVICE_REGISTER, name)) {
        return -1;
    }
    fbr34ker_service_info_t *service = &services[service_count];
    fm_memset(service, 0, sizeof(*service));
    fm_strlcpy(service->name, name, sizeof(service->name));
    fm_strlcpy(service->owner, owner, sizeof(service->owner));
    service->version = version;
    service->state = initial;
    service->platform_feature = feature;
    service->transitions = 1U;
    const int identifier = (int)service_count++;
    (void)event_bus_publish(FBR34KER_EVENT_SERVICE_STATE, service->name,
                            initial, service->transitions);
    return identifier;
}

bool service_registry_set_state(const char *name, fbr34ker_service_state_t state)
{
    const isize index = find_index(name);
    if (!initialized || index < 0 || state > FBR34KER_SERVICE_DISABLED) {
        return false;
    }
    fbr34ker_service_info_t *service = &services[(usize)index];
    if (service->state == state) {
        return true;
    }
    service->state = state;
    ++service->transitions;
    (void)event_bus_publish(FBR34KER_EVENT_SERVICE_STATE, service->name,
                            state, service->transitions);
    return true;
}

bool service_registry_find(const char *name, fbr34ker_service_info_t *information)
{
    const isize index = find_index(name);
    if (information == NULL || index < 0) {
        return false;
    }
    *information = services[(usize)index];
    return true;
}

bool service_registry_find_compatible(const char *name, u32 minimum_version,
                                      u64 required_features,
                                      fbr34ker_service_info_t *information)
{
    fbr34ker_service_info_t service;
    if (!service_registry_find(name, &service) ||
        service.version < minimum_version ||
        (required_features & ~service.platform_feature) != 0U ||
        service.state != FBR34KER_SERVICE_READY) {
        return false;
    }
    if (information != NULL) {
        *information = service;
    }
    return true;
}

u64 service_registry_count(void)
{
    return (u64)service_count;
}

bool service_registry_at(u64 index, fbr34ker_service_info_t *information)
{
    if (information == NULL || index >= service_count) {
        return false;
    }
    *information = services[(usize)index];
    return true;
}

bool service_registry_service_ready(const char *name)
{
    return service_registry_service_compatible(name, 1U, 0U);
}

bool service_registry_service_compatible(const char *name, u32 minimum_version,
                                         u64 required_features)
{
    return service_registry_find_compatible(name, minimum_version,
                                            required_features, NULL);
}

bool service_registry_healthy(void)
{
    if (!initialized) {
        return false;
    }
    for (usize index = 0U; index < service_count; ++index) {
        if (services[index].state == FBR34KER_SERVICE_FAILED) {
            return false;
        }
    }
    return true;
}

const char *service_state_name(fbr34ker_service_state_t state)
{
    switch (state) {
    case FBR34KER_SERVICE_ABSENT: return "absent";
    case FBR34KER_SERVICE_DISCOVERED: return "discovered";
    case FBR34KER_SERVICE_READY: return "ready";
    case FBR34KER_SERVICE_DEGRADED: return "degraded";
    case FBR34KER_SERVICE_FAILED: return "failed";
    case FBR34KER_SERVICE_DISABLED: return "disabled";
    default: return "unknown";
    }
}
