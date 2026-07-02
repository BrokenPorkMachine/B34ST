#include "fbr34ker/format.h"
#include "fbr34ker/string.h"

// SPDX-License-Identifier: BSD-2-Clause
int main(void)
{
    char buffer[160];
    const usize large = ((usize)1U << 40U);
    const int written = fm_snprintf(
        buffer, sizeof(buffer),
        "%-5s|%5s|%-5u|%05u|%zu|%zx|%zd|%05d|%5d",
        "xy", "xy", 7U, 7U, large, large, (isize)-3, -3, -3);
    const char *expected =
        "xy   |   xy|7    |00007|1099511627776|10000000000|-3|-0003|   -3";
    if (written != (int)fm_strlen(expected)) return 1;
    if (fm_strcmp(buffer, expected) != 0) return 2;

    if (fm_snprintf(buffer, sizeof(buffer), "%-4c|%4c", 'a', 'b') != 9) {
        return 3;
    }
    if (fm_strcmp(buffer, "a   |   b") != 0) return 4;
    return 0;
}
