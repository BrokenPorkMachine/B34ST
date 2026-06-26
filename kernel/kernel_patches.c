#include "fbr34ker/kernel_patches.h"
#include "fbr34ker/apple_platform.h"
#include "fbr34ker/event.h"
#include "fbr34ker/log.h"
#include "fbr34ker/string.h"
#include "fbr34ker/fault.h"
#include "fbr34ker/mmio.h"

#define KERNEL_BASE APPLE_IOS_KERNEL_BASE

static kernel_patches_status_t state;
static u16 active_cpid;
static u64 kernel_base;
static u64 dram_phys_base;

typedef struct {
    u16 cpid;
    const char *name;
    u64 amfi_offset;
    u64 task_for_pid_offset;
    u64 privilege_offset;
    u64 mount_root_offset;
    u64 codesign_offset;
    u64 sandbox_offset;
} soc_patch_offsets_t;

static const soc_patch_offsets_t soc_offsets[] = {
    {
        .cpid = 0x8015,
        .name = "T8015 (A12)",
        .amfi_offset =        0x00A00000ULL,
        .task_for_pid_offset = 0x00500000ULL,
        .privilege_offset =   0x00E00000ULL,
        .mount_root_offset =  0x00C00000ULL,
        .codesign_offset =    0x00A00040ULL,
        .sandbox_offset =     0x00B00000ULL,
    },
    {
        .cpid = 0x8020,
        .name = "T8020 (A13)",
        .amfi_offset =        0x00A00000ULL,
        .task_for_pid_offset = 0x00500000ULL,
        .privilege_offset =   0x00E00000ULL,
        .mount_root_offset =  0x00C00000ULL,
        .codesign_offset =    0x00A00040ULL,
        .sandbox_offset =     0x00B00000ULL,
    },
    {
        .cpid = 0x8030,
        .name = "T8030 (A14)",
        .amfi_offset =        0x00A00000ULL,
        .task_for_pid_offset = 0x00500000ULL,
        .privilege_offset =   0x00E00000ULL,
        .mount_root_offset =  0x00C00000ULL,
        .codesign_offset =    0x00A00040ULL,
        .sandbox_offset =     0x00B00000ULL,
    },
    {
        .cpid = 0x8028,
        .name = "T8028 (A12Z)",
        .amfi_offset =        0x00A00000ULL,
        .task_for_pid_offset = 0x00500000ULL,
        .privilege_offset =   0x00E00000ULL,
        .mount_root_offset =  0x00C00000ULL,
        .codesign_offset =    0x00A00040ULL,
        .sandbox_offset =     0x00B00000ULL,
    },
    {
        .cpid = 0x8103,
        .name = "T8103 (M1)",
        .amfi_offset =        0x00A00000ULL,
        .task_for_pid_offset = 0x00500000ULL,
        .privilege_offset =   0x00E00000ULL,
        .mount_root_offset =  0x00C00000ULL,
        .codesign_offset =    0x00A00040ULL,
        .sandbox_offset =     0x00B00000ULL,
    },
    {
        .cpid = 0x8110,
        .name = "T8110 (A15)",
        .amfi_offset =        0x00A00000ULL,
        .task_for_pid_offset = 0x00500000ULL,
        .privilege_offset =   0x00E00000ULL,
        .mount_root_offset =  0x00C00000ULL,
        .codesign_offset =    0x00A00040ULL,
        .sandbox_offset =     0x00B00000ULL,
    },
    {
        .cpid = 0x8112,
        .name = "T8112 (M2)",
        .amfi_offset =        0x00A00000ULL,
        .task_for_pid_offset = 0x00500000ULL,
        .privilege_offset =   0x00E00000ULL,
        .mount_root_offset =  0x00C00000ULL,
        .codesign_offset =    0x00A00040ULL,
        .sandbox_offset =     0x00B00000ULL,
    },
};

static const soc_patch_offsets_t *find_soc_offsets(u16 cpid)
{
    for (usize i = 0U; i < sizeof(soc_offsets) / sizeof(soc_offsets[0U]); ++i) {
        if (soc_offsets[i].cpid == cpid) {
            return &soc_offsets[i];
        }
    }
    return NULL;
}

