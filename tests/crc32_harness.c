#include "fbr34ker/crc32.h"

// SPDX-License-Identifier: BSD-2-Clause
int main(void)
{
    static const char text[] = "123456789";
    return crc32_compute(text, 9U) == 0xcbf43926U ? 0 : 1;
}
