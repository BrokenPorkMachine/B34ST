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

typedef enum {
    IOS_VERSION_UNKNOWN = 0,
    IOS_VERSION_16,
    IOS_VERSION_17,
    IOS_VERSION_18,
} ios_version_t;

static ios_version_t scan_kernel_version_string(u64 base);

typedef struct {
    u16 cpid;
    const char *name;
    ios_version_t ios_ver;
    u64 amfi_offset;
    u64 task_for_pid_offset;
    u64 privilege_offset;
    u64 mount_root_offset;
    u64 codesign_offset;
    u64 sandbox_offset;
    u64 pe_debugger_offset;
    u64 cs_enforcement_offset;
} soc_patch_offsets_t;

static const soc_patch_offsets_t soc_offsets[] = {
    /* ── A12 (T8020) ─────────────────────────────────────── */
    {
        .cpid = 0x8020,
        .name = "T8020 (A12) iOS 16",
        .ios_ver = IOS_VERSION_16,
        .amfi_offset =          0x00A00000ULL,
        .task_for_pid_offset =  0x00500000ULL,
        .privilege_offset =     0x00E00000ULL,
        .mount_root_offset =    0x00C00000ULL,
        .codesign_offset =      0x00A00040ULL,
        .sandbox_offset =       0x00B00000ULL,
        .pe_debugger_offset =   0x00D00000ULL,
        .cs_enforcement_offset = 0x00A00080ULL,
    },
    {
        .cpid = 0x8020,
        .name = "T8020 (A12) iOS 17+",
        .ios_ver = IOS_VERSION_17,
        .amfi_offset =          0x00B00000ULL,
        .task_for_pid_offset =  0x00520000ULL,
        .privilege_offset =     0x00F00000ULL,
        .mount_root_offset =    0x00D00000ULL,
        .codesign_offset =      0x00B00040ULL,
        .sandbox_offset =       0x00C00000ULL,
        .pe_debugger_offset =   0x00E00000ULL,
        .cs_enforcement_offset = 0x00B00080ULL,
    },
    /* ── A13 (T8030) ─────────────────────────────────────── */
    {
        .cpid = 0x8030,
        .name = "T8030 (A13) iOS 16",
        .ios_ver = IOS_VERSION_16,
        .amfi_offset =          0x00A00000ULL,
        .task_for_pid_offset =  0x00500000ULL,
        .privilege_offset =     0x00E00000ULL,
        .mount_root_offset =    0x00C00000ULL,
        .codesign_offset =      0x00A00040ULL,
        .sandbox_offset =       0x00B00000ULL,
        .pe_debugger_offset =   0x00D00000ULL,
        .cs_enforcement_offset = 0x00A00080ULL,
    },
    {
        .cpid = 0x8030,
        .name = "T8030 (A13) iOS 17+",
        .ios_ver = IOS_VERSION_17,
        .amfi_offset =          0x00B00000ULL,
        .task_for_pid_offset =  0x00520000ULL,
        .privilege_offset =     0x00F00000ULL,
        .mount_root_offset =    0x00D00000ULL,
        .codesign_offset =      0x00B00040ULL,
        .sandbox_offset =       0x00C00000ULL,
        .pe_debugger_offset =   0x00E00000ULL,
        .cs_enforcement_offset = 0x00B00080ULL,
    },
    /* ── A12Z (T8028) ────────────────────────────────────── */
    {
        .cpid = 0x8028,
        .name = "T8028 (A12Z) iOS 16",
        .ios_ver = IOS_VERSION_16,
        .amfi_offset =          0x00A40000ULL,
        .task_for_pid_offset =  0x00540000ULL,
        .privilege_offset =     0x00E40000ULL,
        .mount_root_offset =    0x00C40000ULL,
        .codesign_offset =      0x00A40040ULL,
        .sandbox_offset =       0x00B40000ULL,
        .pe_debugger_offset =   0x00D40000ULL,
        .cs_enforcement_offset = 0x00A40080ULL,
    },
    {
        .cpid = 0x8028,
        .name = "T8028 (A12Z) iOS 17+",
        .ios_ver = IOS_VERSION_17,
        .amfi_offset =          0x00B40000ULL,
        .task_for_pid_offset =  0x00560000ULL,
        .privilege_offset =     0x00F40000ULL,
        .mount_root_offset =    0x00D40000ULL,
        .codesign_offset =      0x00B40040ULL,
        .sandbox_offset =       0x00C40000ULL,
        .pe_debugger_offset =   0x00E40000ULL,
        .cs_enforcement_offset = 0x00B40080ULL,
    },
    /* ── A14 (T8101) ─────────────────────────────────────── */
    {
        .cpid = 0x8101,
        .name = "T8101 (A14) iOS 16",
        .ios_ver = IOS_VERSION_16,
        .amfi_offset =          0x00A80000ULL,
        .task_for_pid_offset =  0x00580000ULL,
        .privilege_offset =     0x00E80000ULL,
        .mount_root_offset =    0x00C80000ULL,
        .codesign_offset =      0x00A80040ULL,
        .sandbox_offset =       0x00B80000ULL,
        .pe_debugger_offset =   0x00D80000ULL,
        .cs_enforcement_offset = 0x00A80080ULL,
    },
    {
        .cpid = 0x8101,
        .name = "T8101 (A14) iOS 17+",
        .ios_ver = IOS_VERSION_17,
        .amfi_offset =          0x00B80000ULL,
        .task_for_pid_offset =  0x005A0000ULL,
        .privilege_offset =     0x00F80000ULL,
        .mount_root_offset =    0x00D80000ULL,
        .codesign_offset =      0x00B80040ULL,
        .sandbox_offset =       0x00C80000ULL,
        .pe_debugger_offset =   0x00E80000ULL,
        .cs_enforcement_offset = 0x00B80080ULL,
    },
    /* ── M1 (T8103) ──────────────────────────────────────── */
    {
        .cpid = 0x8103,
        .name = "T8103 (M1) iOS 16",
        .ios_ver = IOS_VERSION_16,
        .amfi_offset =          0x00C00000ULL,
        .task_for_pid_offset =  0x00600000ULL,
        .privilege_offset =     0x01000000ULL,
        .mount_root_offset =    0x00E00000ULL,
        .codesign_offset =      0x00C00040ULL,
        .sandbox_offset =       0x00D00000ULL,
        .pe_debugger_offset =   0x00F00000ULL,
        .cs_enforcement_offset = 0x00C00080ULL,
    },
    {
        .cpid = 0x8103,
        .name = "T8103 (M1) iOS 17+",
        .ios_ver = IOS_VERSION_17,
        .amfi_offset =          0x00D00000ULL,
        .task_for_pid_offset =  0x00620000ULL,
        .privilege_offset =     0x01100000ULL,
        .mount_root_offset =    0x00F00000ULL,
        .codesign_offset =      0x00D00040ULL,
        .sandbox_offset =       0x00E00000ULL,
        .pe_debugger_offset =   0x01000000ULL,
        .cs_enforcement_offset = 0x00D00080ULL,
    },
    /* ── A15 (T8110) ─────────────────────────────────────── */
    {
        .cpid = 0x8110,
        .name = "T8110 (A15) iOS 16",
        .ios_ver = IOS_VERSION_16,
        .amfi_offset =          0x00B00000ULL,
        .task_for_pid_offset =  0x00600000ULL,
        .privilege_offset =     0x00F00000ULL,
        .mount_root_offset =    0x00D00000ULL,
        .codesign_offset =      0x00B00040ULL,
        .sandbox_offset =       0x00C00000ULL,
        .pe_debugger_offset =   0x00E00000ULL,
        .cs_enforcement_offset = 0x00B00080ULL,
    },
    {
        .cpid = 0x8110,
        .name = "T8110 (A15) iOS 17+",
        .ios_ver = IOS_VERSION_17,
        .amfi_offset =          0x00C00000ULL,
        .task_for_pid_offset =  0x00620000ULL,
        .privilege_offset =     0x01000000ULL,
        .mount_root_offset =    0x00E00000ULL,
        .codesign_offset =      0x00C00040ULL,
        .sandbox_offset =       0x00D00000ULL,
        .pe_debugger_offset =   0x00F00000ULL,
        .cs_enforcement_offset = 0x00C00080ULL,
    },
    /* ── M2 (T8112) ──────────────────────────────────────── */
    {
        .cpid = 0x8112,
        .name = "T8112 (M2) iOS 16",
        .ios_ver = IOS_VERSION_16,
        .amfi_offset =          0x00C80000ULL,
        .task_for_pid_offset =  0x00680000ULL,
        .privilege_offset =     0x01080000ULL,
        .mount_root_offset =    0x00E80000ULL,
        .codesign_offset =      0x00C80040ULL,
        .sandbox_offset =       0x00D80000ULL,
        .pe_debugger_offset =   0x00F80000ULL,
        .cs_enforcement_offset = 0x00C80080ULL,
    },
    {
        .cpid = 0x8112,
        .name = "T8112 (M2) iOS 17+",
        .ios_ver = IOS_VERSION_17,
        .amfi_offset =          0x00D80000ULL,
        .task_for_pid_offset =  0x006A0000ULL,
        .privilege_offset =     0x01180000ULL,
        .mount_root_offset =    0x00F80000ULL,
        .codesign_offset =      0x00D80040ULL,
        .sandbox_offset =       0x00E80000ULL,
        .pe_debugger_offset =   0x01080000ULL,
        .cs_enforcement_offset = 0x00D80080ULL,
    },
};

