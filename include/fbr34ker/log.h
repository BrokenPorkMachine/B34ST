#pragma once
#include "fbr34ker/types.h"

typedef enum {
    LOG_LEVEL_DEBUG = 0,
    LOG_LEVEL_INFO,
    LOG_LEVEL_WARN,
    LOG_LEVEL_ERROR
} log_level_t;

void log_init(void);
void log_write(log_level_t level, const char *format, ...);
void log_dump(void);
usize log_export_text(char *buffer, usize capacity);
