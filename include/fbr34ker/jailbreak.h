#pragma once
#include "fbr34ker/types.h"

#define JAILBREAK_KERNELCACHE_MAX_SIZE (128U * 1024U * 1024U)
#define JAILBREAK_MAX_BOOTARGS 2048U
#define JAILBREAK_KASLR_SLIDE_UNKNOWN 0xFFFFFFFFFFFFFFFFULL
#define JAILBREAK_MAX_SEP_COMMAND_SIZE 4096U

typedef enum {
    JAILBREAK_STATE_INACTIVE = 0,
    JAILBREAK_STATE_SECURITY_MODEL_PENDING,
    JAILBREAK_STATE_SECURITY_MODEL_ACTIVE,
    JAILBREAK_STATE_PAGE_TABLES_READY,
    JAILBREAK_STATE_PAC_BYPASSED,
    JAILBREAK_STATE_APRR_BYPASSED,
    JAILBREAK_STATE_WXN_BYPASSED,
    JAILBREAK_STATE_KASLR_DETECTED,
    JAILBREAK_STATE_KERNEL_LOADED,
    JAILBREAK_STATE_BOOTARGS_INJECTED,
    JAILBREAK_STATE_SEP_READY,
    JAILBREAK_STATE_READY_TO_BOOT,
    JAILBREAK_STATE_RUNNING,
    JAILBREAK_STATE_FAILED,
} jailbreak_state_t;

typedef struct {
    u64 kaslr_slide;
    u64 kernel_base_phys;
    u64 kernel_base_virt;
    u64 kernel_entry;
    u64 kernel_size;
    u64 kernelcache_phys;
    u64 kernelcache_size;
    u64 boot_args_phys;
    char boot_args_override[JAILBREAK_MAX_BOOTARGS];
    bool boot_args_modified;
} jailbreak_kernel_info_t;

typedef struct {
    bool sep_available;
    bool sep_initialized;
    u64 sep_base;
    u64 sep_mailbox;
    u64 sep_response;
} jailbreak_sep_info_t;

typedef struct {
    jailbreak_state_t state;
    bool security_model;
    jailbreak_kernel_info_t kernel;
    jailbreak_sep_info_t sep;
    u64 patch_count;
    u64 bypass_count;
} jailbreak_status_t;

void jailbreak_init(void);
void jailbreak_shutdown(void);
bool jailbreak_ready(void);

bool jailbreak_set_security_model(bool enable);
bool jailbreak_is_security_model_active(void);

bool jailbreak_bypass_pac(void);
bool jailbreak_bypass_aprr(void);
bool jailbreak_bypass_wxn(void);

bool jailbreak_apply_all_security_bypasses(void);
bool jailbreak_detect_kaslr_slide(u64 kernelcache_phys, u64 kernelcache_size);
bool jailbreak_detect_kernel(u64 kernelcache_phys, u64 kernelcache_size);
bool jailbreak_parse_boot_args(u64 boot_args_addr);
bool jailbreak_inject_boot_args(const char *custom_args);
bool jailbreak_detect_sep(u64 sep_mmio_base);
bool jailbreak_boot_kernel(u64 entry_point);

bool jailbreak_chain_all(void);
jailbreak_status_t jailbreak_get_status(void);

typedef bool (*jailbreak_progress_callback_t)(const char *stage, u32 percent, void *context);
void jailbreak_set_progress_callback(jailbreak_progress_callback_t callback, void *context);
