#pragma once
#include "fbr34ker/types.h"

#define APPLE_A12_CPID 0x8015U
#define APPLE_A12X_CPID 0x8027U
#define APPLE_A12Z_CPID 0x8028U
#define APPLE_A13_CPID 0x8020U
#define APPLE_A14_CPID 0x8030U
#define APPLE_M1_CPID 0x8103U
#define APPLE_A15_CPID 0x8110U
#define APPLE_M2_CPID 0x8112U

#define APPLE_A12_SOC "T8015"
#define APPLE_A12X_SOC "T8027"
#define APPLE_A12Z_SOC "T8028"
#define APPLE_A13_SOC "T8020"
#define APPLE_A14_SOC "T8030"
#define APPLE_M1_SOC "T8103"
#define APPLE_A15_SOC "T8110"
#define APPLE_M2_SOC "T8112"

#define APPLE_IOS_KERNEL_BASE 0xfffffff007004000ULL
#define APPLE_IOS17_KERNEL_BASE 0xfffffff007804000ULL
#define APPLE_KERNEL_PRELOAD_BASE 0x800000000ULL
#define APPLE_PONGO_BASE 0x800000000ULL
#define APPLE_LOAD_ADDR 0x800000000ULL

#define APPLE_IMAGE4_MAGIC 0x216567614d4947ULL
#define APPLE_IMG4_MAGIC 0x34676d49U
#define APPLE_IM4P_MAGIC 0x70346d49U
#define APPLE_IM4M_MAGIC 0x6d346d49U

#define CHIP_ID_T8010 0x8010U
#define CHIP_ID_T8011 0x8011U
#define CHIP_ID_T8012 0x8012U
#define CHIP_ID_T8015 0x8015U
#define CHIP_ID_T8020 0x8020U
#define CHIP_ID_T8027 0x8027U
#define CHIP_ID_T8030 0x8030U

typedef enum {
    APPLE_BOOT_STAGE_UNKNOWN = 0,
    APPLE_BOOT_STAGE_LLB,
    APPLE_BOOT_STAGE_IBOOT,
    APPLE_BOOT_STAGE_IBEC,
    APPLE_BOOT_STAGE_IBSS,
    APPLE_BOOT_STAGE_KERNEL,
    APPLE_BOOT_STAGE_PONGO
} apple_boot_stage_t;

typedef enum {
    APPLE_DEVICE_NONE = 0,
    APPLE_DEVICE_IPHONE,
    APPLE_DEVICE_IPAD,
    APPLE_DEVICE_IPOD,
    APPLE_DEVICE_APPLE_TV,
    APPLE_DEVICE_HOME_POD
} apple_device_type_t;

typedef struct {
    u16 cpid;
    u16 board_id;
    const char *soc_name;
    apple_device_type_t device_type;
    const char *product_type;
    u64 dram_base;
    u64 dram_size;
    u64 usb_dwc3_base;
    u64 uart_base;
    u64 gic_base;
    u64 i2c_base;
    u64 pmgr_base;
    u32 gic_version;
} apple_soc_config_t;

typedef struct {
    u32 magic;
    u32 header_size;
    u8 key[32];
    u8 iv[8];
    u8 epoch;
    u8 flags;
    u16 reserved;
    u64 image_type;
    u32 max_length;
    u64 reserved2;
} PACKED apple_img4_header_t;

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
} PACKED apple_boot_args_t;

extern const apple_soc_config_t apple_a12_config;
extern const apple_soc_config_t apple_a12x_config;
extern const apple_soc_config_t apple_a12z_config;
extern const apple_soc_config_t apple_a13_config;
extern const apple_soc_config_t apple_a14_config;
extern const apple_soc_config_t apple_m1_config;
extern const apple_soc_config_t apple_a15_config;
extern const apple_soc_config_t apple_m2_config;

const apple_soc_config_t *apple_soc_for_cpid(u16 cpid);
const char *apple_boot_stage_name(apple_boot_stage_t stage);
bool apple_is_pongo_compatible(u16 cpid);
bool apple_soc_init(void);
void apple_setup_mmio(void);
bool apple_probe_soc(void);
