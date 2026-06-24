#pragma once
#include "fbr34ker/types.h"

void stack_guard_init(void);
bool stack_guard_check(void);
u64 stack_guard_low_address(void);
u64 stack_guard_high_address(void);
NORETURN void __stack_chk_fail(void);
extern u64 __stack_chk_guard;
