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
#include "fbr34ker/kernel_patches.h"
#include "fbr34ker/secure_boot_bypass.h"
#include "fbr34ker/persistence.h"
#include "fbr34ker/log.h"
#include "fbr34ker/interrupt.h"
#include "fbr34ker/module.h"
#include "fbr34ker/platform.h"
#include "fbr34ker/protocol.h"
#include "fbr34ker/stack_guard.h"
#include "fbr34ker/timer.h"
#include "fbr34ker/version.h"
#include "fbr34ker/watchdog.h"
#include "fbr34ker/usb.h"
#include "fbr34ker/usbliter8_exploit.h"
#include "fbr34ker/trust_cache.h"
#include "fbr34ker/jailbreak.h"
#include "fbr34ker/jbinit.h"
#include "fbr34ker/mmu.h"
#include "fbr34ker/apple_platform.h"

// SPDX-License-Identifier: BSD-2-Clause
extern u8 __image_start[];
extern u8 __image_end[];

NORETURN void kernel_main(const void *boot_context);

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
        log_trace("load_handoff_modules: no handoff or version < 2, skipping");
        return;
    }
    log_verbose("loading %u boot modules from handoff", handoff->boot_module_count);
    for (u32 index = 0U; index < handoff->boot_module_count; ++index) {
        const fbr34ker_handoff_boot_module_t *item = &handoff->boot_modules[index];
        if (item->type != 1U || item->base == NULL ||
            item->size > FBR34KER_MODULE_MAX_CONTAINER_SIZE) {
            log_trace("  boot module %u: type=%u base=%p size=%llu -> ignored",
                      index, item->type, (void *)item->base, (u64)item->size);
            continue;
        }
        const char *name = NULL;
        const fbr34ker_module_result_t result = module_load_container(
            item->base, (usize)item->size, &name);
        if (result == MODULE_OK) {
            log_info("boot module %s accepted", name ? name : "?");
        } else {
            log_warn("boot module %u rejected: %s", index,
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
        log_trace("device tree from handoff: size=%llu flags=0x%x",
                  (u64)handoff->device_tree_size, handoff->flags);
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

    log_set_level(LOG_LEVEL_TRACE);

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
    log_trace("handoff at %p %s", (const void *)boot_context,
              handoff != NULL ? "accepted" : "absent");

    initialize_device_tree_early(boot_context, handoff);
    boot_evidence_stage(FBR34KER_BOOT_STAGE_CONTEXT);
    log_trace("stage CONTEXT");

    platform_prepare(boot_context);
    console_init();
    boot_evidence_stage(FBR34KER_BOOT_STAGE_PLATFORM);
    log_trace("stage PLATFORM");

    exception_init();
    interrupt_init();
    allocator_init();
    stack_guard_init();
    log_init();
    log_trace("subsystem inits done");

    crash_init();
    protocol_init();
    watchdog_init();
    hardware_probe_init();
    apple_soc_init();
    kernel_patches_init();
    secure_boot_bypass_init();
    persistence_init();
    trust_cache_init();
    usbliter8_exploit_init();
    jbinit_init();
    jbinit_run_all();
    jailbreak_init();
    boot_evidence_stage(FBR34KER_BOOT_STAGE_RUNTIME);
    log_trace("stage RUNTIME");

    const bool architecture_ok = architecture_init();
    if (architecture_ok) {
        boot_evidence_stage(FBR34KER_BOOT_STAGE_ARCHITECTURE);
    } else {
        boot_evidence_error(1U, 0U);
    }
    log_trace("stage ARCHITECTURE %s", architecture_ok ? "ok" : "FAILED");

    print_banner();
    log_info("booted at EL%llu image %llu bytes",
             cpu_current_el(), image_size);
    log_info("architecture %s", architecture_ok ? "ready" : "failed");

    if (handoff != NULL) {
        log_info("handoff v%u: %u regions, %u modules",
                 handoff->version, handoff->memory_region_count,
                 handoff->boot_module_count);
    } else if (boot_context != NULL &&
               !device_tree_looks_valid(boot_context, 0U)) {
        log_warn("unknown boot context at %p", boot_context);
    } else {
        log_info("direct firmware/QEMU boot");
    }

    if (crash_available()) {
        log_warn("crash report preserved");
    }
    module_system_init();
    if (hardware_probe_modules_allowed()) {
        load_handoff_modules(handoff);
    } else if (handoff != NULL && handoff->boot_module_count != 0U) {
        log_warn("boot modules locked by hardware probe");
    }
    bringup_init();
    boot_evidence_stage(FBR34KER_BOOT_STAGE_INTERACTIVE);
    log_trace("stage INTERACTIVE");
    shell_init();
    log_verbose("entering shell");
    shell_run();
}
