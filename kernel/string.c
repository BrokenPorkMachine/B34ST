#include "fbr34ker/string.h"

// SPDX-License-Identifier: BSD-2-Clause
void *fm_memset(void *destination, int value, usize count)
{
    if (destination == NULL || count == 0U) {
        return destination;
    }
    u8 *bytes = (u8 *)destination;
    for (usize index = 0U; index < count; ++index) {
        bytes[index] = (u8)value;
    }
    return destination;
}

void *fm_memcpy(void *destination, const void *source, usize count)
{
    if (destination == NULL || source == NULL || count == 0U) {
        return destination;
    }
    u8 *out = (u8 *)destination;
    const u8 *in = (const u8 *)source;
    for (usize index = 0U; index < count; ++index) {
        out[index] = in[index];
    }
    return destination;
}

void *fm_memmove(void *destination, const void *source, usize count)
{
    u8 *out = (u8 *)destination;
    const u8 *in = (const u8 *)source;

    if (out == NULL || in == NULL || count == 0U) {
        return destination;
    }

    if (out < in) {
        for (usize index = 0U; index < count; ++index) {
            out[index] = in[index];
        }
    } else {
        for (usize index = count; index > 0U; --index) {
            out[index - 1U] = in[index - 1U];
        }
    }
    return destination;
}

int fm_memcmp(const void *left, const void *right, usize count)
{
    if (left == NULL || right == NULL || count == 0U) {
        return (left == right) ? 0 : (left == NULL ? -1 : 1);
    }
    const u8 *a = (const u8 *)left;
    const u8 *b = (const u8 *)right;
    for (usize index = 0U; index < count; ++index) {
        if (a[index] != b[index]) {
            return (int)a[index] - (int)b[index];
        }
    }
    return 0;
}

usize fm_strlen(const char *text)
{
    if (text == NULL) {
        return 0U;
    }
    usize length = 0U;
    while (text[length] != '\0') {
        ++length;
    }
    return length;
}

int fm_strcmp(const char *left, const char *right)
{
    if (left == NULL || right == NULL) {
        return (left == right) ? 0 : (left == NULL ? -1 : 1);
    }
    usize index = 0U;
    while (left[index] != '\0' && left[index] == right[index]) {
        ++index;
    }
    return (int)(u8)left[index] - (int)(u8)right[index];
}

int fm_strncmp(const char *left, const char *right, usize count)
{
    if (left == NULL || right == NULL || count == 0U) {
        return (left == right) ? 0 : (left == NULL ? -1 : 1);
    }
    for (usize index = 0U; index < count; ++index) {
        const u8 a = (u8)left[index];
        const u8 b = (u8)right[index];
        if (a != b) {
            return (int)a - (int)b;
        }
        if (a == 0U) {
            return 0;
        }
    }
    return 0;
}

usize fm_strlcpy(char *destination, const char *source, usize capacity)
{
    if (destination == NULL || capacity == 0U) {
        return 0U;
    }
    const usize source_length = fm_strlen(source);
    usize copy_length = source_length;
    if (copy_length >= capacity) {
        copy_length = capacity - 1U;
    }
    if (source != NULL && copy_length > 0U) {
        fm_memcpy(destination, source, copy_length);
    }
    destination[copy_length] = '\0';
    return source_length;
}

void *memset(void *destination, int value, usize count)
{
    return fm_memset(destination, value, count);
}

void *memcpy(void *destination, const void *source, usize count)
{
    return fm_memcpy(destination, source, count);
}

void *memmove(void *destination, const void *source, usize count)
{
    return fm_memmove(destination, source, count);
}

int memcmp(const void *left, const void *right, usize count)
{
    return fm_memcmp(left, right, count);
}

usize strlen(const char *text)
{
    return fm_strlen(text);
}