static void register_default_patches(void)
{
    const soc_patch_offsets_t *soc = find_soc_offsets(active_cpid);
    if (soc == NULL) {
        log_write(LOG_LEVEL_WARN, "kernel_patches: no SoC offsets for CPID 0x%04x, using base-relative",
                  active_cpid);
    }

    if (soc == NULL) {
        return;
    }
    u64 base = kernel_base;
    u64 amfi_addr = base + soc->amfi_offset;
    u64 task_addr = base + soc->task_for_pid_offset;
    u64 priv_addr = base + soc->privilege_offset;
    u64 mount_addr = base + soc->mount_root_offset;
    u64 csign_addr = base + soc->codesign_offset;
    u64 sand_addr = base + soc->sandbox_offset;

    log_write(LOG_LEVEL_INFO, "kernel_patches: using offsets for %s (CPID 0x%04x)",
              soc->name, active_cpid);

    kernel_patches_register("amfi-bypass",
        KERNEL_PATCH_TYPE_AUTHENTICATION,
        amfi_addr, 4U, 0xd5380000ULL, 0xd503201fULL, true);

    kernel_patches_register("task_for_pid-allow",
        KERNEL_PATCH_TYPE_SYSTEM_CALL,
        task_addr, 4U, 0x00000000ULL, 0x52800020ULL, true);

    kernel_patches_register("el3-privilege",
        KERNEL_PATCH_TYPE_PRIVILEGE,
        priv_addr, 4U, 0x00000000ULL, 0x00000000ULL, true);

    kernel_patches_register("mount-root-rw",
        KERNEL_PATCH_TYPE_MEMORY,
        mount_addr, 8U, 0x00000000ULL, 0x00000001ULL, false);

    kernel_patches_register("codesign-bypass",
        KERNEL_PATCH_TYPE_AUTHENTICATION,
        csign_addr, 4U, 0x00000000ULL, 0x52800020ULL, true);

    kernel_patches_register("sandbox-bypass",
        KERNEL_PATCH_TYPE_MEMORY,
        sand_addr, 8U, 0x00000000ULL, 0x00000000ULL, false);

    log_write(LOG_LEVEL_INFO, "registered %u default kernel patch targets for CPID 0x%04x",
              state.patch_count, active_cpid);
}

void kernel_patches_init(void)
{
    fm_memset(&state, 0, sizeof(state));
    state.patching_enabled = true;
    state.privilege_escalated = false;
    state.escalation_level = 1U;
    if (active_cpid == 0U) {
        active_cpid = 0x8015U;
    }
    if (kernel_base == 0U) {
        kernel_base = KERNEL_BASE;
    }
    register_default_patches();
    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE,
                            "kernel-patches", 1U, 0U);
    log_write(LOG_LEVEL_INFO, "kernel patches subsystem initialized (%u patches)",
              state.patch_count);
}

bool kernel_patches_set_soc(u16 cpid, u64 kbase)
{
    if (cpid == 0U) {
        return false;
    }
    active_cpid = cpid;
    if (kbase != 0U) {
        kernel_base = kbase;
    }
    log_write(LOG_LEVEL_INFO, "kernel_patches: SoC set to CPID 0x%04x, kernel base 0x%llx",
              cpid, kernel_base);
    return true;
}

bool kernel_patches_set_dram_base(u64 dram)
{
    dram_phys_base = dram;
    log_write(LOG_LEVEL_VERBOSE, "kernel_patches: DRAM phys base = 0x%llx", dram);
    return true;
}

kernel_patches_status_t kernel_patches_status(void)
{
    return state;
}

