#pragma once
// SPDX-License-Identifier: BSD-2-Clause
#include "fbr34ker/types.h"

typedef enum {
    LOG_LEVEL_TRACE = -1,
    LOG_LEVEL_DEBUG = 0,
    LOG_LEVEL_INFO,
    LOG_LEVEL_VERBOSE,
    LOG_LEVEL_WARN,
    LOG_LEVEL_ERROR
} log_level_t;

void log_init(void);
void log_write(log_level_t level, const char *format, ...);
void log_dump(void);
usize log_export_text(char *buffer, usize capacity);
void log_set_level(log_level_t level);
log_level_t log_get_level(void);
const char *log_level_name(log_level_t level);

#define log_trace(...)   log_write(LOG_LEVEL_TRACE, __VA_ARGS__)
#define log_debug(...)   log_write(LOG_LEVEL_DEBUG, __VA_ARGS__)
#define log_info(...)    log_write(LOG_LEVEL_INFO, __VA_ARGS__)
#define log_verbose(...) log_write(LOG_LEVEL_VERBOSE, __VA_ARGS__)
#define log_warn(...)    log_write(LOG_LEVEL_WARN, __VA_ARGS__)
#define log_error(...)   log_write(LOG_LEVEL_ERROR, __VA_ARGS__)