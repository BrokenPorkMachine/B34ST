#pragma once
// SPDX-License-Identifier: BSD-2-Clause
#include "fbr34ker/types.h"

#define FBR34KER_TRACE_CAPACITY 64U
#define FBR34KER_TRACE_SOURCE_CAPACITY 32U

typedef enum {
    FBR34KER_TRACE_BOOT = 0,
    FBR34KER_TRACE_LIFECYCLE,
    FBR34KER_TRACE_SERVICE,
    FBR34KER_TRACE_DRIVER,
    FBR34KER_TRACE_FAULT,
    FBR34KER_TRACE_VALIDATION,
    FBR34KER_TRACE_PANIC,
    FBR34KER_TRACE_COUNT
} fbr34ker_trace_category_t;

typedef struct {
    u64 sequence;
    fbr34ker_trace_category_t category;
    u32 action;
    i32 status;
    char source[FBR34KER_TRACE_SOURCE_CAPACITY];
    u64 value0;
    u64 value1;
} fbr34ker_trace_record_t;

typedef struct {
    u64 emitted;
    u64 overwritten;
    u32 retained;
    bool initialized;
} fbr34ker_trace_stats_t;

void trace_init(void);
void trace_shutdown(void);
bool trace_ready(void);
bool trace_emit(fbr34ker_trace_category_t category, u32 action, i32 status,
                const char *source, u64 value0, u64 value1);
u64 trace_count(void);
bool trace_at(u64 index, fbr34ker_trace_record_t *record);
fbr34ker_trace_stats_t trace_stats(void);
const char *trace_category_name(fbr34ker_trace_category_t category);
usize trace_export_json(char *buffer, usize capacity);
