#pragma once
// SPDX-License-Identifier: BSD-2-Clause
#include "fbr34ker/types.h"

#define MAX_KERNEL_PATCHES 16U
#define PATCH_NAME_MAX_LENGTH 48U
#define PATCH_DATA_MAX_SIZE 256U

typedef enum {
    KERNEL_PATCH_TYPE_MEMORY = 0,
    KERNEL_PATCH_TYPE_SYSTEM_CALL,
    KERNEL_PATCH_TYPE_INTERRUPT,
    KERNEL_PATCH_TYPE_AUTHENTICATION,
    KERNEL_PATCH_TYPE_PRIVILEGE,
    KERNEL_PATCH_TYPE_IO_REMAP,
    KERNEL_PATCH_TYPE_MONITOR_HOOK,
    KERNEL_PATCH_TYPE_COUNT
} kernel_patch_type_t;

typedef enum {
    KERNEL_PATCH_STATE_INACTIVE = 0,
    KERNEL_PATCH_STATE_PENDING,
    KERNEL_PATCH_STATE_APPLIED,
    KERNEL_PATCH_STATE_FAILED,
    KERNEL_PATCH_STATE_REVERTED
} kernel_patch_state_t;

typedef struct {
    char name[PATCH_NAME_MAX_LENGTH];
    kernel_patch_type_t type;
    kernel_patch_state_t state;
    u64 target_address;
    u64 patch_size;
    u64 original_value;
    u64 patch_value;
    bool applied;
    bool persistent;
} kernel_patch_entry_t;

typedef struct {
    kernel_patch_entry_t patches[MAX_KERNEL_PATCHES];
    u32 patch_count;
    u32 applied_count;
    u32 failed_count;
    bool patching_enabled;
    bool privilege_escalated;
    u64 escalation_level;
} kernel_patches_status_t;

void kernel_patches_init(void);
kernel_patches_status_t kernel_patches_status(void);

bool kernel_patches_set_soc(u16 cpid, u64 kbase);
bool kernel_patches_set_dram_base(u64 dram_phys_base);
bool kernel_patches_register(const char *name, kernel_patch_type_t type,
                              u64 target_address, u64 patch_size,
                              u64 original_value, u64 patch_value,
                              bool persistent);

bool kernel_patches_apply_all(void);
bool kernel_patches_apply_by_type(kernel_patch_type_t type);
bool kernel_patches_revert_all(void);
bool kernel_patches_revert_by_type(kernel_patch_type_t type);
bool kernel_patches_apply_single(u32 index);
bool kernel_patches_revert_single(u32 index);

bool kernel_patches_escalate_privilege(u64 target_el);
bool kernel_patches_bypass_authentication(void);
bool kernel_patches_hijack_syscall(u64 syscall_number, u64 handler_address);
bool kernel_patches_remap_io_region(u64 physical_base, u64 virtual_base, u64 size);

const char *kernel_patch_type_name(kernel_patch_type_t type);
const char *kernel_patch_state_name(kernel_patch_state_t state);
bool kernel_patching_available(void);
u32 kernel_patch_applied_count(void);

/* Find/return the currently set kernel base address */
bool kernel_patches_find_base(u64 *kbase);
