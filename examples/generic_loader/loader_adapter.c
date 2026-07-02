#include "loader_adapter.h"
#include "fbr34ker/string.h"

// SPDX-License-Identifier: BSD-2-Clause
static bool range_valid(u64 base, u64 size)
{
    return size != 0U && base <= U64_MAX_VALUE - size;
}

static bool copy_regions(fbr34ker_loader_workspace_t *workspace,
                         const fbr34ker_loader_config_t *config)
{
    if (config->region_count == 0U ||
        config->region_count > FBR34KER_LOADER_EXAMPLE_MAX_REGIONS ||
        config->regions == NULL) {
        return false;
    }
    u64 previous_end = 0U;
    for (u32 index = 0U; index < config->region_count; ++index) {
        const fbr34ker_handoff_region_t *region = &config->regions[index];
        if (!range_valid(region->base, region->size) ||
            (index != 0U && region->base < previous_end)) {
            return false;
        }
        previous_end = region->base + region->size;
        workspace->regions[index] = *region;
    }
    return true;
}

static bool copy_modules(fbr34ker_loader_workspace_t *workspace,
                         const fbr34ker_loader_config_t *config)
{
    if (config->module_count > FBR34KER_LOADER_EXAMPLE_MAX_MODULES ||
        (config->module_count != 0U && config->modules == NULL)) {
        return false;
    }
    for (u32 index = 0U; index < config->module_count; ++index) {
        if (config->modules[index].base == NULL ||
            config->modules[index].size == 0U) {
            return false;
        }
        workspace->modules[index] = config->modules[index];
    }
    return true;
}

bool fbr34ker_loader_prepare(fbr34ker_loader_workspace_t *workspace,
                             const fbr34ker_loader_config_t *config)
{
    if (workspace == NULL || config == NULL || config->monitor_entry == NULL ||
        !range_valid(config->monitor_base, config->monitor_size) ||
        (config->services != NULL &&
         (config->services->version != FBR34KER_PLATFORM_SERVICES_VERSION_1 ||
          config->services->structure_size < sizeof(*config->services))) ||
        config->entry_exception_level < 1U ||
        config->entry_exception_level > 3U ||
        (config->page_granule != FBR34KER_PAGE_GRANULE_4K &&
         config->page_granule != FBR34KER_PAGE_GRANULE_16K &&
         config->page_granule != FBR34KER_PAGE_GRANULE_64K) ||
        !copy_regions(workspace, config) || !copy_modules(workspace, config)) {
        return false;
    }

    fm_memset(&workspace->handoff, 0, sizeof(workspace->handoff));
    fm_memset(&workspace->services, 0, sizeof(workspace->services));
    if (config->services != NULL) {
        workspace->services = *config->services;
    }
    fbr34ker_handoff_t *handoff = &workspace->handoff;
    handoff->magic = FBR34KER_HANDOFF_MAGIC;
    handoff->version = FBR34KER_HANDOFF_VERSION_4;
    handoff->structure_size = sizeof(*handoff);
    handoff->monitor_base = config->monitor_base;
    handoff->monitor_size = config->monitor_size;
    handoff->memory_regions = workspace->regions;
    handoff->memory_region_count = config->region_count;
    handoff->boot_modules = config->module_count != 0U ? workspace->modules : NULL;
    handoff->boot_module_count = config->module_count;
    handoff->loader_identifier = config->loader_identifier;
    handoff->platform_identifier = config->platform_identifier;
    handoff->firmware_revision = config->firmware_revision;
    handoff->entry_exception_level = config->entry_exception_level;
    handoff->page_granule = config->page_granule;
    handoff->boot_cpu_id = config->boot_cpu_id;
    handoff->flags = 0U;
    if (config->services != NULL) {
        handoff->platform_services = &workspace->services;
        handoff->platform_services_size = sizeof(workspace->services);
        handoff->flags |= FBR34KER_HANDOFF_FLAG_PLATFORM_SERVICES_VALID;
    }

    if (config->runtime_getc != NULL) {
        handoff->runtime_getc = config->runtime_getc;
        handoff->runtime_io_context = config->runtime_io_context;
        handoff->flags |= FBR34KER_HANDOFF_FLAG_RUNTIME_IO_VALID;
    }
    if (config->timer_read != NULL && config->timer_frequency != NULL) {
        handoff->timer_read = config->timer_read;
        handoff->timer_frequency = config->timer_frequency;
        handoff->timer_context = config->timer_context;
        handoff->flags |= FBR34KER_HANDOFF_FLAG_TIMER_VALID;
    }
    if (config->reboot != NULL && config->halt != NULL) {
        handoff->reboot = config->reboot;
        handoff->halt = config->halt;
        handoff->power_context = config->power_context;
        handoff->flags |= FBR34KER_HANDOFF_FLAG_POWER_VALID;
    }

    if (config->device_tree != NULL && config->device_tree_size != 0U) {
        handoff->device_tree = config->device_tree;
        handoff->device_tree_size = config->device_tree_size;
        handoff->flags |= FBR34KER_HANDOFF_FLAG_DEVICE_TREE_VALID;
    }
    if (config->framebuffer != NULL) {
        handoff->framebuffer = *config->framebuffer;
        handoff->framebuffer_size = config->framebuffer_size;
        handoff->framebuffer_bytes_per_pixel =
            config->framebuffer_bytes_per_pixel;
        handoff->framebuffer_rotation = config->framebuffer_rotation;
        handoff->flags |= FBR34KER_HANDOFF_FLAG_FRAMEBUFFER_VALID;
    }
    if (config->module_policy_enabled) {
        handoff->module_capability_allow_mask =
            config->module_capability_allow_mask;
        handoff->module_slot_limit = config->module_slot_limit;
        handoff->module_instruction_budget_limit =
            config->module_instruction_budget_limit;
        handoff->flags |= FBR34KER_HANDOFF_FLAG_MODULE_POLICY_VALID;
    }
    return true;
}

NORETURN void fbr34ker_loader_launch(fbr34ker_loader_workspace_t *workspace,
                                     const fbr34ker_loader_config_t *config)
{
    if (!fbr34ker_loader_prepare(workspace, config)) {
        for (;;) {
            __asm__ volatile("wfe");
        }
    }
    config->monitor_entry(&workspace->handoff);
    for (;;) {
        __asm__ volatile("wfe");
    }
}
