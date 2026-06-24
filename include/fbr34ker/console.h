#pragma once
#include "fbr34ker/types.h"

#define CONSOLE_HISTORY_CAPACITY 4096U

typedef struct {
    u64 total_characters;
    u64 overwritten_characters;
    usize retained_characters;
} console_history_stats_t;

void console_init(void);
void console_putc(char value);
void console_write(const char *text);
void console_write_n(const char *text, usize length);
int console_getc_nonblocking(void);
char console_getc_blocking(void);
void console_capture_begin(char *buffer, usize capacity, bool suppress_uart);
usize console_capture_end(void);
usize console_history_copy(char *buffer, usize capacity);
console_history_stats_t console_history_stats(void);
bool console_semihosting_set(bool enabled);
bool console_semihosting_enabled(void);
