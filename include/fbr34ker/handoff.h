#pragma once
// SPDX-License-Identifier: BSD-2-Clause
#include "fbr34ker/types.h"

/* Stable numeric value retained for loader ABI compatibility. */
#define FBR34KER_HANDOFF_MAGIC 0x464F524745484F46ULL
#define FBR34KER_HANDOFF_VERSION_1 1U
#define FBR34KER_HANDOFF_VERSION_2 2U
#define FBR34KER_HANDOFF_VERSION_3 3U
#define FBR34KER_HANDOFF_VERSION_4 4U
#define FBR34KER_HANDOFF_VERSION_CURRENT FBR34KER_HANDOFF_VERSION_4
#define FBR34KER_HANDOFF_MAX_REGIONS 128U
#define FBR34KER_HANDOFF_MAX_BOOT_MODULES 16U
#define FBR34KER_HANDOFF_MAX_DEVICE_TREE_SIZE (4U * 1024U * 1024U)

#define FBR34KER_HANDOFF_FLAG_EARLY_CONSOLE_VALID    (1ULL << 0)
#define FBR34KER_HANDOFF_FLAG_DEVICE_TREE_VALID      (1ULL << 1)
#define FBR34KER_HANDOFF_FLAG_FRAMEBUFFER_VALID      (1ULL << 2)
#define FBR34KER_HANDOFF_FLAG_RUNTIME_IO_VALID       (1ULL << 3)
#define FBR34KER_HANDOFF_FLAG_TIMER_VALID            (1ULL << 4)
#define FBR34KER_HANDOFF_FLAG_POWER_VALID            (1ULL << 5)
#define FBR34KER_HANDOFF_FLAG_PLATFORM_SERVICES_VALID (1ULL << 6)
#define FBR34KER_HANDOFF_FLAG_MODULE_POLICY_VALID     (1ULL << 7)
#define FBR34KER_HANDOFF_FLAGS_SUPPORTED \
    (FBR34KER_HANDOFF_FLAG_EARLY_CONSOLE_VALID | \
     FBR34KER_HANDOFF_FLAG_DEVICE_TREE_VALID | \
     FBR34KER_HANDOFF_FLAG_FRAMEBUFFER_VALID | \
     FBR34KER_HANDOFF_FLAG_RUNTIME_IO_VALID | \
     FBR34KER_HANDOFF_FLAG_TIMER_VALID | \
     FBR34KER_HANDOFF_FLAG_POWER_VALID | \
     FBR34KER_HANDOFF_FLAG_PLATFORM_SERVICES_VALID | \
     FBR34KER_HANDOFF_FLAG_MODULE_POLICY_VALID)

#define FBR34KER_HANDOFF_REGION_USABLE      1U
#define FBR34KER_HANDOFF_REGION_RESERVED    2U
#define FBR34KER_HANDOFF_REGION_MMIO        3U
#define FBR34KER_HANDOFF_REGION_MONITOR     4U
#define FBR34KER_HANDOFF_REGION_FRAMEBUFFER 5U

#define FBR34KER_REGION_ATTR_READ       (1U << 0)
#define FBR34KER_REGION_ATTR_WRITE      (1U << 1)
#define FBR34KER_REGION_ATTR_EXECUTE    (1U << 2)
#define FBR34KER_REGION_ATTR_DEVICE     (1U << 3)
#define FBR34KER_REGION_ATTR_DMA        (1U << 4)
#define FBR34KER_REGION_ATTR_SUPPORTED \
    (FBR34KER_REGION_ATTR_READ | FBR34KER_REGION_ATTR_WRITE | \
     FBR34KER_REGION_ATTR_EXECUTE | FBR34KER_REGION_ATTR_DEVICE | \
     FBR34KER_REGION_ATTR_DMA)

#define FBR34KER_PIXEL_FORMAT_XRGB8888 0U
#define FBR34KER_PIXEL_FORMAT_ARGB8888 1U
#define FBR34KER_PIXEL_FORMAT_BGRA8888 2U
#define FBR34KER_PIXEL_FORMAT_RGB565   3U

#define FBR34KER_PLATFORM_SERVICES_VERSION_1 1U
#define FBR34KER_SERVICE_CONSOLE_WRITE   (1ULL << 0)
#define FBR34KER_SERVICE_CONSOLE_READ    (1ULL << 1)
#define FBR34KER_SERVICE_CONSOLE_FLUSH   (1ULL << 2)
#define FBR34KER_SERVICE_FRAMEBUFFER_FLUSH (1ULL << 3)
#define FBR34KER_SERVICE_INTERRUPT_CONTROLLER (1ULL << 4)
#define FBR34KER_SERVICE_WATCHDOG_CONFIGURE (1ULL << 5)
#define FBR34KER_SERVICE_WATCHDOG_KICK   (1ULL << 6)
#define FBR34KER_SERVICE_FLAGS_SUPPORTED \
    (FBR34KER_SERVICE_CONSOLE_WRITE | FBR34KER_SERVICE_CONSOLE_READ | \
     FBR34KER_SERVICE_CONSOLE_FLUSH | FBR34KER_SERVICE_FRAMEBUFFER_FLUSH | \
     FBR34KER_SERVICE_INTERRUPT_CONTROLLER | \
     FBR34KER_SERVICE_WATCHDOG_CONFIGURE | FBR34KER_SERVICE_WATCHDOG_KICK)