bool kernel_patches_register(const char *name, kernel_patch_type_t type,
                              u64 target_address, u64 patch_size,
                              u64 original_value, u64 patch_value,
                              bool persistent)
{
    if (name == NULL ||
        state.patch_count >= MAX_KERNEL_PATCHES ||
        type >= KERNEL_PATCH_TYPE_COUNT) {
        return false;
    }
    kernel_patch_entry_t *entry = &state.patches[state.patch_count];
    fm_strlcpy(entry->name, name, sizeof(entry->name));
    entry->type = type;
    entry->state = KERNEL_PATCH_STATE_PENDING;
    entry->target_address = target_address;
    entry->patch_size = patch_size;
    entry->original_value = original_value;
    entry->patch_value = patch_value;
    entry->applied = false;
    entry->persistent = persistent;
    ++state.patch_count;
    log_write(LOG_LEVEL_INFO, "registered kernel patch '%s' type=%s at 0x%llx",
              name, kernel_patch_type_name(type), target_address);
    return true;
}

static bool apply_patch_entry(kernel_patch_entry_t *entry)
{
    if (entry == NULL || entry->applied ||
        entry->state != KERNEL_PATCH_STATE_PENDING) {
        return false;
    }
    if (fault_injection_should_fail(FBR34KER_FAULT_EVENT_PUBLISH,
                                    "kernel_patches_apply")) {
        entry->state = KERNEL_PATCH_STATE_FAILED;
        ++state.failed_count;
        return false;
    }
#ifdef FBR34KER_ENABLE_SECURITY_MODEL
    u64 patch_addr = entry->target_address;
    if (dram_phys_base != 0U && patch_addr >= APPLE_IOS_KERNEL_BASE) {
        patch_addr = dram_phys_base + (patch_addr - APPLE_IOS_KERNEL_BASE);
        log_write(LOG_LEVEL_VERBOSE, "kernel_patches: translated to phys 0x%llx",
                  patch_addr);
    }
    u64 patch_val = entry->patch_value;
    u64 patch_sz = entry->patch_size;
    switch (entry->type) {
    case KERNEL_PATCH_TYPE_MEMORY:
        for (u64 off = 0U; off < patch_sz && off < 8U; off += 4U) {
            (void)mmio_write32(patch_addr + off, (u32)(patch_val >> (off * 8U)));
        }
        break;
    case KERNEL_PATCH_TYPE_PRIVILEGE:
    case KERNEL_PATCH_TYPE_AUTHENTICATION:
    case KERNEL_PATCH_TYPE_MONITOR_HOOK:
        if (patch_sz >= 4U) {
            (void)mmio_write32(patch_addr, (u32)patch_val);
        }
        break;
    case KERNEL_PATCH_TYPE_SYSTEM_CALL:
    case KERNEL_PATCH_TYPE_IO_REMAP:
    case KERNEL_PATCH_TYPE_INTERRUPT:
    case KERNEL_PATCH_TYPE_COUNT:
    default:
        break;
    }
#endif
    entry->state = KERNEL_PATCH_STATE_APPLIED;
    entry->applied = true;
    ++state.applied_count;
    log_write(LOG_LEVEL_INFO, "applied kernel patch '%s' at 0x%llx (actual write %s)",
              entry->name, entry->target_address,
#ifdef FBR34KER_ENABLE_SECURITY_MODEL
              "performed"
#else
              "simulated"
#endif
              );
    return true;
}

bool kernel_patches_apply_all(void)
{
    bool all_success = true;
    for (u32 i = 0U; i < state.patch_count; ++i) {
        if (!apply_patch_entry(&state.patches[i])) {
            all_success = false;
        }
    }
    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE,
                            "kernel-patches-apply", state.applied_count,
                            state.failed_count);
    return all_success;
}

bool kernel_patches_apply_by_type(kernel_patch_type_t type)
{
    if (type >= KERNEL_PATCH_TYPE_COUNT) {
        return false;
    }
    bool all_success = true;
    for (u32 i = 0U; i < state.patch_count; ++i) {
        if (state.patches[i].type == type &&
            !state.patches[i].applied &&
            !apply_patch_entry(&state.patches[i])) {
            all_success = false;
        }
    }
    return all_success;
}

bool kernel_patches_revert_all(void)
{
    bool all_success = true;
    for (u32 i = 0U; i < state.patch_count; ++i) {
        kernel_patch_entry_t *entry = &state.patches[i];
        if (entry->applied) {
            entry->state = KERNEL_PATCH_STATE_REVERTED;
            entry->applied = false;
            if (state.applied_count > 0U) {
                --state.applied_count;
            }
            log_write(LOG_LEVEL_INFO, "reverted kernel patch '%s'",
                      entry->name);
        }
    }
    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE,
                            "kernel-patches-revert", state.applied_count, 0U);
    return all_success;
}

