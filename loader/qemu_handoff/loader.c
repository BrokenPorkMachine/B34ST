#include "fbr34ker/handoff.h"

#define PL011_BASE 0x09000000ULL
#define UART_DR 0x000U
#define UART_FR 0x018U
#define UART_CR 0x030U
#define UART_ICR 0x044U
#define UART_FR_RXFE (1U << 4)
#define UART_FR_TXFF (1U << 5)
#define UART_CR_UARTEN (1U << 0)
#define UART_CR_TXE (1U << 8)
#define UART_CR_RXE (1U << 9)

#define GENERIC_IMAGE_BASE 0x80000000ULL
#define GENERIC_IMAGE_WINDOW (64ULL * 1024ULL * 1024ULL)
#define FRAMEBUFFER_BASE 0x70000000ULL
#define FRAMEBUFFER_SIZE (4ULL * 1024ULL * 1024ULL)
#define QEMU_RAM_END 0xC0000000ULL
#define FDT_MAGIC 0xD00DFEEDU

// SPDX-License-Identifier: BSD-2-Clause
extern u8 __loader_start[];
extern u8 __loader_end[];

typedef NORETURN void (*generic_entry_fn)(const fbr34ker_handoff_t *handoff);

static fbr34ker_handoff_region_t regions[9] ALIGNED(16);
static fbr34ker_platform_services_t services ALIGNED(16);
static fbr34ker_handoff_t handoff ALIGNED(16);
static volatile u64 watchdog_timeout_ms;
static volatile u64 watchdog_kick_count;

static volatile u32 *uart_reg(u32 offset)
{
    return (volatile u32 *)(usize)(PL011_BASE + offset);
}

static u32 read_be32(const void *pointer)
{
    const u8 *bytes = (const u8 *)pointer;
    return ((u32)bytes[0] << 24U) | ((u32)bytes[1] << 16U) |
           ((u32)bytes[2] << 8U) | (u32)bytes[3];
}

static usize loader_console_write(const char *data, usize size, void *context)
{
    UNUSED(context);
    for (usize index = 0U; index < size; ++index) {
        while ((*uart_reg(UART_FR) & UART_FR_TXFF) != 0U) {
            __asm__ volatile("yield");
        }
        *uart_reg(UART_DR) = (u32)(u8)data[index];
    }
    return size;
}

static usize loader_console_read(char *data, usize size, void *context)
{
    UNUSED(context);
    if (data == NULL || size == 0U ||
        (*uart_reg(UART_FR) & UART_FR_RXFE) != 0U) {
        return 0U;
    }
    data[0] = (char)(*uart_reg(UART_DR) & 0xffU);
    return 1U;
}

static void loader_console_flush(void *context)
{
    UNUSED(context);
    __asm__ volatile("dsb sy" ::: "memory");
}

static void loader_early_putc(char value, void *context)
{
    (void)loader_console_write(&value, 1U, context);
}

static int loader_runtime_getc(void *context)
{
    char value = 0;
    return loader_console_read(&value, 1U, context) == 1U ? (int)(u8)value : -1;
}

static bool loader_framebuffer_flush(void *context)
{
    UNUSED(context);
    __asm__ volatile("dsb sy" ::: "memory");
    return true;
}

static bool loader_watchdog_configure(u64 timeout_ms, void *context)
{
    UNUSED(context);
    if (timeout_ms > 600000ULL) return false;
    watchdog_timeout_ms = timeout_ms;
    return true;
}

static void loader_watchdog_kick(void *context)
{
    UNUSED(context);
    if (watchdog_timeout_ms != 0U) ++watchdog_kick_count;
}

static u64 loader_timer_read(void *context)
{
    UNUSED(context);
    u64 value;
    __asm__ volatile("mrs %0, cntpct_el0" : "=r"(value));
    return value;
}

static u64 loader_timer_frequency(void *context)
{
    UNUSED(context);
    u64 value;
    __asm__ volatile("mrs %0, cntfrq_el0" : "=r"(value));
    return value;
}

static u64 psci_hvc(u64 function_id)
{
    register u64 x0 __asm__("x0") = function_id;
    __asm__ volatile("hvc #0" : "+r"(x0) :: "memory");
    return x0;
}

static NORETURN void loader_reboot(void *context)
{
    UNUSED(context);
    (void)psci_hvc(0x84000009ULL);
    for (;;) __asm__ volatile("wfe");
}

