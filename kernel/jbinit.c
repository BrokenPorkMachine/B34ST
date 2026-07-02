#include "fbr34ker/jbinit.h"
#include "fbr34ker/apple_platform.h"
#include "fbr34ker/mmio.h"
#include "fbr34ker/string.h"
#include "fbr34ker/log.h"
#include "fbr34ker/event.h"
#include "fbr34ker/format.h"

#define DART_BASE_A12  0x8F0000000ULL
#define DART_SIZE      0x400000ULL
#define DART_BASE_A13  0x8F0000000ULL
#define DART_BASE_A14  0x8F0000000ULL
#define DART_BASE_A15  0x8F0000000ULL
#define DART_BASE_M1   0x8F0000000ULL
#define DART_BASE_M2   0x980000000ULL

#define PMGR_BASE_A12  0x8014E0000ULL
#define PMGR_BASE_A13  0x8014E0000ULL
#define PMGR_BASE_A14  0x8014E0000ULL
#define PMGR_BASE_M1   0x8014E0000ULL
#define PMGR_BASE_A15  0x8014E0000ULL
#define PMGR_BASE_M2   0x8014E0000ULL
#define PMGR_SIZE      0x20000ULL

#define DART_TCR_ENABLE     (1U << 0)
#define DART_TCR_BYPASS     (1U << 1)
#define DART_TCR_TTBR0_EN   (1U << 2)
#define DART_TCR_TTBR1_EN   (1U << 3)
#define DART_TCR_TG0_4K     (0U << 4)
#define DART_TCR_TG0_16K    (1U << 4)
#define DART_TCR_TG0_64K    (2U << 4)
#define DART_TCR_TG0_MASK   (3U << 4)
#define DART_TCR_TG1_4K     (0U << 6)
#define DART_TCR_TG1_16K    (1U << 6)
#define DART_TCR_TG1_64K    (2U << 6)
#define DART_TCR_TG1_MASK   (3U << 6)
#define DART_TCR_T0SZ_SHIFT 8
#define DART_TCR_T1SZ_SHIFT 12

#define DART_TTBR_ADDR_SHIFT 12
#define DART_TTBR_VALID    (1ULL << 0)

#define DART_TLB_CMD_FLUSH 1U
#define DART_TLB_CMD_BARRIER 2U

#define ART_ADDR_MASK 0xFFFFFFFFF000ULL

#define PMGR_PSRT_OFFSET   0x0ULL
#define PMGR_PSIST_OFFSET  0x10000ULL
#define PMGR_AICT_OFFSET   0x18000ULL
#define PMGR_PSRT_ENTRIES  128U
#define PMGR_PSRT_ENTRY_SIZE 16U

#define IBEC_CONNECT_TIMEOUT_US 5000000ULL
#define IBEC_POLL_INTERVAL_US   1000ULL

#define SEP_BASE_A12  0x82D000000ULL
#define SEP_BASE_A12X 0x82D000000ULL
#define SEP_BASE_A13  0x82E000000ULL
#define SEP_BASE_A14  0x82F000000ULL
#define SEP_BASE_M1   0x82D000000ULL
#define SEP_BASE_A15  0x82F000000ULL
#define SEP_BASE_M2   0x830000000ULL

#define SYS_REG_BASE_A12 0x8014E0000ULL
#define SYS_REG_BASE_A13 0x8014E0000ULL
#define SYS_REG_BASE_A14 0x8024E0000ULL
#define SYS_REG_BASE_M1  0x8024E0000ULL
#define SYS_REG_BASE_A15 0x8024E0000ULL
#define SYS_REG_BASE_M2  0x8024E0000ULL
#define SYS_REG_SIZE     0x1000ULL

#define SYS_REG_BOOT_MODE 0x0ULL
#define SYS_REG_CHIP_ID   0x4ULL
#define SYS_REG_BOARD_ID  0x8ULL
#define SYS_REG_DEVICE_ID 0xCULL

#define BOOT_MODE_DFU     0x1U
#define BOOT_MODE_RECOVERY 0x2U
#define BOOT_MODE_NORMAL  0x3U
#define BOOT_MODE_PONGO   0x4U
#define BOOT_MODE_RESTORE 0x5U

// SPDX-License-Identifier: BSD-2-Clause
static jbinit_status_t status;
static bool initialized;

static const char *state_names[] = {
    "uninitialized", "hardware-probed", "dart-configured",
    "pmgr-ready", "boot-mode-detected", "ibec-connected",
    "sep-available", "bootargs-ready", "ready", "failed",
};