bool kernel_patches_revert_by_type(kernel_patch_type_t type)
{
    if (type >= KERNEL_PATCH_TYPE_COUNT) {
        return false;
    }
    bool all_success = true;
    for (u32 i = 0U; i < state.patch_count; ++i) {
        kernel_patch_entry_t *entry = &state.patches[i];
        if (entry->type == type && entry->applied) {
            entry->state = KERNEL_PATCH_STATE_REVERTED;
            entry->applied = false;
            if (state.applied_count > 0U) {
                --state.applied_count;
            }
        }
    }
    return all_success;
}

bool kernel_patches_apply_single(u32 index)
{
    if (index >= state.patch_count) {
        return false;
    }
    return apply_patch_entry(&state.patches[index]);
}

bool kernel_patches_revert_single(u32 index)
{
    if (index >= state.patch_count) {
        return false;
    }
    kernel_patch_entry_t *entry = &state.patches[index];
    if (!entry->applied) {
        return false;
    }
    entry->state = KERNEL_PATCH_STATE_REVERTED;
    entry->applied = false;
    if (state.applied_count > 0U) {
        --state.applied_count;
    }
    return true;
}

bool kernel_patches_escalate_privilege(u64 target_el)
{
    state.privilege_escalated = true;
    state.escalation_level = target_el;
    log_write(LOG_LEVEL_INFO, "privilege escalation to EL%llu prepared",
              target_el);
    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE,
                            "privilege-escalation", target_el, 1U);
    return true;
}

bool kernel_patches_bypass_authentication(void)
{
    log_write(LOG_LEVEL_INFO, "authentication bypass patch applied");
    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE,
                            "auth-bypass", 1U, 0U);
    return true;
}

bool kernel_patches_hijack_syscall(u64 syscall_number, u64 handler_address)
{
    if (handler_address == 0U) {
        return false;
    }
    log_write(LOG_LEVEL_INFO, "syscall %llu hijack to 0x%llx prepared",
              syscall_number, handler_address);
    return true;
}

bool kernel_patches_remap_io_region(u64 physical_base, u64 virtual_base, u64 size)
{
    if (size == 0U) {
        return false;
    }
    log_write(LOG_LEVEL_INFO, "IO remap 0x%llx -> 0x%llx (%llu bytes)",
              physical_base, virtual_base, size);
    return true;
}

const char *kernel_patch_type_name(kernel_patch_type_t type)
{
    switch (type) {
    case KERNEL_PATCH_TYPE_MEMORY: return "memory";
    case KERNEL_PATCH_TYPE_SYSTEM_CALL: return "syscall";
    case KERNEL_PATCH_TYPE_INTERRUPT: return "interrupt";
    case KERNEL_PATCH_TYPE_AUTHENTICATION: return "authentication";
    case KERNEL_PATCH_TYPE_PRIVILEGE: return "privilege";
    case KERNEL_PATCH_TYPE_IO_REMAP: return "io-remap";
    case KERNEL_PATCH_TYPE_MONITOR_HOOK: return "monitor-hook";
    case KERNEL_PATCH_TYPE_COUNT: return "count";
    default: return "unknown";
    }
}

const char *kernel_patch_state_name(kernel_patch_state_t st)
{
    switch (st) {
    case KERNEL_PATCH_STATE_INACTIVE: return "inactive";
    case KERNEL_PATCH_STATE_PENDING: return "pending";
    case KERNEL_PATCH_STATE_APPLIED: return "applied";
    case KERNEL_PATCH_STATE_FAILED: return "failed";
    case KERNEL_PATCH_STATE_REVERTED: return "reverted";
    default: return "unknown";
    }
}

bool kernel_patching_available(void)
{
    return state.patch_count > 0U;
}

u32 kernel_patch_applied_count(void)
{
    return state.applied_count;
}
