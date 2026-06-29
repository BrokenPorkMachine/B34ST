#include "fbr34ker/jailbreak.h"
#include "fbr34ker/mmu.h"
#include "fbr34ker/kernel_patches.h"
#include "fbr34ker/secure_boot_bypass.h"
#include "fbr34ker/trust_cache.h"
#include "fbr34ker/usbliter8_exploit.h"
#include "fbr34ker/persistence.h"
#include "fbr34ker/apple_platform.h"
#include "fbr34ker/mmio.h"
#include "fbr34ker/string.h"
#include "fbr34ker/log.h"
#include "fbr34ker/event.h"
#include "fbr34ker/format.h"
#include "fbr34ker/exception.h"

#define LC_SEGMENT_64 0x19U
#define LC_MAIN       0x80000028U

static jailbreak_status_t status;
static jailbreak_progress_callback_t progress_cb;
static void *progress_ctx;

#define KERNELCACHE_MAGIC_IMG4 0x34676d49U
#define KERNELCACHE_MAGIC_IM4P 0x70346d49U
#define KERNELCACHE_MAGIC_FAT_BIN 0xBEBAFECAULL
#define APPLE_BOOT_ARGS_MAGIC 0xBA696F53ULL
#define APPLE_BOOT_ARGS_MAGIC_V2 0x626F6F74ULL
#define APPLE_DEVICE_TREE_MAGIC 0xD00DF000U
#define APPLE_KERNELCACHE_SEARCH_RANGE_A12 (0x800000000ULL)
#define APPLE_KERNELCACHE_SEARCH_END_A12  (0x900000000ULL)
#define APPLE_KERNELCACHE_SEARCH_RANGE_A14 (0x800000000ULL)
#define APPLE_KERNELCACHE_SEARCH_END_A14  (0xC00000000ULL)
#define APPLE_KERNELCACHE_SEARCH_RANGE_M1  (0x800000000ULL)
#define APPLE_KERNELCACHE_SEARCH_END_M1   (0x1800000000ULL)
#define APPLE_KERNELCACHE_SEARCH_RANGE_QEMU (0x40000000ULL)
#define APPLE_KERNELCACHE_SEARCH_END_QEMU  (0x80000000ULL)
#define SEP_BASE_A12  0x82D000000ULL
#define SEP_BASE_A12X 0x82D000000ULL
#define SEP_BASE_A13  0x82E000000ULL
#define SEP_BASE_A14  0x82F000000ULL
#define SEP_BASE_M1   0x82D000000ULL
#define SEP_BASE_A15  0x82F000000ULL
#define SEP_BASE_M2   0x830000000ULL

typedef struct {
    u32 magic;
    u32 header_size;
    u64 kernel_base;
    u64 kernel_size;
    u64 entry_point;
    u8 boot_args[2048];
    u64 device_tree_base;
    u64 device_tree_size;
    u64 ramdisk_base;
    u64 ramdisk_size;
} PACKED apple_boot_args_header_t;

typedef struct {
    u32 magic;
    u32 chip_id;
    u32 sdk_version;
    u32 epoch;
    u64 kernel_size;
    u64 kernel_base;
    u64 entry_point;
    u64 boot_args_addr;
} PACKED kernel_prelink_header_t;

static void report_progress(const char *stage, u32 percent)
{
    if (progress_cb != NULL) {
        progress_cb(stage, percent, progress_ctx);
    }
    log_write(LOG_LEVEL_INFO, "jailbreak: [%u%%] %s", percent, stage);
    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE, stage, percent, 0U);
}

void jailbreak_init(void)
{
    fm_memset(&status, 0, sizeof(status));
    status.state = JAILBREAK_STATE_INACTIVE;
    status.kernel.kaslr_slide = JAILBREAK_KASLR_SLIDE_UNKNOWN;
    status.kernel.boot_args_override[0] = '\0';
    progress_cb = NULL;
    progress_ctx = NULL;
    log_write(LOG_LEVEL_INFO, "jailbreak: initialized");
    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE, "jailbreak-init", 0U, 0U);
}

void jailbreak_shutdown(void)
{
    status.state = JAILBREAK_STATE_INACTIVE;
}

bool jailbreak_ready(void)
{
    return status.state >= JAILBREAK_STATE_SECURITY_MODEL_ACTIVE;
}