static const char *boot_mode_names[] = {
    "unknown", "dfu", "recovery", "normal", "pongo", "restore",
};

static u64 dart_base_for_cpid(u16 cpid)
{
    switch (cpid) {
    case APPLE_A12_CPID:
    case APPLE_A12X_CPID:
    case APPLE_A12Z_CPID:
        return DART_BASE_A12;
    case APPLE_A13_CPID:
        return DART_BASE_A13;
    case APPLE_A14_CPID:
        return DART_BASE_A14;
    case APPLE_A15_CPID:
        return DART_BASE_A15;
    case APPLE_M1_CPID:
        return DART_BASE_M1;
    case APPLE_M2_CPID:
        return DART_BASE_M2;
    default:
        return DART_BASE_A12;
    }
}

static u64 pmgr_base_for_cpid(u16 cpid)
{
    switch (cpid) {
    case APPLE_A12_CPID:
    case APPLE_A12X_CPID:
    case APPLE_A12Z_CPID:
        return PMGR_BASE_A12;
    case APPLE_A13_CPID:
        return PMGR_BASE_A13;
    case APPLE_A14_CPID:
        return PMGR_BASE_A14;
    case APPLE_A15_CPID:
        return PMGR_BASE_A15;
    case APPLE_M1_CPID:
        return PMGR_BASE_M1;
    case APPLE_M2_CPID:
        return PMGR_BASE_M2;
    default:
        return PMGR_BASE_A12;
    }
}

static u64 sys_reg_base_for_cpid(u16 cpid)
{
    switch (cpid) {
    case APPLE_A12_CPID:
    case APPLE_A12X_CPID:
    case APPLE_A12Z_CPID:
    case APPLE_A13_CPID:
        return SYS_REG_BASE_A12;
    case APPLE_A14_CPID:
        return SYS_REG_BASE_A14;
    case APPLE_A15_CPID:
        return SYS_REG_BASE_A15;
    case APPLE_M1_CPID:
        return SYS_REG_BASE_M1;
    case APPLE_M2_CPID:
        return SYS_REG_BASE_M2;
    default:
        return SYS_REG_BASE_A12;
    }
}

static u64 sep_base_for_cpid(u16 cpid)
{
    switch (cpid) {
    case APPLE_A12_CPID:
    case APPLE_A12X_CPID:
    case APPLE_A12Z_CPID:
        return SEP_BASE_A12;
    case APPLE_A13_CPID:
        return SEP_BASE_A13;
    case APPLE_A14_CPID:
        return SEP_BASE_A14;
    case APPLE_A15_CPID:
        return SEP_BASE_A15;
    case APPLE_M1_CPID:
        return SEP_BASE_M1;
    case APPLE_M2_CPID:
        return SEP_BASE_M2;
    default:
        return SEP_BASE_A12;
    }
}

const char *jbinit_state_name(jbinit_state_t state)
{
    if (state >= JBINIT_STATE_FAILED) {
        return "unknown";
    }
    return state_names[state];
}

const char *jbinit_boot_mode_name(jbinit_boot_mode_t mode)
{
    if (mode >= JBINIT_BOOT_MODE_RESTORE) {
        return "unknown";
    }
    return boot_mode_names[mode];
}

bool jbinit_is_a12_plus(void)
{
    return status.hw.cpid >= APPLE_A12_CPID;
}

void jbinit_init(void)
{
    if (initialized) {
        return;
    }
    fm_memset(&status, 0, sizeof(status));
    status.state = JBINIT_STATE_UNINITIALIZED;
    status.hw.cpid = APPLE_A12_CPID;
    status.hw.boot_mode = JBINIT_BOOT_MODE_UNKNOWN;
    initialized = true;
    log_write(LOG_LEVEL_INFO, "jbinit: initialized");
    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE, "jbinit-init", 0U, 0U);
}

void jbinit_shutdown(void)
{
    if (!initialized) {
        return;
    }
    status.state = JBINIT_STATE_UNINITIALIZED;
    initialized = false;
    log_write(LOG_LEVEL_INFO, "jbinit: shutdown");
}

bool jbinit_ready(void)
{
    return initialized && status.state == JBINIT_STATE_READY;
}

bool jbinit_healthy(void)
{
    return initialized && status.state != JBINIT_STATE_FAILED;
}

jbinit_status_t jbinit_get_status(void)
{
    return status;
}

