#include "fbr34ker/hardware_probe.h"
#include "fbr34ker/device_tree.h"
#include "fbr34ker/handoff.h"
#include "fbr34ker/platform.h"
#include "fbr34ker/timer.h"

static hardware_probe_status_t status;
static bool defensive_context;

static bool compiled_immutable(void)
{
#ifdef FBR34KER_PHYSICAL_PROBE_IMAGE
    return true;
#else
    return false;
#endif
}

void hardware_probe_init(void)
{
    const bool external_handoff = fbr34ker_handoff_active() != NULL;
    defensive_context = external_handoff || compiled_immutable();
    status = (hardware_probe_status_t){
        .active = defensive_context,
        .immutable = compiled_immutable(),
        .handoff_reviewed = false,
        .interrupts_validated = false,
        .framebuffer_validated = false,
        .watchdog_validated = false,
        .power_validated = false,
    };
}

hardware_probe_status_t hardware_probe_status(void)
{
    return status;
}

bool hardware_probe_active(void)
{
    return status.active;
}

bool hardware_probe_immutable(void)
{
    return status.immutable;
}

bool hardware_probe_unlock(void)
{
    if (status.immutable || !status.handoff_reviewed) {
        return false;
    }
    status.active = false;
    return true;
}

bool hardware_probe_mark_reviewed(void)
{
    status.handoff_reviewed = true;
    return true;
}

bool hardware_probe_mark_validated(hardware_probe_feature_t feature,
                                   bool validated)
{
    switch (feature) {
    case HARDWARE_PROBE_FEATURE_INTERRUPTS:
        status.interrupts_validated = validated;
        return true;
    case HARDWARE_PROBE_FEATURE_FRAMEBUFFER:
        status.framebuffer_validated = validated;
        return true;
    case HARDWARE_PROBE_FEATURE_WATCHDOG:
        status.watchdog_validated = validated;
        return true;
    case HARDWARE_PROBE_FEATURE_POWER:
        status.power_validated = validated;
        return true;
    default:
        return false;
    }
}

bool hardware_probe_modules_allowed(void)
{
    return !compiled_immutable() && (!defensive_context || !status.active);
}

bool hardware_probe_framebuffer_writes_allowed(void)
{
    return !compiled_immutable() && (!defensive_context ||
        (!status.active && status.framebuffer_validated));
}

bool hardware_probe_interrupt_mutation_allowed(void)
{
    return !compiled_immutable() && (!defensive_context ||
        (!status.active && status.interrupts_validated));
}

bool hardware_probe_watchdog_mutation_allowed(void)
{
    return !compiled_immutable() && (!defensive_context ||
        (!status.active && status.watchdog_validated));
}

bool hardware_probe_power_actions_allowed(void)
{
    return !compiled_immutable() && (!defensive_context ||
        (!status.active && status.power_validated));
}

bool hardware_probe_memory_map_valid(void)
{
    const memory_region_t *regions = NULL;
    const u64 count = platform_memory_regions(&regions);
    if (count == 0U || regions == NULL) {
        return false;
    }
    u64 previous_end = 0U;
    bool monitor_seen = false;
    for (u64 index = 0U; index < count; ++index) {
        const memory_region_t *region = &regions[index];
        u64 end;
        if (region->size == 0U || !u64_add_checked(region->base, region->size, &end) ||
            end <= region->base || (index != 0U && region->base < previous_end)) {
            return false;
        }
        if (region->type < MEMORY_REGION_USABLE ||
            region->type > MEMORY_REGION_FRAMEBUFFER) {
            return false;
        }
        if (region->type == MEMORY_REGION_MONITOR) {
            monitor_seen = true;
        }
        previous_end = end;
    }
    return monitor_seen;
}

