#include "fbr34ker/trace.h"
#include "fbr34ker/format.h"
#include "fbr34ker/string.h"
#include <stdarg.h>

static fbr34ker_trace_record_t records[FBR34KER_TRACE_CAPACITY];
static fbr34ker_trace_stats_t statistics;
static usize head;

void trace_init(void)
{
    fm_memset(records, 0, sizeof(records));
    fm_memset(&statistics, 0, sizeof(statistics));
    statistics.initialized = true;
    head = 0U;
}

void trace_shutdown(void)
{
    statistics.initialized = false;
}

bool trace_ready(void)
{
    return statistics.initialized;
}

bool trace_emit(fbr34ker_trace_category_t category, u32 action, i32 status,
                const char *source, u64 value0, u64 value1)
{
    if (!statistics.initialized || category >= FBR34KER_TRACE_COUNT || source == NULL) {
        return false;
    }
    fbr34ker_trace_record_t record;
    fm_memset(&record, 0, sizeof(record));
    record.sequence = ++statistics.emitted;
    record.category = category;
    record.action = action;
    record.status = status;
    fm_strlcpy(record.source, source, sizeof(record.source));
    record.value0 = value0;
    record.value1 = value1;
    records[head] = record;
    head = (head + 1U) % ARRAY_COUNT(records);
    if (statistics.retained < ARRAY_COUNT(records)) {
        ++statistics.retained;
    } else {
        ++statistics.overwritten;
    }
    return true;
}

u64 trace_count(void)
{
    return statistics.retained;
}

bool trace_at(u64 requested, fbr34ker_trace_record_t *record)
{
    if (!statistics.initialized || record == NULL || requested >= statistics.retained) {
        return false;
    }
    const usize oldest = statistics.retained == ARRAY_COUNT(records) ? head : 0U;
    *record = records[(oldest + (usize)requested) % ARRAY_COUNT(records)];
    return true;
}

fbr34ker_trace_stats_t trace_stats(void)
{
    return statistics;
}

const char *trace_category_name(fbr34ker_trace_category_t category)
{
    switch (category) {
    case FBR34KER_TRACE_BOOT: return "boot";
    case FBR34KER_TRACE_LIFECYCLE: return "lifecycle";
    case FBR34KER_TRACE_SERVICE: return "service";
    case FBR34KER_TRACE_DRIVER: return "driver";
    case FBR34KER_TRACE_FAULT: return "fault";
    case FBR34KER_TRACE_VALIDATION: return "validation";
    case FBR34KER_TRACE_PANIC: return "panic";
    case FBR34KER_TRACE_COUNT: return "count";
    default: return "unknown";
    }
}

static usize append(char *buffer, usize capacity, usize offset,
                    const char *format, ...)
{
    if (buffer == NULL || capacity == 0U || offset >= capacity) {
        return offset;
    }
    va_list arguments;
    va_start(arguments, format);
    const int count = fm_vsnprintf(buffer + offset, capacity - offset,
                                   format, arguments);
    va_end(arguments);
    if (count <= 0) {
        return offset;
    }
    const usize amount = (usize)count;
    return amount >= capacity - offset ? capacity - 1U : offset + amount;
}

usize trace_export_json(char *buffer, usize capacity)
{
    if (buffer == NULL || capacity == 0U) {
        return 0U;
    }
    usize offset = append(buffer, capacity, 0U,
                          "{\"schema\":1,\"emitted\":%llu,\"overwritten\":%llu,\"records\":[",
                          statistics.emitted, statistics.overwritten);
    for (u64 index = 0U; index < trace_count(); ++index) {
        fbr34ker_trace_record_t record;
        if (!trace_at(index, &record)) {
            continue;
        }
        offset = append(buffer, capacity, offset,
                        "%s{\"sequence\":%llu,\"category\":\"%s\",\"action\":%u,"
                        "\"status\":%d,\"source\":\"%s\",\"value0\":%llu,\"value1\":%llu}",
                        index == 0U ? "" : ",", record.sequence,
                        trace_category_name(record.category), record.action,
                        record.status, record.source, record.value0, record.value1);
    }
    return append(buffer, capacity, offset, "]}\n");
}
