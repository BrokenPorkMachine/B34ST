#ifndef FBR34KER_SDK_MODULES_H
#define FBR34KER_SDK_MODULES_H
#include <stdint.h>
#include "fbr34ker_memory.h"

#define FBR34KER_HANDOFF_MAX_BOOT_MODULES 16U
#define FBR34KER_HANDOFF_MODULE_CAP_MASK_SUPPORTED 0x3fU
#define FBR34KER_HANDOFF_MAX_MODULE_SLOTS 4U
#define FBR34KER_HANDOFF_MAX_INSTRUCTION_BUDGET 4096U
#define FBR34KER_BOOT_MODULE_TYPE_FMOD 1U
#define FBR34KER_BOOT_MODULE_MAX_FMOD_SIZE (64U * 1024U)

// SPDX-License-Identifier: BSD-2-Clause
typedef struct FBR34KER_SDK_PACKED {
    const void *base;
    uint64_t size;
    uint32_t type;
    uint32_t flags;
} fbr34ker_handoff_boot_module_t;

#endif
