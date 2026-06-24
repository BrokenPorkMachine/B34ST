#ifndef FBR34KER_SDK_SERVICES_H
#define FBR34KER_SDK_SERVICES_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "fbr34ker_memory.h"

#define FBR34KER_PLATFORM_SERVICES_VERSION_1 1U
#define FBR34KER_SERVICE_CONSOLE_WRITE         (1ULL << 0)
#define FBR34KER_SERVICE_CONSOLE_READ          (1ULL << 1)
#define FBR34KER_SERVICE_CONSOLE_FLUSH         (1ULL << 2)
#define FBR34KER_SERVICE_FRAMEBUFFER_FLUSH     (1ULL << 3)
#define FBR34KER_SERVICE_INTERRUPT_CONTROLLER  (1ULL << 4)
#define FBR34KER_SERVICE_WATCHDOG_CONFIGURE    (1ULL << 5)
#define FBR34KER_SERVICE_WATCHDOG_KICK         (1ULL << 6)
#define FBR34KER_SERVICE_FLAGS_SUPPORTED       0x7fULL

typedef size_t (*fbr34ker_console_write_fn)(const char *, size_t, void *);
typedef size_t (*fbr34ker_console_read_fn)(char *, size_t, void *);
typedef void (*fbr34ker_console_flush_fn)(void *);
typedef bool (*fbr34ker_framebuffer_flush_fn)(void *);
typedef uint32_t (*fbr34ker_interrupt_ack_fn)(void *);
typedef void (*fbr34ker_interrupt_complete_fn)(uint32_t, void *);
typedef bool (*fbr34ker_interrupt_set_enabled_fn)(uint32_t, bool, void *);
typedef bool (*fbr34ker_watchdog_configure_fn)(uint64_t, void *);
typedef void (*fbr34ker_watchdog_kick_fn)(void *);

typedef struct FBR34KER_SDK_PACKED {
    uint32_t version;
    uint32_t structure_size;
    uint64_t capabilities;
    uint64_t reserved;
    fbr34ker_console_write_fn console_write;
    fbr34ker_console_read_fn console_read;
    fbr34ker_console_flush_fn console_flush;
    void *console_context;
    fbr34ker_framebuffer_flush_fn framebuffer_flush;
    void *framebuffer_context;
    fbr34ker_interrupt_ack_fn interrupt_ack;
    fbr34ker_interrupt_complete_fn interrupt_complete;
    fbr34ker_interrupt_set_enabled_fn interrupt_set_enabled;
    void *interrupt_context;
    fbr34ker_watchdog_configure_fn watchdog_configure;
    fbr34ker_watchdog_kick_fn watchdog_kick;
    void *watchdog_context;
} fbr34ker_platform_services_t;

#endif
