#include "fbr34ker/interrupt.h"
#include "fbr34ker/platform.h"
#include "fbr34ker/hardware_probe.h"
#include "fbr34ker/string.h"

#define INTERRUPT_HANDLER_CAPACITY 32U

// SPDX-License-Identifier: BSD-2-Clause
typedef struct {
    bool used;
    u32 interrupt_id;
    interrupt_handler_fn handler;
    void *context;
} interrupt_slot_t;

static interrupt_slot_t slots[INTERRUPT_HANDLER_CAPACITY];
static interrupt_stats_t statistics;

void interrupt_init(void)
{
    fm_memset(slots, 0, sizeof(slots));
    fm_memset(&statistics, 0, sizeof(statistics));
    statistics.last_interrupt = PLATFORM_INTERRUPT_SPURIOUS;
    statistics.controller_available =
        (platform_features() & PLATFORM_FEATURE_INTERRUPTS) != 0U;
    __asm__ volatile("msr daifset, #2" ::: "memory");
}

bool interrupt_register(u32 interrupt_id, interrupt_handler_fn handler,
                        void *context)
{
    if (!hardware_probe_interrupt_mutation_allowed() ||
        handler == NULL || interrupt_id == PLATFORM_INTERRUPT_SPURIOUS) {
        return false;
    }
    for (usize index = 0U; index < ARRAY_COUNT(slots); ++index) {
        if (slots[index].used && slots[index].interrupt_id == interrupt_id) {
            return false;
        }
    }
    for (usize index = 0U; index < ARRAY_COUNT(slots); ++index) {
        if (!slots[index].used) {
            slots[index] = (interrupt_slot_t){
                .used = true,
                .interrupt_id = interrupt_id,
                .handler = handler,
                .context = context,
            };
            if (!platform_interrupt_set_enabled(interrupt_id, true)) {
                fm_memset(&slots[index], 0, sizeof(slots[index]));
                return false;
            }
            return true;
        }
    }
    return false;
}

bool interrupt_unregister(u32 interrupt_id)
{
    for (usize index = 0U; index < ARRAY_COUNT(slots); ++index) {
        if (slots[index].used && slots[index].interrupt_id == interrupt_id) {
            (void)platform_interrupt_set_enabled(interrupt_id, false);
            fm_memset(&slots[index], 0, sizeof(slots[index]));
            return true;
        }
    }
    return false;
}

bool interrupt_set_delivery(bool enabled)
{
    if (enabled && (!statistics.controller_available ||
                    !hardware_probe_interrupt_mutation_allowed())) {
        return false;
    }
    if (enabled) {
        __asm__ volatile("msr daifclr, #2\nisb" ::: "memory");
    } else {
        __asm__ volatile("msr daifset, #2\nisb" ::: "memory");
    }
    statistics.delivery_enabled = enabled;
    return true;
}

static bool is_interrupt_vector(u64 vector)
{
    const u64 slot = vector & 3U;
    return slot == 1U || slot == 2U;
}

bool interrupt_handle_vector(u64 vector)
{
    if (!is_interrupt_vector(vector) || !statistics.controller_available) {
        return false;
    }
    ++statistics.delivered;
    const u32 interrupt_id = platform_interrupt_ack();
    statistics.last_interrupt = interrupt_id;
    if (interrupt_id == PLATFORM_INTERRUPT_SPURIOUS) {
        ++statistics.spurious;
        return true;
    }

    bool handled = false;
    for (usize index = 0U; index < ARRAY_COUNT(slots); ++index) {
        if (slots[index].used && slots[index].interrupt_id == interrupt_id) {
            handled = slots[index].handler(interrupt_id, slots[index].context);
            break;
        }
    }
    if (handled) {
        ++statistics.handled;
    } else {
        ++statistics.unhandled;
        (void)platform_interrupt_set_enabled(interrupt_id, false);
    }
    platform_interrupt_complete(interrupt_id);
    return true;
}

interrupt_stats_t interrupt_stats(void)
{
    return statistics;
}
