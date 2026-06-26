#ifndef FBR34KER_SDK_MEMORY_H
#define FBR34KER_SDK_MEMORY_H
#include <stdint.h>

#define FBR34KER_HANDOFF_MAX_REGIONS 128U
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
#define FBR34KER_REGION_ATTR_SUPPORTED  0x1fU

#if defined(__GNUC__) || defined(__clang__)
#define FBR34KER_SDK_PACKED __attribute__((packed))
#define FBR34KER_SDK_ALIGNED(x) __attribute__((aligned(x)))
#else
#define FBR34KER_SDK_PACKED
#define FBR34KER_SDK_ALIGNED(x)
#endif

typedef struct FBR34KER_SDK_PACKED {
    uint64_t base;
    uint64_t size;
    uint32_t type;
    uint32_t attributes;
} fbr34ker_handoff_region_t;

#endif
