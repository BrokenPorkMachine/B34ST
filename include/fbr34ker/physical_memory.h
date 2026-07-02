#pragma once
// SPDX-License-Identifier: BSD-2-Clause
#include "fbr34ker/types.h"

#define FBR34KER_PMM_PAGE_SIZE 4096ULL
#define FBR34KER_PMM_MAX_USABLE_RANGES 16U
#define FBR34KER_PMM_MAX_RESERVED_RANGES 64U
#define FBR34KER_PMM_MAX_ALLOCATIONS 128U
#define FBR34KER_PMM_TAG_CAPACITY 32U

typedef struct {
    u64 base;
    u64 size;
    char tag[FBR34KER_PMM_TAG_CAPACITY];
} fbr34ker_pmm_range_t;

typedef struct {
    u64 usable_bytes;
    u64 reserved_bytes;
    u64 allocated_bytes;
    u64 free_bytes;
    u64 allocation_attempts;
    u64 allocation_failures;
    u32 usable_ranges;
    u32 reserved_ranges;
    u32 active_allocations;
    bool initialized;
} fbr34ker_pmm_stats_t;

void physical_memory_init(void);
void physical_memory_shutdown(void);
bool physical_memory_ready(void);
bool physical_memory_healthy(void);
bool physical_memory_add_usable(u64 base, u64 size, const char *tag);
bool physical_memory_reserve(u64 base, u64 size, const char *tag);
bool physical_memory_allocate_pages(u32 page_count, u32 alignment_pages,
                                    const char *tag, u64 *base);
bool physical_memory_free_pages(u64 base, u32 page_count);
u32 physical_memory_usable_count(void);
u32 physical_memory_reserved_count(void);
u32 physical_memory_allocation_count(void);
bool physical_memory_usable_at(u32 index, fbr34ker_pmm_range_t *range);
bool physical_memory_reserved_at(u32 index, fbr34ker_pmm_range_t *range);
bool physical_memory_allocation_at(u32 index, fbr34ker_pmm_range_t *range);
fbr34ker_pmm_stats_t physical_memory_stats(void);
