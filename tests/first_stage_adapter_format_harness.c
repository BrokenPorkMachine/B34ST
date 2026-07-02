#include <stdint.h>
#include "fbr34ker/first_stage_adapter.h"
// SPDX-License-Identifier: BSD-2-Clause
int main(void) {
    fbr34ker_first_stage_adapter_descriptor_t descriptor = {0};
    descriptor.abi_version = FBR34KER_FIRST_STAGE_ADAPTER_ABI_VERSION;
    descriptor.structure_size = sizeof(descriptor);
    descriptor.capabilities = FBR34KER_FIRST_STAGE_CAP_UPLOAD |
                              FBR34KER_FIRST_STAGE_CAP_START |
                              FBR34KER_FIRST_STAGE_CAP_RESET;
    descriptor.maximum_memory_regions = FBR34KER_FIRST_STAGE_MAX_MEMORY_REGIONS;
    return descriptor.structure_size == FBR34KER_FIRST_STAGE_DESCRIPTOR_SIZE &&
           (descriptor.capabilities & ~FBR34KER_FIRST_STAGE_CAP_SUPPORTED) == 0 ? 0 : 1;
}
