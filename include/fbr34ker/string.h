#pragma once
// SPDX-License-Identifier: BSD-2-Clause
#include "fbr34ker/types.h"

void *fm_memset(void *destination, int value, usize count);
void *fm_memcpy(void *destination, const void *source, usize count);
void *fm_memmove(void *destination, const void *source, usize count);
int fm_memcmp(const void *left, const void *right, usize count);
usize fm_strlen(const char *text);
int fm_strcmp(const char *left, const char *right);
int fm_strncmp(const char *left, const char *right, usize count);
usize fm_strlcpy(char *destination, const char *source, usize capacity);

/* Compiler/runtime compatibility symbols for freestanding builds. */
void *memset(void *destination, int value, usize count);
void *memcpy(void *destination, const void *source, usize count);
void *memmove(void *destination, const void *source, usize count);
int memcmp(const void *left, const void *right, usize count);
usize strlen(const char *text);