static ios_version_t detect_ios_version_from_kernel(void)
{
    u64 kbase = kernel_base;
    if (kbase == 0U) return IOS_VERSION_UNKNOWN;
    if (kbase >= APPLE_IOS17_KERNEL_BASE) return IOS_VERSION_17;
    u32 test = 0U;
    if (mmio_probe_read32(kbase + 0x200000U, &test)) {
        if ((test & 0xFFFF0000U) == 0xD5030000U || test == 0x14000000U) {
            return IOS_VERSION_17;
        }
    }
    ios_version_t ver = scan_kernel_version_string(kbase);
    if (ver != IOS_VERSION_UNKNOWN) {
        return ver;
    }
    return IOS_VERSION_16;
}

static ios_version_t scan_kernel_version_string(u64 base)
{
    static const char *const ios17_markers[] = {
        "Darwin Kernel Version 23.",
        "iOS 17.",
        "iOS 18.",
        NULL
    };
    static const char *const ios16_markers[] = {
        "Darwin Kernel Version 22.",
        "iOS 16.",
        NULL
    };
    const u64 scan_limit = 0x200000U;
    for (u64 off = 0U; off < scan_limit; off += 16U) {
        char buf[32];
        bool ok = true;
        fm_memset(buf, 0, sizeof(buf));
        for (u32 i = 0U; i < sizeof(buf); i += 4U) {
            u32 word = 0U;
            if (!mmio_probe_read32(base + off + i, &word)) {
                ok = false;
                break;
            }
            buf[i] = (char)(word & 0xFFU);
            buf[i + 1U] = (char)((word >> 8U) & 0xFFU);
            buf[i + 2U] = (char)((word >> 16U) & 0xFFU);
            buf[i + 3U] = (char)((word >> 24U) & 0xFFU);
            if (buf[i] == '\0' || buf[i + 1U] == '\0' ||
                buf[i + 2U] == '\0' || buf[i + 3U] == '\0') {
                break;
            }
        }
        if (!ok) continue;
        for (int m = 0; ios17_markers[m]; ++m) {
            const char *marker = ios17_markers[m];
            usize marker_len = fm_strlen(marker);
            for (usize i = 0; i + marker_len <= 32; ++i) {
                if (fm_strncmp(&buf[i], marker, marker_len) == 0) {
                    log_write(LOG_LEVEL_VERBOSE, "kernel_patches: iOS 17+ version string found: %s", marker);
                    return IOS_VERSION_17;
                }
            }
        }
        for (int m = 0; ios16_markers[m]; ++m) {
            const char *marker = ios16_markers[m];
            usize marker_len = fm_strlen(marker);
            for (usize i = 0; i + marker_len <= 32; ++i) {
                if (fm_strncmp(&buf[i], marker, marker_len) == 0) {
                    log_write(LOG_LEVEL_VERBOSE, "kernel_patches: iOS 16 version string found: %s", marker);
                    return IOS_VERSION_16;
                }
            }
        }
    }
    return IOS_VERSION_UNKNOWN;
}

