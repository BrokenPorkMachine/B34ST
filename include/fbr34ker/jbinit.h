#pragma once
// SPDX-License-Identifier: BSD-2-Clause
#include "fbr34ker/types.h"

#define JBINIT_MAX_BOOTARGS 2048U
#define JBINIT_MAX_DART_REGIONS 16U
#define JBINIT_DART_NUM_TTBR 8U
#define JBINIT_PMGR_MAX_DOMAINS 32U
#define JBINIT_IBEC_CMD_SIZE 256U

typedef enum {
    JBINIT_STATE_UNINITIALIZED = 0,
    JBINIT_STATE_HARDWARE_PROBED,
    JBINIT_STATE_DART_CONFIGURED,
    JBINIT_STATE_PMGR_READY,
    JBINIT_STATE_BOOT_MODE_DETECTED,
    JBINIT_STATE_IBEC_CONNECTED,
    JBINIT_STATE_SEP_AVAILABLE,
    JBINIT_STATE_BOOTARGS_READY,
    JBINIT_STATE_READY,
    JBINIT_STATE_FAILED,
} jbinit_state_t;

typedef enum {
    JBINIT_BOOT_MODE_UNKNOWN = 0,
    JBINIT_BOOT_MODE_DFU,
    JBINIT_BOOT_MODE_RECOVERY,
    JBINIT_BOOT_MODE_NORMAL,
    JBINIT_BOOT_MODE_PONGO,
    JBINIT_BOOT_MODE_RESTORE,
} jbinit_boot_mode_t;

typedef enum {
    JBINIT_DART_DEVICE_USB = 0,
    JBINIT_DART_DEVICE_SPI,
    JBINIT_DART_DEVICE_DMA,
    JBINIT_DART_DEVICE_DISPATCH,
    JBINIT_DART_DEVICE_AES,
    JBINIT_DART_DEVICE_ISP,
    JBINIT_DART_DEVICE_MAX,
} jbinit_dart_device_t;

typedef struct {
    u64 ttbr[JBINIT_DART_NUM_TTBR];
    u64 ttbr_count;
    u32 ttbr0_count;
    u32 ttbr1_count;
    u32 tcr;
    u32 mair;
    u32 nsid;
    u64 base;
    u64 size;
    bool translation_enabled;
    bool bypass_enabled;
    bool initialized;
} PACKED jbinit_dart_config_t;

typedef struct {
    u64 pmgr_base;
    u64 psrt_base;
    u64 psist_base;
    u64 aict_base;
    u32 domain_count;
    bool initialized;
} PACKED jbinit_pmgr_config_t;

typedef struct {
    u64 dram_base;
    u64 dram_size;
    u64 kernelcache_phys;
    u64 kernelcache_size;
    u64 devicetree_phys;
    u64 boot_args_phys;
    u64 sep_base;
    u64 dart_base;
    u64 pmgr_base;
    u64 uart_base;
    u16 cpid;
    u16 board_id;
    jbinit_boot_mode_t boot_mode;
} jbinit_hardware_info_t;

typedef struct {
    u64 usb_base;
    u64 usb_capabilities;
    u32 max_packet_size;
    u32 vendor_id;
    u32 product_id;
    u8 serial_number[64];
} jbinit_usb_device_info_t;

typedef struct {
    jbinit_state_t state;
    jbinit_hardware_info_t hw;
    jbinit_dart_config_t dart[JBINIT_DART_DEVICE_MAX];
    jbinit_pmgr_config_t pmgr;
    jbinit_usb_device_info_t usb;
    bool security_model;
    u64 init_time;
    u64 bypass_count;
    char boot_args[JBINIT_MAX_BOOTARGS];
} jbinit_status_t;

void jbinit_init(void);
void jbinit_shutdown(void);
bool jbinit_ready(void);
bool jbinit_healthy(void);
jbinit_status_t jbinit_get_status(void);

bool jbinit_probe_hardware(void);
bool jbinit_detect_boot_mode(void);
bool jbinit_configure_dart(jbinit_dart_device_t device);
bool jbinit_configure_all_dart(void);
bool jbinit_init_pmgr(void);
bool jbinit_detect_sep(void);
bool jbinit_parse_boot_args(void);
bool jbinit_set_boot_args(const char *args);
bool jbinit_connect_ibec(void);
bool jbinit_run_all(void);

bool jbinit_set_security_model(bool enable);
bool jbinit_is_security_model_active(void);

bool jbinit_is_a12_plus(void);
const char *jbinit_state_name(jbinit_state_t state);
const char *jbinit_boot_mode_name(jbinit_boot_mode_t mode);
