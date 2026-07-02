#include "fbr34ker/bringup.h"
#include "fbr34ker/event.h"
#include "fbr34ker/handoff.h"
#include "fbr34ker/hardware_probe.h"
#include "fbr34ker/string.h"

// SPDX-License-Identifier: BSD-2-Clause
static bool restricted_mode;

static const char *const allowed_commands[] = {
    "help", "version", "info", "platform-info", "exception-level",
    "system-registers", "handoff", "handoff-info", "boot-modules",
    "bringup-status", "bringup-exit", "probe-status", "hardware-probe",
    "probe-validate", "compatibility", "uptime", "timer-frequency",
    "regions", "memory-map", "memory-check", "heap", "health", "log",
    "crash-show", "services", "service-health", "console-services", "platform-features",
    "console-test", "console-history", "console-transports", "timer-test",
    "irq-info", "irq-controller", "watchdog-info", "watchdog-services",
    "framebuffer-info", "display-info", "display-console", "dt-info",
    "device-tree-summary", "dt-node", "dt-find", "dt-property",
    "dt-compatible", "dt-reg", "dt-alias", "dt-stdout", "dt-cells",
    "dt-clock", "dt-interrupts", "dt-clocks", "module-policy",
    "architecture", "components", "service-registry", "drivers", "events",
    "trace", "trace-json", "fault-status", "crash-json", "board-info",
    "hardware-inventory", "board-json", "mmio-map", "physical-memory",
    "bringup-report", "bringup-json", "boot-evidence", "boot-evidence-json",
    "kernel-patches", "secure-boot-bypass", "persistence",
    "exploit-chain", "exploit-status"
};

void bringup_init(void)
{
    restricted_mode = fbr34ker_handoff_active() != NULL ||
                      hardware_probe_active();
    (void)event_bus_publish(FBR34KER_EVENT_BRINGUP_MODE, "bringup-init", restricted_mode ? 1U : 0U, hardware_probe_immutable() ? 1U : 0U);
}

bool bringup_restricted(void)
{
    return restricted_mode;
}

void bringup_enter(void)
{
    restricted_mode = true;
    (void)event_bus_publish(FBR34KER_EVENT_BRINGUP_MODE, "bringup-enter", 1U, 0U);
}

void bringup_exit(void)
{
    if (!hardware_probe_active() || hardware_probe_unlock()) {
        restricted_mode = false;
        (void)event_bus_publish(FBR34KER_EVENT_BRINGUP_MODE, "bringup-exit", 0U, 0U);
    }
}

bool bringup_command_allowed(const char *name)
{
    if (!restricted_mode) {
        return true;
    }
    if (name == NULL || *name == '\0') {
        return false;
    }
    for (usize index = 0U; index < ARRAY_COUNT(allowed_commands); ++index) {
        if (fm_strcmp(name, allowed_commands[index]) == 0) {
            return true;
        }
    }
    return false;
}

const char *bringup_mode_name(void)
{
    if (hardware_probe_immutable()) {
        return "physical-probe/read-only";
    }
    return restricted_mode ? "restricted" : "full";
}
