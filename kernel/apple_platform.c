#include "fbr34ker/apple_platform.h"
#include "fbr34ker/string.h"
#include "fbr34ker/log.h"
#include "fbr34ker/mmio.h"
#include "fbr34ker/usb.h"
#include "fbr34ker/board.h"
#include "fbr34ker/kernel_patches.h"

const apple_soc_config_t apple_a12_config = {
    .cpid = APPLE_A12_CPID,
    .board_id = 0x0U,
    .soc_name = APPLE_A12_SOC,
    .device_type = APPLE_DEVICE_IPHONE,
    .product_type = "iPhone11,2",
    .dram_base = 0x800000000ULL,
    .dram_size = 0x400000000ULL,
    .usb_dwc3_base = 0x860000000ULL,
    .uart_base = 0x823000000ULL,
    .gic_base = 0x82F100000ULL,
    .i2c_base = 0x83500000ULL,
    .pmgr_base = 0x83D000000ULL,
    .gic_version = 3U,
};

const apple_soc_config_t apple_a12x_config = {
    .cpid = APPLE_A12X_CPID,
    .board_id = 0x0U,
    .soc_name = APPLE_A12X_SOC,
    .device_type = APPLE_DEVICE_IPAD,
    .product_type = "iPad8,1",
    .dram_base = 0x800000000ULL,
    .dram_size = 0x800000000ULL,
    .usb_dwc3_base = 0x860000000ULL,
    .uart_base = 0x823000000ULL,
    .gic_base = 0x82F100000ULL,
    .i2c_base = 0x83500000ULL,
    .pmgr_base = 0x83D000000ULL,
    .gic_version = 3U,
};

const apple_soc_config_t apple_a12z_config = {
    .cpid = APPLE_A12Z_CPID,
    .board_id = 0x0U,
    .soc_name = APPLE_A12Z_SOC,
    .device_type = APPLE_DEVICE_IPAD,
    .product_type = "iPad8,9",
    .dram_base = 0x800000000ULL,
    .dram_size = 0x800000000ULL,
    .usb_dwc3_base = 0x860000000ULL,
    .uart_base = 0x823000000ULL,
    .gic_base = 0x82F100000ULL,
    .i2c_base = 0x83500000ULL,
    .pmgr_base = 0x83D000000ULL,
    .gic_version = 3U,
};

const apple_soc_config_t apple_a13_config = {
    .cpid = APPLE_A13_CPID,
    .board_id = 0x0U,
    .soc_name = APPLE_A13_SOC,
    .device_type = APPLE_DEVICE_IPHONE,
    .product_type = "iPhone12,1",
    .dram_base = 0x800000000ULL,
    .dram_size = 0x400000000ULL,
    .usb_dwc3_base = 0x860000000ULL,
    .uart_base = 0x823000000ULL,
    .gic_base = 0x82F100000ULL,
    .i2c_base = 0x83500000ULL,
    .pmgr_base = 0x83D000000ULL,
    .gic_version = 3U,
};

const apple_soc_config_t apple_a14_config = {
    .cpid = APPLE_A14_CPID,
    .board_id = 0x0U,
    .soc_name = APPLE_A14_SOC,
    .device_type = APPLE_DEVICE_IPHONE,
    .product_type = "iPhone13,1",
    .dram_base = 0x800000000ULL,
    .dram_size = 0x400000000ULL,
    .usb_dwc3_base = 0x860000000ULL,
    .uart_base = 0x81D000000ULL,
    .gic_base = 0x82F100000ULL,
    .i2c_base = 0x83500000ULL,
    .pmgr_base = 0x83D000000ULL,
    .gic_version = 3U,
};

