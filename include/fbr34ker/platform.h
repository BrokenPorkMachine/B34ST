#pragma once
// SPDX-License-Identifier: BSD-2-Clause
#include "fbr34ker/types.h"

typedef enum {
    MEMORY_REGION_USABLE = 1,
    MEMORY_REGION_RESERVED = 2,
    MEMORY_REGION_MMIO = 3,
    MEMORY_REGION_MONITOR = 4,
    MEMORY_REGION_FRAMEBUFFER = 5
} memory_region_type_t;

typedef struct {
    u64 base;
    u64 size;
    memory_region_type_t type;
    u32 attributes;
    const char *name;
} memory_region_t;

typedef struct {
    u64 base;
    u64 size;
    u32 width;
    u32 height;
    u32 pixels_per_row;
    u32 pixel_format;
    u32 bytes_per_pixel;
    u32 rotation;
} platform_framebuffer_t;

#define PLATFORM_FEATURE_CONSOLE_OUTPUT  (1ULL << 0)
#define PLATFORM_FEATURE_CONSOLE_INPUT   (1ULL << 1)
#define PLATFORM_FEATURE_CONSOLE_FLUSH   (1ULL << 2)
#define PLATFORM_FEATURE_TIMER           (1ULL << 3)
#define PLATFORM_FEATURE_POWER           (1ULL << 4)
#define PLATFORM_FEATURE_FRAMEBUFFER     (1ULL << 5)
#define PLATFORM_FEATURE_FRAMEBUFFER_FLUSH (1ULL << 6)
#define PLATFORM_FEATURE_INTERRUPTS      (1ULL << 7)
#define PLATFORM_FEATURE_WATCHDOG_CONFIGURE (1ULL << 8)
#define PLATFORM_FEATURE_WATCHDOG_KICK   (1ULL << 9)
#define PLATFORM_FEATURE_MEMORY_CONSOLE   (1ULL << 10)
#define PLATFORM_FEATURE_SEMIHOSTING      (1ULL << 11)
#define PLATFORM_FEATURE_DIRECT_GIC       (1ULL << 12)
#define PLATFORM_FEATURE_DIRECT_PL011     (1ULL << 13)

#define PLATFORM_INTERRUPT_SPURIOUS 0xffffffffU

void platform_prepare(const void *boot_context);
void platform_init(void);
const char *platform_name(void);
const char *platform_console_transport_name(void);
u64 platform_features(void);

void platform_uart_putc(char value);
int platform_uart_getc_nonblocking(void);
void platform_console_flush(void);

u64 platform_memory_regions(const memory_region_t **regions);
bool platform_framebuffer_info(platform_framebuffer_t *framebuffer);
bool platform_framebuffer_clear(u32 color);
bool platform_framebuffer_flush(void);

u32 platform_interrupt_ack(void);
void platform_interrupt_complete(u32 interrupt_id);
bool platform_interrupt_set_enabled(u32 interrupt_id, bool enabled);
bool platform_interrupt_self_test(void);
const char *platform_interrupt_controller_name(void);

bool platform_semihosting_available(void);
bool platform_semihosting_putc(char value);

bool platform_watchdog_configure(u64 timeout_ms);
void platform_watchdog_kick(void);

NORETURN void platform_reboot(void);
NORETURN void platform_halt(void);
