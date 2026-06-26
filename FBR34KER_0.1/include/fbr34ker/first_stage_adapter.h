#pragma once
#include <stddef.h>
#include <stdint.h>

#define FBR34KER_FIRST_STAGE_ADAPTER_ABI_VERSION 1U
#define FBR34KER_FIRST_STAGE_DESCRIPTOR_SIZE 64U
#define FBR34KER_FIRST_STAGE_MAX_MEMORY_REGIONS 32U

#define FBR34KER_FIRST_STAGE_CAP_UPLOAD        (1ULL << 0)
#define FBR34KER_FIRST_STAGE_CAP_START         (1ULL << 1)
#define FBR34KER_FIRST_STAGE_CAP_CONSOLE       (1ULL << 2)
#define FBR34KER_FIRST_STAGE_CAP_INVENTORY     (1ULL << 3)
#define FBR34KER_FIRST_STAGE_CAP_TIMER         (1ULL << 4)
#define FBR34KER_FIRST_STAGE_CAP_INTERRUPTS    (1ULL << 5)
#define FBR34KER_FIRST_STAGE_CAP_WATCHDOG      (1ULL << 6)
#define FBR34KER_FIRST_STAGE_CAP_BOOT_EVIDENCE (1ULL << 7)
#define FBR34KER_FIRST_STAGE_CAP_RESET         (1ULL << 8)
#define FBR34KER_FIRST_STAGE_CAP_SUPPORTED     0x1ffULL

typedef struct __attribute__((packed)) {
    uint32_t abi_version;
    uint32_t structure_size;
    uint64_t capabilities;
    uint64_t maximum_image_size;
    uint32_t maximum_memory_regions;
    uint32_t session_generation;
    uint64_t device_identifier;
    uint64_t reserved[3];
} fbr34ker_first_stage_adapter_descriptor_t;

_Static_assert(sizeof(fbr34ker_first_stage_adapter_descriptor_t) ==
               FBR34KER_FIRST_STAGE_DESCRIPTOR_SIZE,
               "first-stage adapter descriptor ABI size changed");
_Static_assert(offsetof(fbr34ker_first_stage_adapter_descriptor_t, capabilities) == 8U,
               "first-stage capabilities offset changed");
_Static_assert(offsetof(fbr34ker_first_stage_adapter_descriptor_t, device_identifier) == 32U,
               "first-stage device identifier offset changed");