const apple_soc_config_t apple_m1_config = {
    .cpid = APPLE_M1_CPID,
    .board_id = 0x0U,
    .soc_name = APPLE_M1_SOC,
    .device_type = APPLE_DEVICE_IPAD,
    .product_type = "iPad13,4",
    .dram_base = 0x800000000ULL,
    .dram_size = 0x1000000000ULL,
    .usb_dwc3_base = 0x860000000ULL,
    .uart_base = 0x823000000ULL,
    .gic_base = 0x82F100000ULL,
    .i2c_base = 0x83500000ULL,
    .pmgr_base = 0x83D000000ULL,
    .gic_version = 3U,
};

const apple_soc_config_t apple_a15_config = {
    .cpid = APPLE_A15_CPID,
    .board_id = 0x0U,
    .soc_name = APPLE_A15_SOC,
    .device_type = APPLE_DEVICE_IPHONE,
    .product_type = "iPhone14,2",
    .dram_base = 0x800000000ULL,
    .dram_size = 0x400000000ULL,
    .usb_dwc3_base = 0x860000000ULL,
    .uart_base = 0x81D000000ULL,
    .gic_base = 0x82F100000ULL,
    .i2c_base = 0x83500000ULL,
    .pmgr_base = 0x83D600000ULL,
    .gic_version = 3U,
};

const apple_soc_config_t apple_m2_config = {
    .cpid = APPLE_M2_CPID,
    .board_id = 0x0U,
    .soc_name = APPLE_M2_SOC,
    .device_type = APPLE_DEVICE_IPAD,
    .product_type = "iPad14,3",
    .dram_base = 0x800000000ULL,
    .dram_size = 0x1000000000ULL,
    .usb_dwc3_base = 0x860000000ULL,
    .uart_base = 0x823000000ULL,
    .gic_base = 0x82F100000ULL,
    .i2c_base = 0x83500000ULL,
    .pmgr_base = 0x83D600000ULL,
    .gic_version = 3U,
};

const apple_soc_config_t *apple_soc_for_cpid(u16 cpid)
{
    switch (cpid) {
    case APPLE_A12_CPID:
        return &apple_a12_config;
    case APPLE_A12X_CPID:
        return &apple_a12x_config;
    case APPLE_A12Z_CPID:
        return &apple_a12z_config;
    case APPLE_A13_CPID:
        return &apple_a13_config;
    case APPLE_A14_CPID:
        return &apple_a14_config;
    case APPLE_M1_CPID:
        return &apple_m1_config;
    case APPLE_A15_CPID:
        return &apple_a15_config;
    case APPLE_M2_CPID:
        return &apple_m2_config;
    default:
        return NULL;
    }
}

const char *apple_boot_stage_name(apple_boot_stage_t stage)
{
    switch (stage) {
    case APPLE_BOOT_STAGE_LLB: return "LLB";
    case APPLE_BOOT_STAGE_IBOOT: return "iBoot";
    case APPLE_BOOT_STAGE_IBEC: return "iBEC";
    case APPLE_BOOT_STAGE_IBSS: return "iBSS";
    case APPLE_BOOT_STAGE_KERNEL: return "kernel";
    case APPLE_BOOT_STAGE_PONGO: return "pongoOS";
    case APPLE_BOOT_STAGE_UNKNOWN: return "unknown";
    default: return "unknown";
    }
}

bool apple_is_pongo_compatible(u16 cpid)
{
    switch (cpid) {
    case APPLE_A12_CPID:
    case APPLE_A12X_CPID:
    case APPLE_A12Z_CPID:
    case APPLE_A13_CPID:
    case APPLE_A14_CPID:
    case APPLE_M1_CPID:
    case APPLE_A15_CPID:
    case APPLE_M2_CPID:
        return true;
    default:
        return false;
    }
}

