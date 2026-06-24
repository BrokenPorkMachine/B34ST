#pragma once
#include "fbr34ker/handoff.h"

#define FBR34KER_LOADER_EXAMPLE_MAX_REGIONS 16U
#define FBR34KER_LOADER_EXAMPLE_MAX_MODULES 4U

typedef void (*fbr34ker_monitor_entry_fn)(const fbr34ker_handoff_t *handoff);

typedef struct ALIGNED(16) {
    fbr34ker_handoff_t handoff;
    fbr34ker_handoff_region_t regions[FBR34KER_LOADER_EXAMPLE_MAX_REGIONS];
    fbr34ker_handoff_boot_module_t modules[FBR34KER_LOADER_EXAMPLE_MAX_MODULES];
    fbr34ker_platform_services_t services;
} fbr34ker_loader_workspace_t;

typedef struct {
    fbr34ker_monitor_entry_fn monitor_entry;
    u64 monitor_base;
    u64 monitor_size;

    const fbr34ker_handoff_region_t *regions;
    u32 region_count;
    const fbr34ker_handoff_boot_module_t *modules;
    u32 module_count;

    const void *device_tree;
    u64 device_tree_size;
    const fbr34ker_handoff_framebuffer_t *framebuffer;
    u64 framebuffer_size;
    u32 framebuffer_bytes_per_pixel;
    u32 framebuffer_rotation;

    const fbr34ker_platform_services_t *services;

    /* Version 3-compatible runtime callbacks retained by handoff v4. */
    fbr34ker_runtime_getc_fn runtime_getc;
    void *runtime_io_context;
    fbr34ker_timer_read_fn timer_read;
    fbr34ker_timer_read_fn timer_frequency;
    void *timer_context;
    fbr34ker_power_action_fn reboot;
    fbr34ker_power_action_fn halt;
    void *power_context;
    u32 entry_exception_level;
    u32 page_granule;
    u32 boot_cpu_id;
    u64 loader_identifier;
    u64 platform_identifier;
    u64 firmware_revision;

    bool module_policy_enabled;
    u32 module_capability_allow_mask;
    u16 module_slot_limit;
    u32 module_instruction_budget_limit;
} fbr34ker_loader_config_t;

bool fbr34ker_loader_prepare(fbr34ker_loader_workspace_t *workspace,
                             const fbr34ker_loader_config_t *config);
NORETURN void fbr34ker_loader_launch(fbr34ker_loader_workspace_t *workspace,
                                     const fbr34ker_loader_config_t *config);
