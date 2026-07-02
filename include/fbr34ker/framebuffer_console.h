#pragma once
// SPDX-License-Identifier: BSD-2-Clause
#include "fbr34ker/types.h"

typedef struct {
    bool available;
    bool enabled;
    u32 columns;
    u32 rows;
    u32 cursor_column;
    u32 cursor_row;
    u64 rendered_characters;
    u64 scroll_count;
} framebuffer_console_stats_t;

void framebuffer_console_init(void);
bool framebuffer_console_set_enabled(bool enabled);
bool framebuffer_console_enabled(void);
void framebuffer_console_putc(char value);
void framebuffer_console_write(const char *text);
bool framebuffer_console_clear(void);
void framebuffer_console_panic(const char *message);
framebuffer_console_stats_t framebuffer_console_stats(void);
