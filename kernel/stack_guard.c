#include "fbr34ker/stack_guard.h"
#include "fbr34ker/exception.h"
#include "fbr34ker/format.h"
#include "fbr34ker/string.h"

#define STACK_GUARD_PATTERN 0x6dU

extern u8 __stack_guard_low_start[];
extern u8 __stack_guard_low_end[];
extern u8 __stack_guard_high_start[];
extern u8 __stack_guard_high_end[];

u64 __stack_chk_guard = 0x8a5cd789635d2dffULL;

static bool region_is_guarded(const u8 *start, const u8 *end)
{
    for (const u8 *cursor = start; cursor < end; ++cursor) {
        if (*cursor != STACK_GUARD_PATTERN) {
            return false;
        }
    }
    return true;
}

void stack_guard_init(void)
{
    fm_memset(__stack_guard_low_start, STACK_GUARD_PATTERN,
              (usize)(__stack_guard_low_end - __stack_guard_low_start));
    fm_memset(__stack_guard_high_start, STACK_GUARD_PATTERN,
              (usize)(__stack_guard_high_end - __stack_guard_high_start));
}

bool stack_guard_check(void)
{
    return region_is_guarded(__stack_guard_low_start, __stack_guard_low_end) &&
           region_is_guarded(__stack_guard_high_start, __stack_guard_high_end);
}

u64 stack_guard_low_address(void)
{
    return (u64)(usize)__stack_guard_low_start;
}

u64 stack_guard_high_address(void)
{
    return (u64)(usize)__stack_guard_high_start;
}

NORETURN void __stack_chk_fail(void)
{
    fm_printf("\n*** stack protector failure ***\n");
    cpu_halt_forever();
}
