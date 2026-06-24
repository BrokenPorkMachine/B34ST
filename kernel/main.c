#include "fbr34ker/allocator.h"
#include "fbr34ker/architecture.h"
#include "fbr34ker/build_info.h"
#include "fbr34ker/bringup.h"
#include "fbr34ker/boot_evidence.h"
#include "fbr34ker/command.h"
#include "fbr34ker/console.h"
#include "fbr34ker/crash.h"
#include "fbr34ker/device_tree.h"
#include "fbr34ker/exception.h"
#include "fbr34ker/format.h"
#include "fbr34ker/handoff.h"
#include "fbr34ker/hardware_probe.h"
#include "fbr34ker/log.h"
#include "fbr34ker/interrupt.h"
#include "fbr34ker/module.h"
#include "fbr34ker/platform.h"
#include "fbr34ker/protocol.h"
#include "fbr34ker/stack_guard.h"
#include "fbr34ker/version.h"
#include "fbr34ker/watchdog.h"

extern u8 __image_start[];
extern u8 __image_end[];

static void print_banner(void)
{
    fm_printf("\n");
    fm_printf("  FBR34KER %s\n", FBR34KER_MONITOR_VERSION);
    fm_printf("  Clean-room AArch64 preboot research monitor\n");
    const fbr34ker_build_info_t *build = fbr34ker_build_info();
    fm_printf("  Build: %s / %s\n", build->build_channel, build->build_target);
    fm_printf("  Platform: %s\n\n", platform_name());
}

static void load_handoff_modules(const fbr34ker_handoff_t *handoff)
{
    if (handoff == NULL || handoff->version < FBR34KER_HANDOFF_VERSION_2) {
        return;
    }
    for (u32 index = 0U; index < handoff->boot_module_count; ++index) {
        const fbr34ker_handoff_boot_module_t *item = &handoff->boot_modules[index];
        if (item->type != 1U || item->base == NULL ||
            item->size > FBR34KER_MODULE_MAX_CONTAINER_SIZE) {
            log_write(LOG_LEVEL_WARN, "ignored boot module %u", index);
            continue;
        }
        const char *name = NULL;
        const fbr34ker_module_result_t result = module_load_container(
            item->base, (usize)item->size, &name);
        if (result == MODULE_OK) {
            log_write(LOG_LEVEL_INFO, "accepted boot module %s", name);
        } else {
            log_write(LOG_LEVEL_WARN, "boot module %u rejected: %s", index,
                      module_result_string(result));
        }
    }
}

typedef enum {
    BOOT_TREE_NONE = 0,
    BOOT_TREE_LOADER,
    BOOT_TREE_FIRMWARE,
    BOOT_TREE_INVALID_LOADER,
} boot_tree_source_t;

static boot_tree_source_t initialize_device_tree_early(
    const void *boot_context, const fbr34ker_handoff_t *handoff)
{
    const bool handoff_has_device_tree = handoff != NULL &&
        handoff->device_tree != NULL && handoff->device_tree_size != 0U &&
        (handoff->version == FBR34KER_HANDOFF_VERSION_1 ||
         (handoff->flags & FBR34KER_HANDOFF_FLAG_DEVICE_TREE_VALID) != 0U);
    if (handoff_has_device_tree) {
        return device_tree_init(handoff->device_tree,
                                (usize)handoff->device_tree_size)
            ? BOOT_TREE_LOADER : BOOT_TREE_INVALID_LOADER;
    }
    if (device_tree_looks_valid(boot_context, 0U) &&
        device_tree_init(boot_context, 0U)) {
        return BOOT_TREE_FIRMWARE;
    }
    return BOOT_TREE_NONE;
}

NORETURN void kernel_main(const void *boot_context)
{
    boot_evidence_init();
    const fbr34ker_handoff_t *handoff = (const fbr34ker_handoff_t *)boot_context;
    const u64 image_base = (u64)(usize)__image_start;
    const u64 image_size = (u64)(usize)(__image_end - __image_start);
    if (fbr34ker_handoff_valid(handoff) &&
        fbr34ker_handoff_covers_range(handoff, image_base, image_size)) {
        fbr34ker_handoff_set_active(handoff);
    } else {
        handoff = NULL;
        fbr34ker_handoff_set_active(NULL);
    }

    const boot_tree_source_t tree_source =
        initialize_device_tree_early(boot_context, handoff);
    boot_evidence_stage(FBR34KER_BOOT_STAGE_CONTEXT);

    platform_prepare(boot_context);
    console_init();
    boot_evidence_stage(FBR34KER_BOOT_STAGE_PLATFORM);
    exception_init();
    interrupt_init();
    allocator_init();
    stack_guard_init();
    log_init();
    crash_init();
    protocol_init();
    watchdog_init();
    hardware_probe_init();
    boot_evidence_stage(FBR34KER_BOOT_STAGE_RUNTIME);
    const bool architecture_ok = architecture_init();
    if (architecture_ok) boot_evidence_stage(FBR34KER_BOOT_STAGE_ARCHITECTURE);
    else boot_evidence_error(1U, 0U);

    print_banner();
    log_write(LOG_LEVEL_INFO, "booted at EL%llu", cpu_current_el());
    log_write(LOG_LEVEL_INFO, "image 0x%016llx..0x%016llx",
              (u64)(usize)__image_start, (u64)(usize)__image_end);
    log_write(architecture_ok ? LOG_LEVEL_INFO : LOG_LEVEL_ERROR,
              "runtime architecture %s", architecture_ok ? "ready" : "failed");

    if (handoff != NULL) {
        log_write(LOG_LEVEL_INFO,
                  "accepted handoff v%u with %u memory regions",
                  handoff->version, handoff->memory_region_count);
    } else if (boot_context != NULL &&
               !device_tree_looks_valid(boot_context, 0U)) {
        log_write(LOG_LEVEL_WARN, "ignored unknown boot context");
    } else {
        log_write(LOG_LEVEL_INFO, "direct firmware/QEMU boot context");
    }

    if (tree_source == BOOT_TREE_LOADER) {
        log_write(LOG_LEVEL_INFO, "accepted loader device tree (%llu bytes)",
                  (u64)device_tree_size());
    } else if (tree_source == BOOT_TREE_FIRMWARE) {
        log_write(LOG_LEVEL_INFO, "accepted firmware/QEMU device tree (%llu bytes)",
                  (u64)device_tree_size());
    } else if (tree_source == BOOT_TREE_INVALID_LOADER) {
        log_write(LOG_LEVEL_WARN, "loader device tree failed validation");
    }
    if (crash_available()) {
        log_write(LOG_LEVEL_WARN, "a preserved crash report is available");
    }
    module_system_init();
    if (hardware_probe_modules_allowed()) {
        load_handoff_modules(handoff);
    } else if (handoff != NULL && handoff->boot_module_count != 0U) {
        log_write(LOG_LEVEL_WARN, "boot modules locked by defensive hardware mode");
    }
    bringup_init();
    boot_evidence_stage(FBR34KER_BOOT_STAGE_INTERACTIVE);
    shell_init();
    shell_run();
}