#define FBR34KER_HANDOFF_MODULE_CAP_MASK_SUPPORTED 0x3fU
#define FBR34KER_HANDOFF_MAX_MODULE_SLOTS 4U
#define FBR34KER_HANDOFF_MAX_INSTRUCTION_BUDGET 4096U

#define FBR34KER_PAGE_GRANULE_4K     4096U
#define FBR34KER_PAGE_GRANULE_16K   16384U
#define FBR34KER_PAGE_GRANULE_64K   65536U

typedef void (*fbr34ker_early_putc_fn)(char value, void *context);
typedef int (*fbr34ker_runtime_getc_fn)(void *context);
typedef u64 (*fbr34ker_timer_read_fn)(void *context);
typedef void (*fbr34ker_power_action_fn)(void *context);

typedef usize (*fbr34ker_console_write_fn)(const char *data, usize size,
                                           void *context);
typedef usize (*fbr34ker_console_read_fn)(char *data, usize size,
                                          void *context);
typedef void (*fbr34ker_console_flush_fn)(void *context);
typedef bool (*fbr34ker_framebuffer_flush_fn)(void *context);
typedef u32 (*fbr34ker_interrupt_ack_fn)(void *context);
typedef void (*fbr34ker_interrupt_complete_fn)(u32 interrupt_id,
                                               void *context);
typedef bool (*fbr34ker_interrupt_set_enabled_fn)(u32 interrupt_id,
                                                  bool enabled,
                                                  void *context);
typedef bool (*fbr34ker_watchdog_configure_fn)(u64 timeout_ms,
                                               void *context);
typedef void (*fbr34ker_watchdog_kick_fn)(void *context);

typedef struct PACKED {
    u64 base;
    u64 size;
    u32 type;
    u32 attributes;
} fbr34ker_handoff_region_t;

typedef struct PACKED {
    const void *base;
    u64 size;
    u32 type;
    u32 flags;
} fbr34ker_handoff_boot_module_t;

typedef struct PACKED {
    u64 base;
    u32 width;
    u32 height;
    u32 pixels_per_row;
    u32 pixel_format;
} fbr34ker_handoff_framebuffer_t;

typedef struct PACKED {
    u32 version;
    u32 structure_size;
    u64 capabilities;
    u64 reserved;

    fbr34ker_console_write_fn console_write;
    fbr34ker_console_read_fn console_read;
    fbr34ker_console_flush_fn console_flush;
    void *console_context;

    fbr34ker_framebuffer_flush_fn framebuffer_flush;
    void *framebuffer_context;

    fbr34ker_interrupt_ack_fn interrupt_ack;
    fbr34ker_interrupt_complete_fn interrupt_complete;
    fbr34ker_interrupt_set_enabled_fn interrupt_set_enabled;
    void *interrupt_context;

    fbr34ker_watchdog_configure_fn watchdog_configure;
    fbr34ker_watchdog_kick_fn watchdog_kick;
    void *watchdog_context;
} fbr34ker_platform_services_t;

typedef struct PACKED {
    /* Version 1 prefix: never reorder these fields. */
    u64 magic;
    u32 version;
    u32 structure_size;
    u64 monitor_base;
    u64 monitor_size;
    const fbr34ker_handoff_region_t *memory_regions;
    u32 memory_region_count;
    u32 reserved;
    const void *device_tree;
    u64 device_tree_size;
    fbr34ker_early_putc_fn early_putc;
    void *early_console_context;

    /* Version 2 extension. */
    u64 flags;
    const fbr34ker_handoff_boot_module_t *boot_modules;
    u32 boot_module_count;
    u32 reserved_v2;
    fbr34ker_handoff_framebuffer_t framebuffer;
    u64 loader_identifier;

    /* Version 3 extension: hardware-neutral runtime services. */
    fbr34ker_runtime_getc_fn runtime_getc;
    void *runtime_io_context;
    fbr34ker_timer_read_fn timer_read;
    fbr34ker_timer_read_fn timer_frequency;
    void *timer_context;
    fbr34ker_power_action_fn reboot;
    fbr34ker_power_action_fn halt;
    void *power_context;
    u64 platform_identifier;

    /* Version 4 extension: portable platform services and policy. */
    const fbr34ker_platform_services_t *platform_services;
    u32 platform_services_size;
    u32 entry_exception_level;
    u32 page_granule;
    u32 boot_cpu_id;
    u64 framebuffer_size;
    u32 framebuffer_bytes_per_pixel;
    u32 framebuffer_rotation;
    u32 module_capability_allow_mask;
    u16 module_slot_limit;
    u16 reserved_v4_small;
    u32 module_instruction_budget_limit;
    u64 firmware_revision;
    u64 reserved_v4[2];
} fbr34ker_handoff_t;

bool fbr34ker_handoff_valid(const fbr34ker_handoff_t *handoff);
bool fbr34ker_handoff_covers_range(const fbr34ker_handoff_t *handoff,
                                   u64 base, u64 size);
bool fbr34ker_handoff_describes_range(const fbr34ker_handoff_t *handoff,
                                      u64 base, u64 size,
                                      u32 allowed_type_mask,
                                      u32 required_attributes);
void fbr34ker_handoff_set_active(const fbr34ker_handoff_t *handoff);
const fbr34ker_handoff_t *fbr34ker_handoff_active(void);
