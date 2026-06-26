#pragma once
#include "fbr34ker/types.h"

typedef struct {
    usize capacity;
    usize used;
    usize remaining;
    usize allocations;
    usize active_allocations;
    usize frees;
    usize failed_allocations;
    usize double_frees;
    usize corruptions;
} allocator_stats_t;

void allocator_init(void);
bool allocator_init_region(void *base, usize size);
void *allocator_alloc(usize size, usize alignment);
bool allocator_free(void *pointer);
bool allocator_check(void);
allocator_stats_t allocator_stats(void);
u64 allocator_base(void);
u64 allocator_limit(void);
