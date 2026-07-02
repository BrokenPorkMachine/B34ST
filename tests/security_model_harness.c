#include "fbr34ker/event.h"
#include "fbr34ker/fault.h"
#include "fbr34ker/kernel_patches.h"
#include "fbr34ker/log.h"
#include "fbr34ker/persistence.h"
#include "fbr34ker/secure_boot_bypass.h"

#include <stdarg.h>

// SPDX-License-Identifier: BSD-2-Clause
bool event_bus_publish(fbr34ker_event_type_t type, const char *source,
                       u64 value0, u64 value1)
{
    UNUSED(type);
    UNUSED(source);
    UNUSED(value0);
    UNUSED(value1);
    return true;
}

bool fault_injection_should_fail(fbr34ker_fault_point_t point,
                                 const char *source)
{
    UNUSED(point);
    UNUSED(source);
    return false;
}

void log_write(log_level_t level, const char *format, ...)
{
    UNUSED(level);
    UNUSED(format);
}

int main(void)
{
    u8 output[256U];
    const u8 manifest[] = {1U, 2U, 3U};
    usize output_size = sizeof(output);

    kernel_patches_init();
    secure_boot_bypass_init();
    persistence_init();

    /* subsystems are available after init with default entries */
    if (!kernel_patching_available()) return 1;
    if (!secure_boot_bypass_available()) return 2;
    if (!persistence_available()) return 3;

    /* verify default patches registered */
    kernel_patches_status_t kps = kernel_patches_status();
    if (kps.patch_count == 0U) return 4;

    /* verify default bypasses registered */
    secure_boot_bypass_status_t sbs = secure_boot_bypass_status();
    if (sbs.bypass_count == 0U) return 5;

    /* verify default hooks registered */
    persistence_status_t ps = persistence_status();
    if (ps.hook_count == 0U) return 6;

    /* can register additional patches */
    if (!kernel_patches_register("test-patch", KERNEL_PATCH_TYPE_MEMORY,
                                 0x1000U, 8U, 0U, 1U, false)) return 7;

    /* can apply all patches */
    if (!kernel_patches_apply_all()) return 8;
    kps = kernel_patches_status();
    if (kps.applied_count == 0U) return 9;

    /* can escalate privilege */
    if (!kernel_patches_escalate_privilege(3U)) return 10;

    /* individual bypass functions work */
    if (!secure_boot_bypass_image4_signature()) return 11;
    if (secure_boot_bypass_forge_signature(output, &output_size,
                                            manifest, sizeof(manifest))) return 12;

    /* can activate all bypasses */
    if (!secure_boot_bypass_activate_all()) return 13;
    sbs = secure_boot_bypass_status();
    if (sbs.active_count == 0U) return 14;

    /* persistence operations work */
    if (!persistence_deploy_all()) return 15;
    if (!persistence_activate_all()) return 16;
    if (!persistence_enable_ota_persistence()) return 17;

    /* A physical base is metadata, never an in-array write offset. */
    if (!persistence_allocate_hidden_storage(0x800000000ULL, 32U)) return 22;
    if (!persistence_store_payload("bounded", manifest, sizeof(manifest))) return 23;
    ps = persistence_status();
    if (ps.hidden_storage_base != 0x800000000ULL) return 24;
    if (ps.hidden_storage[0] != 1U || ps.hidden_storage[2] != 3U) return 25;

    /* verify state after operations */
    ps = persistence_status();
    if (!ps.ota_persistent) return 18;
    if (ps.active_count == 0U) return 19;

    /* revert all patches */
    if (!kernel_patches_revert_all()) return 20;
    kps = kernel_patches_status();
    if (kps.applied_count != 0U) return 21;

    return 0;
}