static NORETURN void loader_halt(void *context)
{
    UNUSED(context);
    (void)psci_hvc(0x84000008ULL);
    for (;;) __asm__ volatile("wfe");
}

static u32 current_exception_level(void)
{
    u64 value;
    __asm__ volatile("mrs %0, CurrentEL" : "=r"(value));
    return (u32)(value >> 2U);
}

static u32 boot_cpu_id(void)
{
    u64 value;
    __asm__ volatile("mrs %0, mpidr_el1" : "=r"(value));
    return (u32)(value & 0xFFFFFFU);
}

static void initialize_uart(void)
{
    *uart_reg(UART_CR) = 0U;
    *uart_reg(UART_ICR) = 0x7ffU;
    *uart_reg(UART_CR) = UART_CR_UARTEN | UART_CR_TXE | UART_CR_RXE;
}

static void initialize_regions(void)
{
    regions[0] = (fbr34ker_handoff_region_t){
        .base = 0x08000000ULL, .size = 0x01000000ULL,
        .type = FBR34KER_HANDOFF_REGION_MMIO,
        .attributes = FBR34KER_REGION_ATTR_READ | FBR34KER_REGION_ATTR_WRITE |
                      FBR34KER_REGION_ATTR_DEVICE,
    };
    regions[1] = (fbr34ker_handoff_region_t){
        .base = PL011_BASE, .size = 0x1000ULL,
        .type = FBR34KER_HANDOFF_REGION_MMIO,
        .attributes = FBR34KER_REGION_ATTR_READ | FBR34KER_REGION_ATTR_WRITE |
                      FBR34KER_REGION_ATTR_DEVICE,
    };
    regions[2] = (fbr34ker_handoff_region_t){
        .base = 0x40000000ULL, .size = 0x00080000ULL,
        .type = FBR34KER_HANDOFF_REGION_USABLE,
        .attributes = FBR34KER_REGION_ATTR_READ | FBR34KER_REGION_ATTR_WRITE,
    };
    regions[3] = (fbr34ker_handoff_region_t){
        .base = 0x40080000ULL, .size = 0x00080000ULL,
        .type = FBR34KER_HANDOFF_REGION_RESERVED,
        .attributes = FBR34KER_REGION_ATTR_READ | FBR34KER_REGION_ATTR_WRITE |
                      FBR34KER_REGION_ATTR_EXECUTE,
    };
    regions[4] = (fbr34ker_handoff_region_t){
        .base = 0x40100000ULL, .size = 0x2ff00000ULL,
        .type = FBR34KER_HANDOFF_REGION_USABLE,
        .attributes = FBR34KER_REGION_ATTR_READ | FBR34KER_REGION_ATTR_WRITE,
    };
    regions[5] = (fbr34ker_handoff_region_t){
        .base = FRAMEBUFFER_BASE, .size = FRAMEBUFFER_SIZE,
        .type = FBR34KER_HANDOFF_REGION_FRAMEBUFFER,
        .attributes = FBR34KER_REGION_ATTR_READ | FBR34KER_REGION_ATTR_WRITE,
    };
    regions[6] = (fbr34ker_handoff_region_t){
        .base = FRAMEBUFFER_BASE + FRAMEBUFFER_SIZE,
        .size = GENERIC_IMAGE_BASE - (FRAMEBUFFER_BASE + FRAMEBUFFER_SIZE),
        .type = FBR34KER_HANDOFF_REGION_USABLE,
        .attributes = FBR34KER_REGION_ATTR_READ | FBR34KER_REGION_ATTR_WRITE,
    };
    regions[7] = (fbr34ker_handoff_region_t){
        .base = GENERIC_IMAGE_BASE, .size = GENERIC_IMAGE_WINDOW,
        .type = FBR34KER_HANDOFF_REGION_MONITOR,
        .attributes = FBR34KER_REGION_ATTR_READ | FBR34KER_REGION_ATTR_WRITE |
                      FBR34KER_REGION_ATTR_EXECUTE,
    };
    regions[8] = (fbr34ker_handoff_region_t){
        .base = GENERIC_IMAGE_BASE + GENERIC_IMAGE_WINDOW,
        .size = QEMU_RAM_END - (GENERIC_IMAGE_BASE + GENERIC_IMAGE_WINDOW),
        .type = FBR34KER_HANDOFF_REGION_USABLE,
        .attributes = FBR34KER_REGION_ATTR_READ | FBR34KER_REGION_ATTR_WRITE,
    };
}