bool jbinit_set_security_model(bool enable)
{
    status.security_model = enable;
    log_write(LOG_LEVEL_INFO, "jbinit: security model %s",
              enable ? "ACTIVE" : "PENDING");
    return true;
}

bool jbinit_is_security_model_active(void)
{
    return status.security_model;
}

#define BOOT_ARGS_SEARCH_START_OFFSET 0x100000ULL
#define BOOT_ARGS_SEARCH_END_OFFSET   0x200000ULL

static u64 scan_for_boot_args(u64 start, u64 end)
{
    for (u64 addr = start; addr < end && addr < (start + 0x400000ULL); addr += 0x10ULL) {
        u32 magic = 0U;
        if (!mmio_probe_read32(addr, &magic)) continue;
        if (magic == 0xBA696F53U || magic == 0x626F6F74U) {
            return addr;
        }
    }
    return 0U;
}

bool jbinit_probe_hardware(void)
{
    if (!initialized) {
        return false;
    }

    const apple_soc_config_t *soc = apple_soc_for_cpid(status.hw.cpid);
    if (soc == NULL) {
        log_write(LOG_LEVEL_WARN, "jbinit: unknown SoC CPID 0x%04x, using defaults",
                  status.hw.cpid);
        status.hw.dram_base = 0x800000000ULL;
        status.hw.dram_size = 0x80000000ULL;
        status.hw.uart_base = 0x0ULL;
    } else {
        status.hw.dram_base = soc->dram_base;
        status.hw.dram_size = soc->dram_size;
        status.hw.uart_base = soc->uart_base;
        status.hw.cpid = soc->cpid;
        status.hw.board_id = soc->board_id;
        log_write(LOG_LEVEL_INFO, "jbinit: SoC %s (CPID 0x%04x, board 0x%04x)",
                  soc->soc_name, soc->cpid, soc->board_id);
    }

    status.hw.dart_base = dart_base_for_cpid(status.hw.cpid);
    status.hw.pmgr_base = pmgr_base_for_cpid(status.hw.cpid);
    status.hw.sep_base = sep_base_for_cpid(status.hw.cpid);

    status.hw.boot_args_phys = scan_for_boot_args(
        status.hw.dram_base + BOOT_ARGS_SEARCH_START_OFFSET,
        status.hw.dram_base + BOOT_ARGS_SEARCH_END_OFFSET);

    log_write(LOG_LEVEL_VERBOSE, "jbinit: DRAM 0x%llx (%llu MB)",
              status.hw.dram_base, status.hw.dram_size / (1024U * 1024U));
    log_write(LOG_LEVEL_VERBOSE, "jbinit: DART at 0x%llx, PMGR at 0x%llx",
              status.hw.dart_base, status.hw.pmgr_base);

    status.state = JBINIT_STATE_HARDWARE_PROBED;
    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE, "jbinit-probe", 0U, 0U);
    return true;
}

bool jbinit_detect_boot_mode(void)
{
    if (!initialized || status.state < JBINIT_STATE_HARDWARE_PROBED) {
        return false;
    }

    u64 sys_reg_base = sys_reg_base_for_cpid(status.hw.cpid);
    u32 boot_mode_val = 0U;

    if (mmio_probe_read32(sys_reg_base + SYS_REG_BOOT_MODE, &boot_mode_val)) {
        switch (boot_mode_val) {
        case BOOT_MODE_DFU:
            status.hw.boot_mode = JBINIT_BOOT_MODE_DFU;
            break;
        case BOOT_MODE_RECOVERY:
            status.hw.boot_mode = JBINIT_BOOT_MODE_RECOVERY;
            break;
        case BOOT_MODE_NORMAL:
            status.hw.boot_mode = JBINIT_BOOT_MODE_NORMAL;
            break;
        case BOOT_MODE_PONGO:
            status.hw.boot_mode = JBINIT_BOOT_MODE_PONGO;
            break;
        case BOOT_MODE_RESTORE:
            status.hw.boot_mode = JBINIT_BOOT_MODE_RESTORE;
            break;
        default:
            status.hw.boot_mode = JBINIT_BOOT_MODE_UNKNOWN;
            break;
        }
        log_write(LOG_LEVEL_INFO, "jbinit: boot mode = %s (reg 0x%x)",
                  jbinit_boot_mode_name(status.hw.boot_mode), boot_mode_val);
    } else {
        u32 usb_test = 0U;
        const apple_soc_config_t *soc = apple_soc_for_cpid(status.hw.cpid);
        if (soc != NULL && mmio_probe_read32(soc->usb_dwc3_base, &usb_test) &&
            usb_test != 0U && usb_test != 0xFFFFFFFFU) {
            status.hw.boot_mode = JBINIT_BOOT_MODE_DFU;
            log_write(LOG_LEVEL_INFO, "jbinit: USB DWC3 active, assuming DFU mode");
        } else {
            status.hw.boot_mode = JBINIT_BOOT_MODE_NORMAL;
            log_write(LOG_LEVEL_INFO, "jbinit: no boot mode register, assuming normal boot");
        }
    }

    status.state = JBINIT_STATE_BOOT_MODE_DETECTED;
    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE, "jbinit-boot-mode",
                            (u64)status.hw.boot_mode, 0U);
    return true;
}