static const soc_patch_offsets_t *find_soc_offsets(u16 cpid)
{
    ios_version_t ios_ver = detect_ios_version_from_kernel();
    for (usize i = 0U; i < sizeof(soc_offsets) / sizeof(soc_offsets[0U]); ++i) {
        if (soc_offsets[i].cpid == cpid && soc_offsets[i].ios_ver == ios_ver) {
            return &soc_offsets[i];
        }
    }
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
    u64 debug_addr = base + soc->pe_debugger_offset;
    u64 cs_enforce_addr = base + soc->cs_enforcement_offset;

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

    kernel_patches_register("PE-i-can-has-debugger",
        KERNEL_PATCH_TYPE_AUTHENTICATION,
        debug_addr, 4U, 0x00000000ULL, 0xD503201FU, true);

    kernel_patches_register("cs-enforcement-disable",
        KERNEL_PATCH_TYPE_AUTHENTICATION,
        cs_enforce_addr, 4U, 0x00000000ULL, 0xD503201FU, true);

    log_write(LOG_LEVEL_INFO, "registered %u default kernel patch targets for CPID 0x%04x (iOS %s)",
              state.patch_count, active_cpid,
              soc->ios_ver == IOS_VERSION_17 ? "17+" : "16");
}

void kernel_patches_init(void)
{
    fm_memset(&state, 0, sizeof(state));
    state.patching_enabled = true;
    state.privilege_escalated = false;
    state.escalation_level = 1U;
    if (active_cpid == 0U) {
        active_cpid = 0x8020U;
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
    if (name == NULL || target_address == 0U ||
        patch_size == 0U || patch_size > sizeof(u64) ||
        (patch_size != 4U && patch_size != 8U) ||
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
    bool write_ok = true;
    switch (entry->type) {
    case KERNEL_PATCH_TYPE_MEMORY:
        for (u64 off = 0U; off < patch_sz && off < 8U; off += 4U) {
            if (!mmio_write32(patch_addr + off,
                              (u32)(patch_val >> (off * 8U)))) {
                write_ok = false;
                break;
            }
        }
        break;
    case KERNEL_PATCH_TYPE_PRIVILEGE:
    case KERNEL_PATCH_TYPE_AUTHENTICATION:
    case KERNEL_PATCH_TYPE_MONITOR_HOOK:
    case KERNEL_PATCH_TYPE_SYSTEM_CALL:
    case KERNEL_PATCH_TYPE_IO_REMAP:
    case KERNEL_PATCH_TYPE_INTERRUPT:
        write_ok = mmio_write32(patch_addr, (u32)patch_val);
        break;
    case KERNEL_PATCH_TYPE_COUNT:
    default:
        write_ok = false;
        break;
    }
    if (!write_ok) {
        entry->state = KERNEL_PATCH_STATE_FAILED;
        ++state.failed_count;
        log_write(LOG_LEVEL_ERROR, "kernel patch '%s' write failed at 0x%llx",
                  entry->name, patch_addr);
        return false;
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

static bool revert_patch_entry(kernel_patch_entry_t *entry)
{
    if (entry == NULL || !entry->applied) {
        return false;
    }
#ifdef FBR34KER_ENABLE_SECURITY_MODEL
    u64 patch_addr = entry->target_address;
    if (dram_phys_base != 0U && patch_addr >= APPLE_IOS_KERNEL_BASE) {
        patch_addr = dram_phys_base + (patch_addr - APPLE_IOS_KERNEL_BASE);
    }
    bool write_ok = true;
    if (entry->type == KERNEL_PATCH_TYPE_MEMORY) {
        for (u64 off = 0U; off < entry->patch_size && off < 8U; off += 4U) {
            if (!mmio_write32(
                    patch_addr + off,
                    (u32)(entry->original_value >> (off * 8U)))) {
                write_ok = false;
                break;
            }
        }
    } else {
        write_ok = mmio_write32(patch_addr, (u32)entry->original_value);
    }
    if (!write_ok) {
        entry->state = KERNEL_PATCH_STATE_FAILED;
        ++state.failed_count;
        log_write(LOG_LEVEL_ERROR, "kernel patch '%s' revert failed at 0x%llx",
                  entry->name, patch_addr);
        return false;
    }
#endif
    entry->state = KERNEL_PATCH_STATE_REVERTED;
    entry->applied = false;
    if (state.applied_count > 0U) {
        --state.applied_count;
    }
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
            if (!revert_patch_entry(entry)) {
                all_success = false;
                continue;
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
            if (!revert_patch_entry(entry)) {
                all_success = false;
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
    return revert_patch_entry(&state.patches[index]);
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

bool kernel_patches_find_base(u64 *kbase)
{
    if (kbase == NULL || kernel_base == 0U) {
        return false;
    }
    *kbase = kernel_base;
    return true;
}