bool jailbreak_set_security_model(bool enable)
{
    status.security_model = enable;
    status.state = enable
        ? JAILBREAK_STATE_SECURITY_MODEL_ACTIVE
        : JAILBREAK_STATE_SECURITY_MODEL_PENDING;
    log_write(LOG_LEVEL_INFO, "jailbreak: security model %s",
              enable ? "ACTIVE (writes enabled)" : "PENDING (state model only)");
    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE, "security-model",
                            enable ? 1U : 0U, 0U);
    return true;
}

bool jailbreak_is_security_model_active(void)
{
    return status.security_model;
}

bool jailbreak_bypass_pac(void)
{
    report_progress("pac-bypass", 15U);
    if (!mmu_pac_strip_all()) {
        log_write(LOG_LEVEL_ERROR, "jailbreak: PAC bypass failed");
        return false;
    }
    status.bypass_count++;
    log_write(LOG_LEVEL_INFO, "jailbreak: PAC bypassed (pointer auth disabled)");

    if (status.security_model) {
        u64 apiakey_lo = 0U, apiakey_hi = 0U;
        __asm__ volatile("mrs %0, S3_0_C2_C1_0" : "=r"(apiakey_lo));
        __asm__ volatile("mrs %0, S3_0_C2_C1_1" : "=r"(apiakey_hi));
        log_write(LOG_LEVEL_VERBOSE, "jailbreak: APIAKey_EL1=0x%016llx%016llx",
                  apiakey_hi, apiakey_lo);
    }
    return true;
}

bool jailbreak_bypass_aprr(void)
{
    report_progress("aprr-bypass", 30U);
    if (!mmu_aprr_bypass()) {
        log_write(LOG_LEVEL_ERROR, "jailbreak: APRR/PPL bypass failed");
        return false;
    }
    status.bypass_count++;
    log_write(LOG_LEVEL_INFO, "jailbreak: APRR/PPL bypassed");
    return true;
}

bool jailbreak_bypass_wxn(void)
{
    report_progress("wxn-bypass", 40U);
    if (!mmu_wxn_disable()) {
        log_write(LOG_LEVEL_ERROR, "jailbreak: W^X bypass failed");
        return false;
    }
    status.bypass_count++;
    log_write(LOG_LEVEL_INFO, "jailbreak: W^X bypassed (SCTLR_EL1.WXN cleared)");
    return true;
}

bool jailbreak_apply_all_security_bypasses(void)
{
    log_write(LOG_LEVEL_INFO, "jailbreak: applying all security bypasses");
    report_progress("security-bypasses", 10U);

    if (!jailbreak_bypass_pac()) {
        status.state = JAILBREAK_STATE_FAILED;
        return false;
    }
    status.state = JAILBREAK_STATE_PAC_BYPASSED;

    if (!jailbreak_bypass_aprr()) {
        status.state = JAILBREAK_STATE_FAILED;
        return false;
    }
    status.state = JAILBREAK_STATE_APRR_BYPASSED;

    if (!jailbreak_bypass_wxn()) {
        status.state = JAILBREAK_STATE_FAILED;
        return false;
    }
    status.state = JAILBREAK_STATE_WXN_BYPASSED;

    log_write(LOG_LEVEL_INFO, "jailbreak: all security bypasses applied successfully");
    report_progress("bypasses-complete", 50U);
    return true;
}

static u64 scan_for_kernelcache(u64 start, u64 end)
{
    for (u64 addr = start; addr < end; addr += 0x1000ULL) {
        u32 magic = 0U;
        if (!mmio_probe_read32(addr, &magic)) continue;
        if (magic == KERNELCACHE_MAGIC_IMG4 || magic == KERNELCACHE_MAGIC_IM4P) {
            return addr;
        }
    }
    return 0U;
}

