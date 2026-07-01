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
                          FBR34KER_MMIO_READ | FBR34KER_MMIO_WRITE | FBR34KER_MMIO_PROBE_SAFE, 0x04U);
    mmio_register_window("UART", 0x81D000000ULL, 0x700000,
                          FBR34KER_MMIO_READ | FBR34KER_MMIO_WRITE | FBR34KER_MMIO_PROBE_SAFE, 0x04U);
    mmio_register_window("I2C", 0x83500000ULL, 0x10000,
                          FBR34KER_MMIO_READ | FBR34KER_MMIO_WRITE, 0x04U);
    mmio_register_window("PMGR", 0x83D000000ULL, 0x1000000,
                          FBR34KER_MMIO_READ | FBR34KER_MMIO_WRITE | FBR34KER_MMIO_PROBE_SAFE, 0x04U);
    mmio_register_window("GICD", 0x82F100000ULL, 0x10000,
                          FBR34KER_MMIO_READ | FBR34KER_MMIO_WRITE, 0x04U);
    mmio_register_window("GICR", 0x82F200000ULL, 0x200000,
                          FBR34KER_MMIO_READ | FBR34KER_MMIO_WRITE, 0x04U);
    mmio_register_window("DRAM_PROBE", 0xC00000000ULL, 0x400000004ULL,
                          FBR34KER_MMIO_READ | FBR34KER_MMIO_PROBE_SAFE, 0x04U);
}

bool apple_probe_soc(void)
{
    const apple_soc_config_t *soc = NULL;

    /* Confirm Apple Silicon by probing DWC3 at the universal base */
    u32 dwc3_test = 0U;
    if (!mmio_probe_read32(USB_DWC3_MMIO_BASE, &dwc3_test) ||
        dwc3_test == 0U || dwc3_test == 0xFFFFFFFFU) {
        log_write(LOG_LEVEL_WARN, "no Apple DWC3 detected, defaulting to A13");
        soc = &apple_a13_config;
        goto register_devices;
    }

    /* Discriminate SoC by probing UART and PMGR at their variant base addresses.
     *
     *   A15 (T8110): PMGR @ 0x83D600000, UART @ 0x81D000000
     *   M2  (T8112): PMGR @ 0x83D600000, UART @ 0x823000000
     *   A14 (T8101): PMGR @ 0x83D000000, UART @ 0x81D000000
     *   A12/A13/M1:  PMGR @ 0x83D000000, UART @ 0x823000000
     */
    u32 pmgr_high_v = 0U;
    u32 uart_low_v  = 0U;
    u32 uart_std_v  = 0U;

    bool pmgr_high = (mmio_probe_read32(0x83D600000ULL, &pmgr_high_v) &&
                      pmgr_high_v != 0U && pmgr_high_v != 0xFFFFFFFFU);
    bool uart_low  = (mmio_probe_read32(0x81D000000ULL, &uart_low_v) &&
                      uart_low_v != 0U && uart_low_v != 0xFFFFFFFFU);
    bool uart_std  = (mmio_probe_read32(0x823000000ULL, &uart_std_v) &&
                      uart_std_v != 0U && uart_std_v != 0xFFFFFFFFU);

    if (pmgr_high && uart_low) {
        soc = &apple_a15_config;
    } else if (pmgr_high && uart_std) {
        soc = &apple_m2_config;
    } else if (uart_low) {
        soc = &apple_a14_config;
    } else if (uart_std) {
        /* A12/A13/M1/A12X/A12Z cluster — same MMIO footprint.
         * Distinguish by probing DRAM addressable range:
         *   M1:     64GB  (top @ 0x1800000000) — 0x1000000000 accessible
         *   A12X/Z: 32GB  (top @ 0x1000000000) — 0xC00000000 accessible, 0x1000000000 not
         *   A12/13: 16GB  (top @ 0xC00000000)  — 0xC00000000 not accessible
         */
        u32 dram_val = 0U;
        if (mmio_probe_read32(0x1000000000ULL, &dram_val)) {
            soc = &apple_m1_config;
        } else if (mmio_probe_read32(0xC00000000ULL, &dram_val)) {
            soc = &apple_a12z_config;
        } else {
            soc = &apple_a13_config;
        }
    } else {
        log_write(LOG_LEVEL_WARN, "could not determine SoC from MMIO footprint, defaulting to A13");
        soc = &apple_a13_config;
    }

    log_write(LOG_LEVEL_INFO, "Apple SoC detected: %s (CPID 0x%04x) via MMIO probe",
              soc->soc_name, soc->cpid);

register_devices:
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
