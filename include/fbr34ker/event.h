#pragma once
// SPDX-License-Identifier: BSD-2-Clause
#include "fbr34ker/types.h"

#define FBR34KER_EVENT_JOURNAL_CAPACITY 32U
#define FBR34KER_EVENT_SUBSCRIBER_CAPACITY 8U
#define FBR34KER_EVENT_SOURCE_CAPACITY 32U

typedef enum {
    FBR34KER_EVENT_BOOT = 0,
    FBR34KER_EVENT_COMPONENT_STATE,
    FBR34KER_EVENT_SERVICE_STATE,
    FBR34KER_EVENT_DRIVER_STATE,
    FBR34KER_EVENT_BRINGUP_MODE,
    FBR34KER_EVENT_MODULE_LOADED,
    FBR34KER_EVENT_MODULE_EXECUTED,
    FBR34KER_EVENT_MODULE_UNLOADED,
    FBR34KER_EVENT_ROLLBACK,
    FBR34KER_EVENT_VALIDATION,
    FBR34KER_EVENT_KERNEL_PATCH,
    FBR34KER_EVENT_SECURE_BOOT_BYPASS,
    FBR34KER_EVENT_PERSISTENCE,
    FBR34KER_EVENT_EXPLOIT_CHAIN,
    FBR34KER_EVENT_COUNT
} fbr34ker_event_type_t;

typedef struct {
    u64 sequence;
    fbr34ker_event_type_t type;
    char source[FBR34KER_EVENT_SOURCE_CAPACITY];
    u64 value0;
    u64 value1;
} fbr34ker_event_t;

typedef void (*fbr34ker_event_callback_t)(const fbr34ker_event_t *event,
                                           void *context);

typedef struct {
    u64 published;
    u64 overwritten;
    u64 callback_calls;
    u64 callback_failures;
    u64 recursive_dispatches;
    u64 injected_failures;
    u32 journal_count;
    u32 subscriber_count;
} fbr34ker_event_stats_t;

void event_bus_init(void);
void event_bus_shutdown(void);
bool event_bus_ready(void);
bool event_bus_subscribe(u64 type_mask, fbr34ker_event_callback_t callback,
                         void *context);
bool event_bus_publish(fbr34ker_event_type_t type, const char *source,
                       u64 value0, u64 value1);
u64 event_bus_count(void);
bool event_bus_at(u64 index, fbr34ker_event_t *event);
fbr34ker_event_stats_t event_bus_stats(void);
const char *event_type_name(fbr34ker_event_type_t type);
