#pragma once
#include "fbr34ker/types.h"
#include <stdarg.h>

int fm_printf(const char *format, ...);
int fm_vprintf(const char *format, va_list arguments);
int fm_snprintf(char *buffer, usize capacity, const char *format, ...);
int fm_vsnprintf(char *buffer, usize capacity, const char *format,
                 va_list arguments);