bool jailbreak_detect_kaslr_slide(u64 kernelcache_phys, u64 kernelcache_size)
{
    if (kernelcache_phys == 0U || kernelcache_size == 0U) {
        status.kernel.kaslr_slide = JAILBREAK_KASLR_SLIDE_UNKNOWN;
        return false;
    }

    u64 slide = 0U;
    bool found = false;
    u64 kern_base_used = APPLE_IOS_KERNEL_BASE;

    for (u64 offset = 0U; offset < kernelcache_size && offset < (256U * 1024U * 1024U); offset += 4U) {
        u32 word = 0U;
        if (!mmio_probe_read32(kernelcache_phys + offset, &word)) continue;
        if (word != 0xFEEDFACF && word != 0xFEEDFACE) continue;

        u32 hdr[8];
        fm_memset(hdr, 0, sizeof(hdr));
        for (u32 i = 0U; i < 8U && (offset + i * 4U) < kernelcache_size; ++i) {
            mmio_probe_read32(kernelcache_phys + offset + i * 4U, &hdr[i]);
        }
        u32 ncmds = hdr[4];
        if (ncmds == 0U || ncmds > 64U) { break; }
        u64 cmd_off = kernelcache_phys + offset + 32U;
        u32 lc_found = 0U;
        u64 vmaddr = 0U;
        for (u32 ci = 0U; ci < ncmds && ci < 64U; ++ci) {
            u32 cmd_type = 0U, cmd_size = 0U;
            if (!mmio_probe_read32(cmd_off, &cmd_type)) break;
            if (!mmio_probe_read32(cmd_off + 4U, &cmd_size)) break;
            if (cmd_size < 8U || cmd_size > 4096U) break;
            if (cmd_type == LC_SEGMENT_64) {
                u32 seg_words[18];
                fm_memset(seg_words, 0, sizeof(seg_words));
                for (u32 i = 0U; i < 18U; ++i) {
                    mmio_probe_read32(cmd_off + i * 4U, &seg_words[i]);
                }
                u64 svmaddr = (u64)seg_words[6] | ((u64)seg_words[7] << 32);
                u64 sfsize = (u64)seg_words[14] | ((u64)seg_words[15] << 32);
                if (svmaddr >= 0xFFFFFFF007000000ULL && sfsize > 0U) {
                    vmaddr = svmaddr;
                    lc_found = 1U;
                    break;
                }
            }
            cmd_off += cmd_size;
        }

        if (lc_found != 0U && vmaddr != 0U) {
            u64 base_a16 = APPLE_IOS_KERNEL_BASE & 0xFFFFFFFFFFF00000ULL;
            u64 base_a17 = APPLE_IOS17_KERNEL_BASE & 0xFFFFFFFFFFF00000ULL;
            if (vmaddr >= base_a17 && (vmaddr - base_a17) < 0x40000000ULL) {
                slide = vmaddr - base_a17;
                kern_base_used = APPLE_IOS17_KERNEL_BASE;
                found = true;
            } else if (vmaddr >= base_a16 && (vmaddr - base_a16) < 0x40000000ULL) {
                slide = vmaddr - base_a16;
                found = true;
            }
            slide &= 0xFFFFFFFFFFF00000ULL;
        }
        break;
    }

    if (!found) {
        status.kernel.kaslr_slide = JAILBREAK_KASLR_SLIDE_UNKNOWN;
        log_write(LOG_LEVEL_WARN, "jailbreak: KASLR slide not detected");
        return false;
    }

    status.kernel.kaslr_slide = slide;
    status.kernel.kernel_base_virt = kern_base_used + slide;
    status.kernel.kernel_base_phys = kernelcache_phys;
    status.kernel.kernelcache_phys = kernelcache_phys;
    status.kernel.kernelcache_size = kernelcache_size;
    status.state = JAILBREAK_STATE_KASLR_DETECTED;

    log_write(LOG_LEVEL_INFO, "jailbreak: KASLR slide = 0x%llx", slide);
    log_write(LOG_LEVEL_INFO, "jailbreak: kernel base (0x%llx) virt = 0x%llx",
              kern_base_used, status.kernel.kernel_base_virt);
    log_write(LOG_LEVEL_INFO, "jailbreak: kernel base phys = 0x%llx",
              status.kernel.kernel_base_phys);
    report_progress("kaslr-detected", 60U);
    return true;
}

