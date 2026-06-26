#ifndef FBR34KER_SDK_HANDOFF_H
#define FBR34KER_SDK_HANDOFF_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "fbr34ker_memory.h"
#include "fbr34ker_modules.h"
#include "fbr34ker_services.h"

#define FBR34KER_HANDOFF_MAGIC 0x464F524745484F46ULL
#define FBR34KER_HANDOFF_VERSION_1 1U
#define FBR34KER_HANDOFF_VERSION_2 2U
#define FBR34KER_HANDOFF_VERSION_3 3U
#define FBR34KER_HANDOFF_VERSION_4 4U
#define FBR34KER_HANDOFF_VERSION_CURRENT 4U
#define FBR34KER_HANDOFF_MAX_DEVICE_TREE_SIZE (4U * 1024U * 1024U)

#define FBR34KER_HANDOFF_FLAG_EARLY_CONSOLE_VALID     (1ULL << 0)
#define FBR34KER_HANDOFF_FLAG_DEVICE_TREE_VALID       (1ULL << 1)
#define FBR34KER_HANDOFF_FLAG_FRAMEBUFFER_VALID       (1ULL << 2)
#define FBR34KER_HANDOFF_FLAG_RUNTIME_IO_VALID        (1ULL << 3)
#define FBR34KER_HANDOFF_FLAG_TIMER_VALID             (1ULL << 4)
#define FBR34KER_HANDOFF_FLAG_POWER_VALID             (1ULL << 5)
#define FBR34KER_HANDOFF_FLAG_PLATFORM_SERVICES_VALID (1ULL << 6)
#define FBR34KER_HANDOFF_FLAG_MODULE_POLICY_VALID      (1ULL << 7)
#define FBR34KER_HANDOFF_FLAGS_SUPPORTED 0xffULL

#define FBR34KER_PIXEL_FORMAT_XRGB8888 0U
#define FBR34KER_PIXEL_FORMAT_ARGB8888 1U
#define FBR34KER_PIXEL_FORMAT_BGRA8888 2U
#define FBR34KER_PIXEL_FORMAT_RGB565   3U
#define FBR34KER_PAGE_GRANULE_4K 4096U
#define FBR34KER_PAGE_GRANULE_16K 16384U
#define FBR34KER_PAGE_GRANULE_64K 65536U

typedef void (*fbr34ker_early_putc_fn)(char, void *);
typedef int (*fbr34ker_runtime_getc_fn)(void *);
typedef uint64_t (*fbr34ker_timer_read_fn)(void *);
typedef void (*fbr34ker_power_action_fn)(void *);

typedef struct FBR34KER_SDK_PACKED {
    uint64_t base;
    uint32_t width;
    uint32_t height;
    uint32_t pixels_per_row;
    uint32_t pixel_format;
} fbr34ker_handoff_framebuffer_t;

typedef struct FBR34KER_SDK_PACKED {
    uint64_t magic;
    uint32_t version;
    uint32_t structure_size;
    uint64_t monitor_base;
    uint64_t monitor_size;
    const fbr34ker_handoff_region_t *memory_regions;
    uint32_t memory_region_count;
    uint32_t reserved;
    const void *device_tree;
    uint64_t device_tree_size;
    fbr34ker_early_putc_fn early_putc;
    void *early_console_context;
    uint64_t flags;
    const fbr34ker_handoff_boot_module_t *boot_modules;
    uint32_t boot_module_count;
    uint32_t reserved_v2;
    fbr34ker_handoff_framebuffer_t framebuffer;
    uint64_t loader_identifier;
    fbr34ker_runtime_getc_fn runtime_getc;
    void *runtime_io_context;
    fbr34ker_timer_read_fn timer_read;
    fbr34ker_timer_read_fn timer_frequency;
    void *timer_context;
    fbr34ker_power_action_fn reboot;
    fbr34ker_power_action_fn halt;
    void *power_context;
    uint64_t platform_identifier;
    const fbr34ker_platform_services_t *platform_services;
    uint32_t platform_services_size;
    uint32_t entry_exception_level;
    uint32_t page_granule;
    uint32_t boot_cpu_id;
    uint64_t framebuffer_size;
    uint32_t framebuffer_bytes_per_pixel;
    uint32_t framebuffer_rotation;
    uint32_t module_capability_allow_mask;
    uint16_t module_slot_limit;
    uint16_t reserved_v4_small;
    uint32_t module_instruction_budget_limit;
    uint64_t firmware_revision;
    uint64_t reserved_v4[2];
} fbr34ker_handoff_t;

#if defined(__STDC_VERSION__) && __STDC_VERSION__ >= 201112L
_Static_assert(sizeof(void *) == 8, "FBR34KER ABI requires 64-bit pointers");
_Static_assert(sizeof(fbr34ker_handoff_region_t) == 24, "region ABI size");
_Static_assert(sizeof(fbr34ker_handoff_boot_module_t) == 24, "module ABI size");
_Static_assert(sizeof(fbr34ker_handoff_framebuffer_t) == 24, "framebuffer ABI size");
_Static_assert(sizeof(fbr34ker_platform_services_t) == 128, "services ABI size");
_Static_assert(sizeof(fbr34ker_handoff_t) == 284, "handoff ABI size");
_Static_assert(offsetof(fbr34ker_handoff_t, flags) == 80, "v2 ABI offset");
_Static_assert(offsetof(fbr34ker_handoff_t, runtime_getc) == 136, "v3 ABI offset");
_Static_assert(offsetof(fbr34ker_handoff_t, platform_services) == 208, "v4 ABI offset");
_Static_assert(offsetof(fbr34ker_handoff_t, reserved_v4) == 268, "v4 tail offset");
#endif

#endif