const char *hardware_compatibility_state_name(hardware_compatibility_state_t state)
{
    switch (state) {
    case HARDWARE_COMPAT_PASS: return "PASS";
    case HARDWARE_COMPAT_PARTIAL: return "PARTIAL";
    case HARDWARE_COMPAT_UNSUPPORTED: return "UNSUPPORTED";
    case HARDWARE_COMPAT_NOT_TESTED: return "NOT TESTED";
    case HARDWARE_COMPAT_LOCKED: return "LOCKED";
    case HARDWARE_COMPAT_FAIL: return "FAIL";
    default: return "UNKNOWN";
    }
}

hardware_compatibility_state_t hardware_probe_handoff_state(void)
{
    if (fbr34ker_handoff_active() == NULL) {
        return status.immutable ? HARDWARE_COMPAT_FAIL : HARDWARE_COMPAT_NOT_TESTED;
    }
    return HARDWARE_COMPAT_PASS;
}

hardware_compatibility_state_t hardware_probe_console_output_state(void)
{
    return (platform_features() & PLATFORM_FEATURE_CONSOLE_OUTPUT) != 0U
        ? HARDWARE_COMPAT_PASS : HARDWARE_COMPAT_PARTIAL;
}

hardware_compatibility_state_t hardware_probe_console_input_state(void)
{
    return (platform_features() & PLATFORM_FEATURE_CONSOLE_INPUT) != 0U
        ? HARDWARE_COMPAT_PASS : HARDWARE_COMPAT_UNSUPPORTED;
}

hardware_compatibility_state_t hardware_probe_timer_state(void)
{
    return timer_frequency() != 0U ? HARDWARE_COMPAT_PASS : HARDWARE_COMPAT_FAIL;
}

hardware_compatibility_state_t hardware_probe_memory_state(void)
{
    return hardware_probe_memory_map_valid() ? HARDWARE_COMPAT_PASS
                                             : HARDWARE_COMPAT_FAIL;
}

hardware_compatibility_state_t hardware_probe_device_tree_state(void)
{
    return device_tree_valid() ? HARDWARE_COMPAT_PASS : HARDWARE_COMPAT_PARTIAL;
}

hardware_compatibility_state_t hardware_probe_interrupt_state(void)
{
    if ((platform_features() & PLATFORM_FEATURE_INTERRUPTS) == 0U) {
        return HARDWARE_COMPAT_UNSUPPORTED;
    }
    return status.interrupts_validated ? HARDWARE_COMPAT_PASS
                                       : HARDWARE_COMPAT_NOT_TESTED;
}

hardware_compatibility_state_t hardware_probe_watchdog_state(void)
{
    const u64 required = PLATFORM_FEATURE_WATCHDOG_CONFIGURE |
                         PLATFORM_FEATURE_WATCHDOG_KICK;
    if ((platform_features() & required) != required) {
        return HARDWARE_COMPAT_UNSUPPORTED;
    }
    return status.watchdog_validated ? HARDWARE_COMPAT_PASS
                                     : HARDWARE_COMPAT_NOT_TESTED;
}

hardware_compatibility_state_t hardware_probe_framebuffer_state(void)
{
    if ((platform_features() & PLATFORM_FEATURE_FRAMEBUFFER) == 0U) {
        return HARDWARE_COMPAT_UNSUPPORTED;
    }
    if (status.active || !status.framebuffer_validated) {
        return HARDWARE_COMPAT_LOCKED;
    }
    return HARDWARE_COMPAT_PASS;
}

hardware_compatibility_state_t hardware_probe_module_state(void)
{
    return hardware_probe_modules_allowed() ? HARDWARE_COMPAT_PASS
                                            : HARDWARE_COMPAT_LOCKED;
}

hardware_compatibility_state_t hardware_probe_power_state(void)
{
    if ((platform_features() & PLATFORM_FEATURE_POWER) == 0U) {
        return HARDWARE_COMPAT_UNSUPPORTED;
    }
    if (status.active || !status.power_validated) {
        return HARDWARE_COMPAT_LOCKED;
    }
    return HARDWARE_COMPAT_PASS;
}