bool jailbreak_detect_kernel(u64 kernelcache_phys, u64 kernelcache_size)
{
    if (kernelcache_phys == 0U || kernelcache_size == 0U) {
        kernelcache_phys = scan_for_kernelcache(APPLE_KERNELCACHE_SEARCH_RANGE_A12,
                                                 APPLE_KERNELCACHE_SEARCH_END_A12);
        if (kernelcache_phys == 0U) {
            kernelcache_phys = scan_for_kernelcache(APPLE_KERNELCACHE_SEARCH_RANGE_A14,
                                                     APPLE_KERNELCACHE_SEARCH_END_A14);
        }
        if (kernelcache_phys == 0U) {
            kernelcache_phys = scan_for_kernelcache(APPLE_KERNELCACHE_SEARCH_RANGE_M1,
                                                     APPLE_KERNELCACHE_SEARCH_END_M1);
        }
        if (kernelcache_phys == 0U) {
            kernelcache_phys = scan_for_kernelcache(APPLE_KERNELCACHE_SEARCH_RANGE_QEMU,
                                                     APPLE_KERNELCACHE_SEARCH_END_QEMU);
        }
        if (kernelcache_phys == 0U) {
            log_write(LOG_LEVEL_WARN, "jailbreak: no kernelcache found in DRAM");
            return false;
        }
        kernelcache_size = JAILBREAK_KERNELCACHE_MAX_SIZE;
    }

    status.kernel.kernelcache_phys = kernelcache_phys;
    status.kernel.kernelcache_size = kernelcache_size;
    log_write(LOG_LEVEL_INFO, "jailbreak: kernelcache at phys 0x%llx (%llu MB)",
              kernelcache_phys, kernelcache_size / (1024U * 1024U));

    if (!jailbreak_detect_kaslr_slide(kernelcache_phys, kernelcache_size)) {
        status.kernel.kernel_base_virt = APPLE_IOS_KERNEL_BASE;
        status.kernel.kernel_base_phys = kernelcache_phys;
    }

    u64 entry = 0U;
    u32 hdr_words[8];
    fm_memset(hdr_words, 0, sizeof(hdr_words));
    for (u32 i = 0U; i < 8U; ++i) {
        mmio_probe_read32(kernelcache_phys + i * 4U, &hdr_words[i]);
    }
    u32 ncmds = hdr_words[4];
    u64 cmd_off = kernelcache_phys + 32U;
    for (u32 ci = 0U; ci < ncmds; ++ci) {
        u32 cmd_type = 0U, cmd_size = 0U;
        if (!mmio_probe_read32(cmd_off, &cmd_type)) break;
        if (!mmio_probe_read32(cmd_off + 4U, &cmd_size)) break;
        if (cmd_size < 8U || cmd_size > 4096U) break;
        if (cmd_type == LC_MAIN) {
            u32 entry_lo = 0U, entry_hi = 0U;
            mmio_probe_read32(cmd_off + 8U, &entry_lo);
            mmio_probe_read32(cmd_off + 12U, &entry_hi);
            entry = (u64)entry_lo | ((u64)entry_hi << 32);
            break;
        }
        cmd_off += cmd_size;
    }

    if (entry == 0U) {
        status.kernel.kernel_entry = status.kernel.kernel_base_phys + 0x8000U;
        log_write(LOG_LEVEL_WARN, "jailbreak: LC_MAIN not found, using default entry offset");
    } else {
        status.kernel.kernel_entry = kernelcache_phys + entry;
        log_write(LOG_LEVEL_INFO, "jailbreak: kernel entry at phys 0x%llx",
                  status.kernel.kernel_entry);
    }

    status.state = JAILBREAK_STATE_KERNEL_LOADED;
    report_progress("kernel-detected", 70U);
    return true;
}

static u64 scan_for_boot_args(u64 start, u64 end)
{
    for (u64 addr = start; addr < end && addr < (start + 0x400000ULL); addr += 0x10ULL) {
        u32 magic = 0U;
        if (!mmio_probe_read32(addr, &magic)) continue;
        if (magic == APPLE_BOOT_ARGS_MAGIC || magic == APPLE_BOOT_ARGS_MAGIC_V2) {
            return addr;
        }
    }
    return 0U;
}

