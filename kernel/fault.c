#include "fbr34ker/fault.h"
#include "fbr34ker/string.h"
#include "fbr34ker/trace.h"

static fbr34ker_fault_status_t status;
static bool initialized;

void fault_injection_init(void)
{
    if (initialized) {
        return;
    }
    fm_memset(&status, 0, sizeof(status));
    initialized = true;
}

void fault_injection_shutdown(void)
{
    status.enabled = false;
    initialized = false;
}

bool fault_injection_available(void)
{
#ifdef FBR34KER_ENABLE_FAULT_INJECTION
    return initialized;
#else
    return false;
#endif
}

bool fault_injection_arm(fbr34ker_fault_point_t point, const char *source,
                         u32 trigger_after, u32 count)
{
#ifndef FBR34KER_ENABLE_FAULT_INJECTION
    UNUSED(point); UNUSED(source); UNUSED(trigger_after); UNUSED(count);
    return false;
#else
    if (!initialized || point >= FBR34KER_FAULT_POINT_COUNT || count == 0U) {
        return false;
    }
    fm_memset(&status, 0, sizeof(status));
    status.enabled = true;
    status.point = point;
    status.trigger_after = trigger_after;
    status.remaining = count;
    if (source != NULL) {
        fm_strlcpy(status.source, source, sizeof(status.source));
    }
    (void)trace_emit(FBR34KER_TRACE_FAULT, 1U, 0, fault_point_name(point),
                     trigger_after, count);
    return true;
#endif
}

void fault_injection_disarm(void)
{
    status.enabled = false;
    status.remaining = 0U;
}

bool fault_injection_should_fail(fbr34ker_fault_point_t point, const char *source)
{
#ifndef FBR34KER_ENABLE_FAULT_INJECTION
    UNUSED(point); UNUSED(source);
    return false;
#else
    if (!initialized || !status.enabled || status.point != point) {
        return false;
    }
    if (status.source[0] != '\0' &&
        (source == NULL || fm_strcmp(status.source, source) != 0)) {
        return false;
    }
    ++status.checks;
    if (status.trigger_after > 0U) {
        --status.trigger_after;
        return false;
    }
    if (status.remaining == 0U) {
        status.enabled = false;
        return false;
    }
    --status.remaining;
    ++status.injections;
    if (status.remaining == 0U) {
        status.enabled = false;
    }
    (void)trace_emit(FBR34KER_TRACE_FAULT, 2U, -1,
                     source == NULL ? fault_point_name(point) : source,
                     point, status.injections);
    return true;
#endif
}

fbr34ker_fault_status_t fault_injection_status(void)
{
    return status;
}

const char *fault_point_name(fbr34ker_fault_point_t point)
{
    switch (point) {
    case FBR34KER_FAULT_COMPONENT_START: return "component-start";
    case FBR34KER_FAULT_DRIVER_PROBE: return "driver-probe";
    case FBR34KER_FAULT_DRIVER_START: return "driver-start";
    case FBR34KER_FAULT_SERVICE_REGISTER: return "service-register";
    case FBR34KER_FAULT_EVENT_PUBLISH: return "event-publish";
    case FBR34KER_FAULT_TIMEOUT: return "timeout";
    default: return "unknown";
    }
}

bool fault_point_parse(const char *name, fbr34ker_fault_point_t *point)
{
    if (name == NULL || point == NULL) {
        return false;
    }
    for (u32 value = 0U; value < (u32)FBR34KER_FAULT_POINT_COUNT; ++value) {
        if (fm_strcmp(name, fault_point_name((fbr34ker_fault_point_t)value)) == 0) {
            *point = (fbr34ker_fault_point_t)value;
            return true;
        }
    }
    return false;
}
