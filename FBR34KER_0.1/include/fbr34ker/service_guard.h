#pragma once
#include "fbr34ker/types.h"

typedef enum {
    SERVICE_GUARD_CONSOLE_WRITE = 0,
    SERVICE_GUARD_CONSOLE_READ,
    SERVICE_GUARD_CONSOLE_FLUSH,
    SERVICE_GUARD_FRAMEBUFFER_FLUSH,
    SERVICE_GUARD_INTERRUPT_ACK,
    SERVICE_GUARD_INTERRUPT_COMPLETE,
    SERVICE_GUARD_INTERRUPT_ENABLE,
    SERVICE_GUARD_WATCHDOG_CONFIGURE,
    SERVICE_GUARD_WATCHDOG_KICK,
    SERVICE_GUARD_RUNTIME_INPUT,
    SERVICE_GUARD_TIMER_READ,
    SERVICE_GUARD_TIMER_FREQUENCY,
    SERVICE_GUARD_REBOOT,
    SERVICE_GUARD_HALT,
    SERVICE_GUARD_COUNT
} service_guard_id_t;

typedef struct {
    u64 calls;
    u64 failures;
    u64 overruns;
    u64 recursive_denials;
    u64 last_duration_ticks;
    u32 consecutive_failures;
    bool active;
    bool disabled;
} service_guard_status_t;

void service_guard_init(void);
bool service_guard_begin(service_guard_id_t id);
void service_guard_end(service_guard_id_t id, bool success);
bool service_guard_available(service_guard_id_t id);
service_guard_status_t service_guard_status(service_guard_id_t id);
const char *service_guard_name(service_guard_id_t id);