bool jbinit_configure_dart(jbinit_dart_device_t device)
{
    if (!initialized || status.hw.dart_base == 0U) {
        return false;
    }
    if (device >= JBINIT_DART_DEVICE_MAX) {
        return false;
    }

    u64 dart_base = status.hw.dart_base + ((u64)device * DART_SIZE);
    jbinit_dart_config_t *cfg = &status.dart[device];

    cfg->base = dart_base;
    cfg->size = DART_SIZE;
    cfg->tcr = DART_TCR_ENABLE | DART_TCR_TTBR0_EN |
               DART_TCR_TG0_4K | (25U << DART_TCR_T0SZ_SHIFT);
    cfg->nsid = (u32)device;
    cfg->bypass_enabled = true;
    cfg->translation_enabled = false;

    u32 tcr_val = cfg->tcr;
    mmio_write32(dart_base + 0x20U, tcr_val);

    for (u32 i = 0U; i < JBINIT_DART_NUM_TTBR; ++i) {
        mmio_write32(dart_base + 0x40U + i * 8U, 0U);
        mmio_write32(dart_base + 0x44U + i * 8U, 0U);
    }

    mmio_write32(dart_base + 0x200U, DART_TLB_CMD_FLUSH);
    mmio_write32(dart_base + 0x200U, DART_TLB_CMD_BARRIER);

    cfg->initialized = true;
    log_write(LOG_LEVEL_INFO, "jbinit: DART device %u configured at 0x%llx (bypass)",
              (u32)device, dart_base);

    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE, "jbinit-dart",
                            (u64)device, 0U);
    return true;
}

bool jbinit_configure_all_dart(void)
{
    if (!initialized) {
        return false;
    }

    u32 configured = 0U;
    for (u32 i = 0U; i < (u32)JBINIT_DART_DEVICE_MAX; ++i) {
        if (jbinit_configure_dart((jbinit_dart_device_t)i)) {
            configured++;
        }
    }

    if (configured > 0U) {
        status.state = JBINIT_STATE_DART_CONFIGURED;
        log_write(LOG_LEVEL_INFO, "jbinit: %u DART devices configured", configured);
    } else {
        log_write(LOG_LEVEL_WARN, "jbinit: no DART devices configured");
    }

    return configured > 0U;
}

bool jbinit_init_pmgr(void)
{
    if (!initialized || status.hw.pmgr_base == 0U) {
        return false;
    }

    status.pmgr.pmgr_base = status.hw.pmgr_base;
    status.pmgr.psrt_base = status.hw.pmgr_base + PMGR_PSRT_OFFSET;
    status.pmgr.psist_base = status.hw.pmgr_base + PMGR_PSIST_OFFSET;
    status.pmgr.aict_base = status.hw.pmgr_base + PMGR_AICT_OFFSET;

    u32 psrt_header = 0U;
    u32 domain_found = 0U;
    if (mmio_probe_read32(status.pmgr.psrt_base, &psrt_header)) {
        for (u32 i = 0U; i < PMGR_PSRT_ENTRIES; ++i) {
            u64 entry_addr = status.pmgr.psrt_base +
                             (u64)(i + 1U) * PMGR_PSRT_ENTRY_SIZE;
            u32 entry_magic = 0U;
            if (!mmio_probe_read32(entry_addr, &entry_magic)) {
                break;
            }
            if (entry_magic == 0U || entry_magic == 0xFFFFFFFFU) {
                continue;
            }
            domain_found++;
        }
    }

    status.pmgr.domain_count = domain_found;
    status.pmgr.initialized = true;
    status.state = JBINIT_STATE_PMGR_READY;

    log_write(LOG_LEVEL_INFO, "jbinit: PMGR at 0x%llx, %u power domains",
              status.hw.pmgr_base, domain_found);
    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE, "jbinit-pmgr",
                            (u64)domain_found, 0U);
    return true;
}

