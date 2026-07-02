#pragma once
// SPDX-License-Identifier: BSD-2-Clause

typedef __UINT8_TYPE__  u8;
typedef __UINT16_TYPE__ u16;
typedef __UINT32_TYPE__ u32;
typedef __UINT64_TYPE__ u64;
typedef __INT8_TYPE__   i8;
typedef __INT16_TYPE__  i16;
typedef __INT32_TYPE__  i32;
typedef __INT64_TYPE__  i64;
typedef __SIZE_TYPE__   usize;
typedef __PTRDIFF_TYPE__ isize;
typedef _Bool bool;

#ifndef true
#define true 1
#endif
#ifndef false
#define false 0
#endif
#ifndef NULL
#define NULL ((void *)0)
#endif

#define U64_MAX_VALUE ((u64)~(u64)0)
#define USIZE_MAX_VALUE ((usize)~(usize)0)
#define ARRAY_COUNT(x) (sizeof(x) / sizeof((x)[0]))
#define UNUSED(x) ((void)(x))
#define NORETURN __attribute__((noreturn))
#define PACKED __attribute__((packed))
#define ALIGNED(x) __attribute__((aligned(x)))
#define STATIC_ASSERT(expr, msg) _Static_assert((expr), msg)

static inline bool usize_add_checked(usize left, usize right, usize *result)
{
    if (result == NULL || left > USIZE_MAX_VALUE - right) {
        return false;
    }
    *result = left + right;
    return true;
}

static inline bool u64_add_checked(u64 left, u64 right, u64 *result)
{
    if (result == NULL || left > U64_MAX_VALUE - right) {
        return false;
    }
    *result = left + right;
    return true;
}
