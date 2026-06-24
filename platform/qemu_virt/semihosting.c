#include "fbr34ker/platform.h"

bool platform_semihosting_available(void)
{
    return true;
}

bool platform_semihosting_putc(char value)
{
    register u64 operation __asm__("x0") = 0x03U; /* SYS_WRITEC */
    register const char *parameter __asm__("x1") = &value;
    __asm__ volatile("hlt #0xf000" : "+r"(operation) : "r"(parameter) : "memory");
    return true;
}
