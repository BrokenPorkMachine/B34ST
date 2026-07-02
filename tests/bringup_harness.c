#include "fbr34ker/bringup.h"
#include "fbr34ker/handoff.h"
#include "fbr34ker/hardware_probe.h"
#include "fbr34ker/string.h"

// SPDX-License-Identifier: BSD-2-Clause
bool hardware_probe_active(void)
{
    return fbr34ker_handoff_active() != NULL;
}

bool hardware_probe_unlock(void)
{
    return true;
}

bool hardware_probe_immutable(void)
{
    return false;
}

int main(void)
{
    fbr34ker_handoff_set_active(NULL);
    bringup_init();
    if (bringup_restricted() || !bringup_command_allowed("module-run")) return 1;

    fbr34ker_handoff_region_t region = {
        .base = 0x80000000U,
        .size = 0x1000U,
        .type = FBR34KER_HANDOFF_REGION_MONITOR,
        .attributes = FBR34KER_REGION_ATTR_READ |
                      FBR34KER_REGION_ATTR_WRITE |
                      FBR34KER_REGION_ATTR_EXECUTE,
    };
    fbr34ker_handoff_t handoff;
    fm_memset(&handoff, 0, sizeof(handoff));
    handoff.magic = FBR34KER_HANDOFF_MAGIC;
    handoff.version = FBR34KER_HANDOFF_VERSION_1;
    handoff.structure_size = sizeof(handoff);
    handoff.monitor_base = region.base;
    handoff.monitor_size = region.size;
    handoff.memory_regions = &region;
    handoff.memory_region_count = 1U;
    fbr34ker_handoff_set_active(&handoff);
    if (fbr34ker_handoff_active() == NULL) return 2;

    bringup_init();
    if (!bringup_restricted()) return 3;
    if (!bringup_command_allowed("timer-test")) return 4;
    if (bringup_command_allowed("module-run")) return 5;
    bringup_exit();
    if (bringup_restricted() || !bringup_command_allowed("module-run")) return 6;
    bringup_enter();
    if (!bringup_restricted()) return 7;
    return 0;
}
