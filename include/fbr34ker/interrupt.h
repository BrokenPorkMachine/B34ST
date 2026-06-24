#pragma once
#include "fbr34ker/types.h"

typedef bool (*interrupt_handler_fn)(u32 interrupt_id, void *context);

typedef struct {
    u64 delivered;
    u64 handled;
    u64 unhandled;
    u64 spurious;
    u32 last_interrupt;
    bool controller_available;
    bool delivery_enabled;
} interrupt_stats_t;

void interrupt_init(void);
bool interrupt_register(u32 interrupt_id, interrupt_handler_fn handler,
                        void *context);
bool interrupt_unregister(u32 interrupt_id);
bool interrupt_set_delivery(bool enabled);
bool interrupt_handle_vector(u64 vector);
interrupt_stats_t interrupt_stats(void);
