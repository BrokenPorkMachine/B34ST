#include "fbr34ker/log.h"
#include "fbr34ker/format.h"
#include "fbr34ker/string.h"
#include "fbr34ker/timer.h"
#include <stdarg.h>

#define LOG_ENTRY_COUNT 64U
#define LOG_TEXT_SIZE 160U
#define LOG_DEFAULT_LEVEL LOG_LEVEL_INFO

typedef struct {
    u64 timestamp_ms;
    log_level_t level;
    char text[LOG_TEXT_SIZE];
} log_entry_t;

static log_entry_t entries[LOG_ENTRY_COUNT];
static usize next_entry;
static usize stored_entries;
static log_level_t current_level = LOG_DEFAULT_LEVEL;

void log_set_level(log_level_t level)
{
    current_level = level;
}

log_level_t log_get_level(void)
{
    return current_level;
}

const char *log_level_name(log_level_t level)
{
    switch (level) {
    case LOG_LEVEL_TRACE:   return "TRACE";
    case LOG_LEVEL_DEBUG:   return "DEBUG";
    case LOG_LEVEL_INFO:    return "INFO";
    case LOG_LEVEL_VERBOSE: return "VERBOSE";
    case LOG_LEVEL_WARN:    return "WARN";
    case LOG_LEVEL_ERROR:   return "ERROR";
    default:                return "?";
    }
}

void log_init(void)
{
    fm_memset(entries, 0, sizeof(entries));
    next_entry = 0U;
    stored_entries = 0U;
    current_level = LOG_DEFAULT_LEVEL;
}

void log_write(log_level_t level, const char *format, ...)
{
    if (level < current_level) {
        return;
    }

    log_entry_t *entry = &entries[next_entry];
    entry->timestamp_ms = timer_uptime_ms();
    entry->level = level;

    va_list arguments;
    va_start(arguments, format);
    (void)fm_vsnprintf(entry->text, sizeof(entry->text), format, arguments);
    va_end(arguments);

    fm_printf("[%llu ms] %s: %s\n", entry->timestamp_ms,
              log_level_name(level), entry->text);

    next_entry = (next_entry + 1U) % LOG_ENTRY_COUNT;
    if (stored_entries < LOG_ENTRY_COUNT) {
        ++stored_entries;
    }
}

static usize append_text(char *buffer, usize capacity, usize offset,
                         const char *format, ...)
{
    if (buffer == NULL || capacity == 0U || offset >= capacity) {
        return offset;
    }
    va_list arguments;
    va_start(arguments, format);
    const int written = fm_vsnprintf(buffer + offset, capacity - offset,
                                     format, arguments);
    va_end(arguments);
    if (written <= 0) {
        return offset;
    }
    const usize amount = (usize)written;
    return amount > capacity - offset - 1U
        ? capacity - 1U : offset + amount;
}

usize log_export_text(char *buffer, usize capacity)
{
    if (buffer == NULL || capacity == 0U) {
        return 0U;
    }
    buffer[0] = '\0';
    if (stored_entries == 0U) {
        return append_text(buffer, capacity, 0U, "No log entries.\n");
    }
    usize offset = 0U;
    const usize first = stored_entries == LOG_ENTRY_COUNT ? next_entry : 0U;
    for (usize index = 0U; index < stored_entries; ++index) {
        const log_entry_t *entry = &entries[(first + index) % LOG_ENTRY_COUNT];
        offset = append_text(buffer, capacity, offset, "[%llu ms] %s: %s\n",
                             entry->timestamp_ms, log_level_name(entry->level),
                             entry->text);
        if (offset + 1U >= capacity) {
            break;
        }
    }
    return offset;
}

void log_dump(void)
{
    char text[8192];
    const usize length = log_export_text(text, sizeof(text));
    if (length != 0U) {
        fm_printf("%s", text);
    }
}
