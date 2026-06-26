#pragma once
#include "fbr34ker/types.h"

#define FBR34KER_HAL_SIM_CONSOLE_CAPACITY 256U
#define FBR34KER_HAL_SIM_IRQ_CAPACITY 64U

typedef enum {
    FBR34KER_HAL_POWER_RUNNING = 0,
    FBR34KER_HAL_POWER_SHUTDOWN,
    FBR34KER_HAL_POWER_RESET
} fbr34ker_hal_power_state_t;

typedef struct {
    u64 features;
    u64 time_ms;
    char console[FBR34KER_HAL_SIM_CONSOLE_CAPACITY];
    usize console_length;
    bool irq_enabled[FBR34KER_HAL_SIM_IRQ_CAPACITY];
    bool irq_pending[FBR34KER_HAL_SIM_IRQ_CAPACITY];
    u32 framebuffer_color;
    u64 framebuffer_writes;
    bool watchdog_armed;
    u64 watchdog_deadline_ms;
    u64 watchdog_kicks;
    fbr34ker_hal_power_state_t power_state;
} fbr34ker_hal_sim_t;

void hal_sim_init(fbr34ker_hal_sim_t *simulation, u64 features);
bool hal_sim_console_putc(fbr34ker_hal_sim_t *simulation, char value);
void hal_sim_advance(fbr34ker_hal_sim_t *simulation, u64 milliseconds);
bool hal_sim_irq_enable(fbr34ker_hal_sim_t *simulation, u32 interrupt_id, bool enabled);
bool hal_sim_irq_raise(fbr34ker_hal_sim_t *simulation, u32 interrupt_id);
bool hal_sim_irq_ack(fbr34ker_hal_sim_t *simulation, u32 *interrupt_id);
bool hal_sim_framebuffer_clear(fbr34ker_hal_sim_t *simulation, u32 color);
bool hal_sim_watchdog_configure(fbr34ker_hal_sim_t *simulation, u64 timeout_ms);
bool hal_sim_watchdog_kick(fbr34ker_hal_sim_t *simulation);
bool hal_sim_watchdog_expired(const fbr34ker_hal_sim_t *simulation);
bool hal_sim_power_request(fbr34ker_hal_sim_t *simulation, fbr34ker_hal_power_state_t state);