bool jbinit_detect_sep(void)
{
    if (!initialized || status.hw.sep_base == 0U) {
        return false;
    }

    u32 test_word = 0U;
    bool sep_detected = mmio_probe_read32(status.hw.sep_base, &test_word) &&
                        test_word != 0U && test_word != 0xFFFFFFFFU;

    if (sep_detected) {
        status.state = JBINIT_STATE_SEP_AVAILABLE;
        log_write(LOG_LEVEL_INFO, "jbinit: SEP detected at 0x%llx",
                  status.hw.sep_base);
    } else {
        log_write(LOG_LEVEL_WARN, "jbinit: SEP not detected at 0x%llx",
                  status.hw.sep_base);
    }

    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE, "jbinit-sep",
                            sep_detected ? 1U : 0U, 0U);
    return sep_detected;
}

bool jbinit_parse_boot_args(void)
{
    if (!initialized || status.hw.boot_args_phys == 0U) {
        return false;
    }

    apple_boot_args_t hdr;
    fm_memset(&hdr, 0, sizeof(hdr));
    for (u32 i = 0U; i < sizeof(hdr); i += 4U) {
        u32 word = 0U;
        if (mmio_probe_read32(status.hw.boot_args_phys + i, &word)) {
            ((u8 *)&hdr)[i] = (u8)(word & 0xFFU);
            ((u8 *)&hdr)[i + 1] = (u8)((word >> 8) & 0xFFU);
            ((u8 *)&hdr)[i + 2] = (u8)((word >> 16) & 0xFFU);
            ((u8 *)&hdr)[i + 3] = (u8)((word >> 24) & 0xFFU);
        }
    }

    usize copy_len = fm_strlen((const char *)hdr.boot_args);
    if (copy_len >= JBINIT_MAX_BOOTARGS) {
        copy_len = JBINIT_MAX_BOOTARGS - 1U;
    }
    fm_memcpy(status.boot_args, hdr.boot_args, copy_len);
    status.boot_args[copy_len] = '\0';

    if (!status.security_model) {
        log_write(LOG_LEVEL_INFO, "jbinit: boot-args staged (not written)");
    }

    status.state = JBINIT_STATE_BOOTARGS_READY;
    log_write(LOG_LEVEL_INFO, "jbinit: boot-args parsed: %.128s", status.boot_args);
    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE, "jbinit-bootargs", 0U, 0U);
    return true;
}

bool jbinit_set_boot_args(const char *args)
{
    if (args == NULL || args[0] == '\0') {
        return false;
    }

    fm_strlcpy(status.boot_args, args, JBINIT_MAX_BOOTARGS);
    log_write(LOG_LEVEL_INFO, "jbinit: boot-args set to: %s", args);
    return true;
}

bool jbinit_connect_ibec(void)
{
    if (!initialized || status.hw.boot_mode != JBINIT_BOOT_MODE_DFU) {
        return false;
    }

    log_write(LOG_LEVEL_INFO, "jbinit: iBEC connection not required (DFU mode detected)");
    status.state = JBINIT_STATE_IBEC_CONNECTED;
    return true;
}

bool jbinit_run_all(void)
{
    if (!initialized) {
        return false;
    }

    if (status.state < JBINIT_STATE_HARDWARE_PROBED) {
        if (!jbinit_probe_hardware()) {
            status.state = JBINIT_STATE_FAILED;
            return false;
        }
    }

    if (status.state < JBINIT_STATE_BOOT_MODE_DETECTED) {
        if (!jbinit_detect_boot_mode()) {
            log_write(LOG_LEVEL_WARN, "jbinit: boot mode detection failed, continuing");
        }
    }

    if (status.state < JBINIT_STATE_DART_CONFIGURED) {
        jbinit_configure_all_dart();
    }

    if (status.state < JBINIT_STATE_PMGR_READY) {
        jbinit_init_pmgr();
    }

    if (status.state < JBINIT_STATE_SEP_AVAILABLE) {
        jbinit_detect_sep();
    }

    if (status.hw.boot_args_phys != 0U && status.state < JBINIT_STATE_BOOTARGS_READY) {
        jbinit_parse_boot_args();
    }

    status.state = JBINIT_STATE_READY;
    log_write(LOG_LEVEL_INFO, "jbinit: initialization complete");
    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE, "jbinit-ready", 1U, 0U);
    return true;
}