void apple_setup_mmio(void)
{
    mmio_register_window("DWC3", USB_DWC3_MMIO_BASE, USB_DWC3_MMIO_SIZE,
                          FBR34KER_MMIO_READ | FBR34KER_MMIO_WRITE, 0x04U);
    mmio_register_window("UART", 0x823000000ULL, 0x10000,
                          FBR34KER_MMIO_READ | FBR34KER_MMIO_WRITE, 0x04U);
    mmio_register_window("I2C", 0x83500000ULL, 0x10000,
                          FBR34KER_MMIO_READ | FBR34KER_MMIO_WRITE, 0x04U);
    mmio_register_window("PMGR", 0x83D000000ULL, 0x100000,
                          FBR34KER_MMIO_READ | FBR34KER_MMIO_WRITE, 0x04U);
    mmio_register_window("GICD", 0x82F100000ULL, 0x10000,
                          FBR34KER_MMIO_READ | FBR34KER_MMIO_WRITE, 0x04U);
    mmio_register_window("GICR", 0x82F200000ULL, 0x200000,
                          FBR34KER_MMIO_READ | FBR34KER_MMIO_WRITE, 0x04U);
}

bool apple_probe_soc(void)
{
    u16 probe_cpids[] = {APPLE_M2_CPID, APPLE_A15_CPID, APPLE_M1_CPID,
                         APPLE_A14_CPID, APPLE_A13_CPID, APPLE_A12Z_CPID,
                         APPLE_A12X_CPID, APPLE_A12_CPID};
    const apple_soc_config_t *soc = NULL;

    for (u32 i = 0U; i < sizeof(probe_cpids) / sizeof(probe_cpids[0U]); ++i) {
        const apple_soc_config_t *candidate = apple_soc_for_cpid(probe_cpids[i]);
        if (candidate == NULL) continue;
        u32 test = 0U;
        if (mmio_probe_read32(candidate->usb_dwc3_base, &test) && test != 0U && test != 0xFFFFFFFFU) {
            soc = candidate;
            log_write(LOG_LEVEL_INFO, "Apple SoC detected: %s (CPID 0x%04x) via DWC3 probe",
                      soc->soc_name, soc->cpid);
            break;
        }
    }

    if (soc == NULL) {
        log_write(LOG_LEVEL_WARN, "no known Apple SoC detected by DWC3 probe, defaulting to A13");
        soc = &apple_a13_config;
    }

    log_write(LOG_LEVEL_INFO, "Apple SoC: %s (%s) CPID 0x%04x",
              soc->soc_name, soc->product_type, soc->cpid);

    board_add_device("dwc3-usb", "snps,dwc3", FBR34KER_DEVICE_USB,
                     FBR34KER_DEVICE_FLAG_MMIO_READ | FBR34KER_DEVICE_FLAG_MMIO_WRITE,
                     soc->usb_dwc3_base, 0x100000, 0U, 0xffffffffU);
    board_add_device("uart", "apple,s5l-uart", FBR34KER_DEVICE_UART,
                     FBR34KER_DEVICE_FLAG_MMIO_READ | FBR34KER_DEVICE_FLAG_MMIO_WRITE,
                     soc->uart_base, 0x10000, 0U, 0xffffffffU);
    board_add_device("gic", "arm,gic-v3", FBR34KER_DEVICE_INTERRUPT_CONTROLLER,
                     FBR34KER_DEVICE_FLAG_MMIO_READ | FBR34KER_DEVICE_FLAG_MMIO_WRITE,
                     soc->gic_base, 0x300000, 0U, 0xffffffffU);
    board_add_device("i2c", "apple,s5l-i2c", FBR34KER_DEVICE_I2C,
                     FBR34KER_DEVICE_FLAG_MMIO_READ | FBR34KER_DEVICE_FLAG_MMIO_WRITE,
                     soc->i2c_base, 0x10000, 0U, 0xffffffffU);

    kernel_patches_set_soc(soc->cpid, APPLE_IOS_KERNEL_BASE);
    kernel_patches_set_dram_base(soc->dram_base);
    usb_init(soc->usb_dwc3_base);
    return true;
}

bool apple_soc_init(void)
{
    apple_setup_mmio();
    return apple_probe_soc();
}
