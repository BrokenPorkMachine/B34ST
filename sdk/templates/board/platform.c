#include "fbr34ker/platform.h"
#include "fbr34ker/timer.h"

void platform_prepare(const void *boot_context) { (void)boot_context; }
void platform_init(void) { timer_init(); }
const char *platform_name(void) { return "{{NAME}}"; }
const char *platform_console_transport_name(void) { return "unimplemented"; }
u64 platform_features(void) { return 0U; }
void platform_uart_putc(char value) { (void)value; }
int platform_uart_getc_nonblocking(void) { return -1; }
void platform_console_flush(void) {}
void platform_reboot(void) { for (;;) __asm__ volatile("wfe"); }
void platform_shutdown(void) { for (;;) __asm__ volatile("wfe"); }
const memory_region_t *platform_memory_map(u64 *count) { *count = 0U; return 0; }
