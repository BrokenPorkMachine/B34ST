#include "fbr34ker/event.h"
#include "fbr34ker/fault.h"
#include "fbr34ker/string.h"

// SPDX-License-Identifier: BSD-2-Clause
typedef struct {
    u64 mask;
    fbr34ker_event_callback_t callback;
    void *context;
} event_subscriber_t;

static fbr34ker_event_t journal[FBR34KER_EVENT_JOURNAL_CAPACITY];
static event_subscriber_t subscribers[FBR34KER_EVENT_SUBSCRIBER_CAPACITY];
static fbr34ker_event_stats_t statistics;
static usize journal_head;
static bool initialized;
static bool dispatching;

void event_bus_init(void)
{
    fm_memset(journal, 0, sizeof(journal));
    fm_memset(subscribers, 0, sizeof(subscribers));
    fm_memset(&statistics, 0, sizeof(statistics));
    journal_head = 0U;
    initialized = true;
    dispatching = false;
}

void event_bus_shutdown(void)
{
    initialized = false;
    dispatching = false;
    statistics.subscriber_count = 0U;
}

bool event_bus_ready(void)
{
    return initialized;
}

bool event_bus_subscribe(u64 mask, fbr34ker_event_callback_t callback,
                         void *context)
{
    if (!initialized || callback == NULL || mask == 0U ||
        statistics.subscriber_count >= ARRAY_COUNT(subscribers)) {
        return false;
    }
    subscribers[statistics.subscriber_count++] = (event_subscriber_t){
        .mask = mask,
        .callback = callback,
        .context = context,
    };
    return true;
}

bool event_bus_publish(fbr34ker_event_type_t type, const char *source,
                       u64 value0, u64 value1)
{
    if (!initialized || type >= FBR34KER_EVENT_COUNT || source == NULL) {
        return false;
    }
    if (fault_injection_should_fail(FBR34KER_FAULT_EVENT_PUBLISH, source)) {
        ++statistics.injected_failures;
        return false;
    }
    fbr34ker_event_t event;
    fm_memset(&event, 0, sizeof(event));
    event.sequence = ++statistics.published;
    event.type = type;
    fm_strlcpy(event.source, source, sizeof(event.source));
    event.value0 = value0;
    event.value1 = value1;
    journal[journal_head] = event;
    journal_head = (journal_head + 1U) % ARRAY_COUNT(journal);
    if (statistics.journal_count < ARRAY_COUNT(journal)) {
        ++statistics.journal_count;
    } else {
        ++statistics.overwritten;
    }
    if (type >= 64U) {
        return false;
    }
    if (dispatching) {
        ++statistics.recursive_dispatches;
        return true;
    }
    dispatching = true;
    const u64 bit = 1ULL << (u32)type;
    for (usize index = 0U; index < statistics.subscriber_count; ++index) {
        if ((subscribers[index].mask & bit) == 0U) {
            continue;
        }
        ++statistics.callback_calls;
        if (subscribers[index].callback == NULL) {
            ++statistics.callback_failures;
            continue;
        }
        subscribers[index].callback(&event, subscribers[index].context);
    }
    dispatching = false;
    return true;
}

u64 event_bus_count(void)
{
    return statistics.journal_count;
}

bool event_bus_at(u64 requested, fbr34ker_event_t *event)
{
    if (!initialized || event == NULL || requested >= statistics.journal_count) {
        return false;
    }
    const usize oldest = statistics.journal_count == ARRAY_COUNT(journal)
        ? journal_head : 0U;
    *event = journal[(oldest + (usize)requested) % ARRAY_COUNT(journal)];
    return true;
}

fbr34ker_event_stats_t event_bus_stats(void)
{
    return statistics;
}

const char *event_type_name(fbr34ker_event_type_t type)
{
    switch (type) {
    case FBR34KER_EVENT_BOOT: return "boot";
    case FBR34KER_EVENT_COMPONENT_STATE: return "component";
    case FBR34KER_EVENT_SERVICE_STATE: return "service";
    case FBR34KER_EVENT_DRIVER_STATE: return "driver";
    case FBR34KER_EVENT_BRINGUP_MODE: return "bringup";
    case FBR34KER_EVENT_MODULE_LOADED: return "module-loaded";
    case FBR34KER_EVENT_MODULE_EXECUTED: return "module-executed";
    case FBR34KER_EVENT_MODULE_UNLOADED: return "module-unloaded";
    case FBR34KER_EVENT_ROLLBACK: return "rollback";
    case FBR34KER_EVENT_VALIDATION: return "validation";
    case FBR34KER_EVENT_KERNEL_PATCH: return "kernel-patch";
    case FBR34KER_EVENT_SECURE_BOOT_BYPASS: return "secure-boot-bypass";
    case FBR34KER_EVENT_PERSISTENCE: return "persistence";
    case FBR34KER_EVENT_EXPLOIT_CHAIN: return "exploit-chain";
    case FBR34KER_EVENT_COUNT: return "count";
    default: return "unknown";
    }
}