bool jailbreak_parse_boot_args(u64 boot_args_addr)
{
    if (boot_args_addr == 0U) {
        if (status.kernel.kernelcache_phys != 0U) {
            boot_args_addr = scan_for_boot_args(
                status.kernel.kernelcache_phys,
                status.kernel.kernelcache_phys + status.kernel.kernelcache_size);
        }
        if (boot_args_addr == 0U && status.kernel.kernel_base_phys != 0U) {
            boot_args_addr = scan_for_boot_args(
                status.kernel.kernel_base_phys + 0x80000ULL,
                status.kernel.kernel_base_phys + 0x200000ULL);
        }
        if (boot_args_addr == 0U) {
            boot_args_addr = APPLE_KERNEL_PRELOAD_BASE + 0x100000ULL;
        }
    }
    status.kernel.boot_args_phys = boot_args_addr;

    apple_boot_args_header_t hdr;
    fm_memset(&hdr, 0, sizeof(hdr));
    for (u32 i = 0U; i < sizeof(hdr); i += 4U) {
        u32 word = 0U;
        if (mmio_probe_read32(boot_args_addr + i, &word)) {
            ((u8 *)&hdr)[i] = (u8)(word & 0xFF);
            ((u8 *)&hdr)[i + 1] = (u8)((word >> 8) & 0xFF);
            ((u8 *)&hdr)[i + 2] = (u8)((word >> 16) & 0xFF);
            ((u8 *)&hdr)[i + 3] = (u8)((word >> 24) & 0xFF);
        }
    }

    log_write(LOG_LEVEL_INFO, "jailbreak: boot args at phys 0x%llx", boot_args_addr);
    log_write(LOG_LEVEL_VERBOSE, "jailbreak: boot-args string: %.128s", hdr.boot_args);
    return true;
}

bool jailbreak_inject_boot_args(const char *custom_args)
{
    if (custom_args == NULL || custom_args[0] == '\0') {
        custom_args = "-s amfi_get_out_of_my_way=1 cs_enforcement_disable=1 keepsyms=1 debug=0x2014 wdt=0";
    }

    if (status.kernel.boot_args_phys == 0U) {
        if (!jailbreak_parse_boot_args(0U)) {
            return false;
        }
    }

    fm_strlcpy(status.kernel.boot_args_override, custom_args,
               sizeof(status.kernel.boot_args_override));
    status.kernel.boot_args_modified = true;

    if (status.security_model) {
        apple_boot_args_header_t hdr;
        fm_memset(&hdr, 0, sizeof(hdr));
        for (u32 i = 0U; i < sizeof(hdr); i += 4U) {
            u32 word = 0U;
            mmio_probe_read32(status.kernel.boot_args_phys + i, &word);
            ((u8 *)&hdr)[i] = (u8)(word & 0xFF);
            ((u8 *)&hdr)[i + 1] = (u8)((word >> 8) & 0xFF);
            ((u8 *)&hdr)[i + 2] = (u8)((word >> 16) & 0xFF);
            ((u8 *)&hdr)[i + 3] = (u8)((word >> 24) & 0xFF);
        }

        usize arg_len = fm_strlen(custom_args);
        usize copy_len = arg_len < sizeof(hdr.boot_args) ? arg_len : sizeof(hdr.boot_args) - 1U;
        for (u32 i = 0U; i < copy_len; ++i) {
            hdr.boot_args[i] = custom_args[i];
        }
        hdr.boot_args[copy_len] = '\0';

        u64 addr = status.kernel.boot_args_phys;
        for (u32 i = 0U; i < sizeof(hdr); i += 4U) {
            u32 word = (u32)((u8 *)&hdr)[i] |
                      ((u32)((u8 *)&hdr)[i + 1] << 8) |
                      ((u32)((u8 *)&hdr)[i + 2] << 16) |
                      ((u32)((u8 *)&hdr)[i + 3] << 24);
            mmio_write32(addr + i, word);
        }
        log_write(LOG_LEVEL_INFO, "jailbreak: boot-args injected (security model)");
    } else {
        log_write(LOG_LEVEL_INFO, "jailbreak: boot-args staged (not written, no security model)");
    }

    status.state = JAILBREAK_STATE_BOOTARGS_INJECTED;
    report_progress("bootargs-injected", 80U);
    return true;
}

