#pragma once
#include "fbr34ker/types.h"

typedef enum {
    HARDWARE_PROBE_FEATURE_INTERRUPTS = 0,
    HARDWARE_PROBE_FEATURE_FRAMEBUFFER = 1,
    HARDWARE_PROBE_FEATURE_WATCHDOG = 2,
    HARDWARE_PROBE_FEATURE_POWER = 3,
    HARDWARE_PROBE_FEATURE_KERNEL_PATCHING = 4,
    HARDWARE_PROBE_FEATURE_SECURE_BOOT_BYPASS = 5,
    HARDWARE_PROBE_FEATURE_PERSISTENCE = 6,
} hardware_probe_feature_t;

typedef enum {
    HARDWARE_COMPAT_PASS = 0,
    HARDWARE_COMPAT_PARTIAL = 1,
    HARDWARE_COMPAT_UNSUPPORTED = 2,
    HARDWARE_COMPAT_NOT_TESTED = 3,
    HARDWARE_COMPAT_LOCKED = 4,
    HARDWARE_COMPAT_FAIL = 5,
} hardware_compatibility_state_t;

typedef struct {
    bool active;
    bool immutable;
    bool handoff_reviewed;
    bool interrupts_validated;
    bool framebuffer_validated;
    bool watchdog_validated;
    bool power_validated;
    bool kernel_patching_validated;
    bool secure_boot_bypass_validated;
    bool persistence_validated;
} hardware_probe_status_t;

void hardware_probe_init(void);
hardware_probe_status_t hardware_probe_status(void);
bool hardware_probe_active(void);
bool hardware_probe_immutable(void);
bool hardware_probe_unlock(void);
bool hardware_probe_mark_reviewed(void);
bool hardware_probe_mark_validated(hardware_probe_feature_t feature,
                                   bool validated);
bool hardware_probe_modules_allowed(void);
bool hardware_probe_framebuffer_writes_allowed(void);
bool hardware_probe_interrupt_mutation_allowed(void);
bool hardware_probe_watchdog_mutation_allowed(void);
bool hardware_probe_power_actions_allowed(void);
bool hardware_probe_memory_map_valid(void);
const char *hardware_compatibility_state_name(hardware_compatibility_state_t state);
hardware_compatibility_state_t hardware_probe_handoff_state(void);
hardware_compatibility_state_t hardware_probe_console_output_state(void);
hardware_compatibility_state_t hardware_probe_console_input_state(void);
hardware_compatibility_state_t hardware_probe_timer_state(void);
hardware_compatibility_state_t hardware_probe_memory_state(void);
hardware_compatibility_state_t hardware_probe_device_tree_state(void);
hardware_compatibility_state_t hardware_probe_interrupt_state(void);
hardware_compatibility_state_t hardware_probe_watchdog_state(void);
hardware_compatibility_state_t hardware_probe_framebuffer_state(void);
hardware_compatibility_state_t hardware_probe_module_state(void);
hardware_compatibility_state_t hardware_probe_power_state(void);
bool hardware_probe_kernel_patching_allowed(void);
bool hardware_probe_secure_boot_bypass_allowed(void);
bool hardware_probe_persistence_allowed(void);
hardware_compatibility_state_t hardware_probe_kernel_patching_state(void);
hardware_compatibility_state_t hardware_probe_secure_boot_bypass_state(void);
hardware_compatibility_state_t hardware_probe_persistence_state(void);