NORETURN void qemu_loader_main(const void *device_tree)
{
    initialize_uart();
    initialize_regions();

    services = (fbr34ker_platform_services_t){
        .version = FBR34KER_PLATFORM_SERVICES_VERSION_1,
        .structure_size = sizeof(services),
        .capabilities = FBR34KER_SERVICE_CONSOLE_WRITE |
                        FBR34KER_SERVICE_CONSOLE_READ |
                        FBR34KER_SERVICE_CONSOLE_FLUSH |
                        FBR34KER_SERVICE_FRAMEBUFFER_FLUSH |
                        FBR34KER_SERVICE_WATCHDOG_CONFIGURE |
                        FBR34KER_SERVICE_WATCHDOG_KICK,
        .console_write = loader_console_write,
        .console_read = loader_console_read,
        .console_flush = loader_console_flush,
        .framebuffer_flush = loader_framebuffer_flush,
        .watchdog_configure = loader_watchdog_configure,
        .watchdog_kick = loader_watchdog_kick,
    };

    u64 flags = FBR34KER_HANDOFF_FLAG_EARLY_CONSOLE_VALID |
                FBR34KER_HANDOFF_FLAG_FRAMEBUFFER_VALID |
                FBR34KER_HANDOFF_FLAG_RUNTIME_IO_VALID |
                FBR34KER_HANDOFF_FLAG_TIMER_VALID |
                FBR34KER_HANDOFF_FLAG_POWER_VALID |
                FBR34KER_HANDOFF_FLAG_PLATFORM_SERVICES_VALID |
                FBR34KER_HANDOFF_FLAG_MODULE_POLICY_VALID;
    u64 device_tree_size = 0U;
    if (device_tree != NULL && read_be32(device_tree) == FDT_MAGIC) {
        device_tree_size = read_be32((const u8 *)device_tree + 4U);
        if (device_tree_size != 0U &&
            device_tree_size <= FBR34KER_HANDOFF_MAX_DEVICE_TREE_SIZE) {
            flags |= FBR34KER_HANDOFF_FLAG_DEVICE_TREE_VALID;
        } else {
            device_tree = NULL;
            device_tree_size = 0U;
        }
    } else {
        device_tree = NULL;
    }

    handoff = (fbr34ker_handoff_t){
        .magic = FBR34KER_HANDOFF_MAGIC,
        .version = FBR34KER_HANDOFF_VERSION_CURRENT,
        .structure_size = sizeof(handoff),
        .monitor_base = GENERIC_IMAGE_BASE,
        .monitor_size = GENERIC_IMAGE_WINDOW,
        .memory_regions = regions,
        .memory_region_count = ARRAY_COUNT(regions),
        .device_tree = device_tree,
        .device_tree_size = device_tree_size,
        .early_putc = loader_early_putc,
        .flags = flags,
        .framebuffer = {
            .base = FRAMEBUFFER_BASE,
            .width = 1024U,
            .height = 768U,
            .pixels_per_row = 1024U,
            .pixel_format = FBR34KER_PIXEL_FORMAT_XRGB8888,
        },
        .loader_identifier = 0x51454d554c445231ULL,
        .runtime_getc = loader_runtime_getc,
        .timer_read = loader_timer_read,
        .timer_frequency = loader_timer_frequency,
        .reboot = loader_reboot,
        .halt = loader_halt,
        .platform_identifier = 0x51454d5556495254ULL,
        .platform_services = &services,
        .platform_services_size = sizeof(services),
        .entry_exception_level = current_exception_level(),
        .page_granule = FBR34KER_PAGE_GRANULE_4K,
        .boot_cpu_id = boot_cpu_id(),
        .framebuffer_size = FRAMEBUFFER_SIZE,
        .framebuffer_bytes_per_pixel = 4U,
        .module_capability_allow_mask = FBR34KER_HANDOFF_MODULE_CAP_MASK_SUPPORTED,
        .module_slot_limit = FBR34KER_HANDOFF_MAX_MODULE_SLOTS,
        .module_instruction_budget_limit = FBR34KER_HANDOFF_MAX_INSTRUCTION_BUDGET,
    };

    loader_early_putc('L', NULL);
    loader_early_putc('D', NULL);
    loader_early_putc('R', NULL);
    loader_early_putc('\n', NULL);

    generic_entry_fn entry = (generic_entry_fn)(usize)GENERIC_IMAGE_BASE;
    entry(&handoff);
}