bool jailbreak_detect_sep(u64 sep_mmio_base)
{
    if (sep_mmio_base == 0U) {
        u64 bases[] = {SEP_BASE_M2, SEP_BASE_A15, SEP_BASE_A14, SEP_BASE_A13,
                       SEP_BASE_M1, SEP_BASE_A12X, SEP_BASE_A12, 0U};
        for (u32 i = 0U; bases[i] != 0U; ++i) {
            u32 test = 0U;
            if (mmio_probe_read32(bases[i], &test) && test != 0U && test != 0xFFFFFFFFU) {
                sep_mmio_base = bases[i];
                break;
            }
        }
        if (sep_mmio_base == 0U) {
            sep_mmio_base = SEP_BASE_A12;
        }
    }

    status.sep.sep_base = sep_mmio_base;
    status.sep.sep_mailbox = sep_mmio_base + 0x10000U;
    status.sep.sep_response = sep_mmio_base + 0x20000U;

    u32 test_word = 0U;
    if (mmio_probe_read32(sep_mmio_base, &test_word)) {
        status.sep.sep_available = true;
        log_write(LOG_LEVEL_INFO, "jailbreak: SEP detected at 0x%llx", sep_mmio_base);
    } else {
        status.sep.sep_available = false;
        log_write(LOG_LEVEL_WARN, "jailbreak: SEP not detected at 0x%llx", sep_mmio_base);
    }

    status.sep.sep_initialized = true;
    status.state = JAILBREAK_STATE_SEP_READY;
    report_progress("sep-ready", 85U);
    return true;
}

bool jailbreak_boot_kernel(u64 entry_point)
{
    if (entry_point == 0U) {
        entry_point = status.kernel.kernel_entry;
    }
    if (entry_point == 0U) {
        log_write(LOG_LEVEL_ERROR, "jailbreak: no kernel entry point");
        return false;
    }

    u64 boot_args_phys = status.kernel.boot_args_phys;

    log_write(LOG_LEVEL_WARN, "jailbreak: booting kernel at phys 0x%llx (boot_args=0x%llx)",
              entry_point, boot_args_phys);
    report_progress("booting-kernel", 100U);
    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE,
                            "jailbreak-boot", entry_point, 2U);

    status.state = JAILBREAK_STATE_RUNNING;

    __asm__ volatile("dsb sy" ::: "memory");
    __asm__ volatile("isb" ::: "memory");

    u64 sctlr = 0U;
    __asm__ volatile("mrs %0, sctlr_el1" : "=r"(sctlr));
    if ((sctlr & MMU_SCTLR_M) != 0U) {
        log_write(LOG_LEVEL_WARN, "jailbreak: disabling MMU before kernel boot");
        sctlr &= ~MMU_SCTLR_M;
        sctlr &= ~MMU_SCTLR_WXN;
        __asm__ volatile("msr sctlr_el1, %0" : : "r"(sctlr) : "memory");
        __asm__ volatile("isb" ::: "memory");
    }

    log_write(LOG_LEVEL_WARN, "jailbreak: jumping to kernel entry (x0=0, x1=boot_args, x2=NULL)");

    void (*kernel_entry)(u64, u64, void *) = (void (*)(u64, u64, void *))(usize)entry_point;
    kernel_entry(0U, boot_args_phys, NULL);

    status.state = JAILBREAK_STATE_FAILED;
    log_write(LOG_LEVEL_ERROR, "jailbreak: kernel returned (unexpected)");
    return false;
}

bool jailbreak_chain_all(void)
{
    log_write(LOG_LEVEL_INFO, "jailbreak: running full chain");
    report_progress("jailbreak-chain", 0U);

    if (!jailbreak_apply_all_security_bypasses()) {
        return false;
    }

    if (!mmu_enable()) {
        log_write(LOG_LEVEL_ERROR, "jailbreak: MMU enable failed");
        status.state = JAILBREAK_STATE_FAILED;
        return false;
    }
    status.state = JAILBREAK_STATE_PAGE_TABLES_READY;
    report_progress("mmu-enabled", 55U);

    if (status.kernel.kernelcache_phys == 0U) {
        jailbreak_detect_kernel(0U, 0U);
    }

    if (status.kernel.boot_args_phys == 0U) {
        jailbreak_parse_boot_args(0U);
    }

    if (!status.kernel.boot_args_modified) {
        jailbreak_inject_boot_args(NULL);
    }

    if (!status.sep.sep_initialized) {
        jailbreak_detect_sep(0U);
    }

    log_write(LOG_LEVEL_INFO, "jailbreak: chain complete, ready to boot");
    status.state = JAILBREAK_STATE_READY_TO_BOOT;
    report_progress("chain-complete", 95U);
    return true;
}

jailbreak_status_t jailbreak_get_status(void)
{
    return status;
}

void jailbreak_set_progress_callback(jailbreak_progress_callback_t callback, void *context)
{
    progress_cb = callback;
    progress_ctx = context;
}
