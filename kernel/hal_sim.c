#include "fbr34ker/hal_sim.h"
#include "fbr34ker/platform.h"
#include "fbr34ker/string.h"

void hal_sim_init(fbr34ker_hal_sim_t *simulation, u64 features)
{
    if (simulation == NULL) {
        return;
    }
    fm_memset(simulation, 0, sizeof(*simulation));
    simulation->features = features;
    simulation->power_state = FBR34KER_HAL_POWER_RUNNING;
}

bool hal_sim_console_putc(fbr34ker_hal_sim_t *simulation, char value)
{
    if (simulation == NULL ||
        (simulation->features & PLATFORM_FEATURE_CONSOLE_OUTPUT) == 0U ||
        simulation->console_length + 1U >= sizeof(simulation->console)) {
        return false;
    }
    simulation->console[simulation->console_length++] = value;
    simulation->console[simulation->console_length] = '\0';
    return true;
}

void hal_sim_advance(fbr34ker_hal_sim_t *simulation, u64 milliseconds)
{
    if (simulation != NULL && (simulation->features & PLATFORM_FEATURE_TIMER) != 0U) {
        simulation->time_ms += milliseconds;
    }
}

bool hal_sim_irq_enable(fbr34ker_hal_sim_t *simulation, u32 interrupt_id, bool enabled)
{
    if (simulation == NULL ||
        (simulation->features & PLATFORM_FEATURE_INTERRUPTS) == 0U ||
        interrupt_id >= FBR34KER_HAL_SIM_IRQ_CAPACITY) {
        return false;
    }
    simulation->irq_enabled[interrupt_id] = enabled;
    return true;
}

bool hal_sim_irq_raise(fbr34ker_hal_sim_t *simulation, u32 interrupt_id)
{
    if (simulation == NULL || interrupt_id >= FBR34KER_HAL_SIM_IRQ_CAPACITY ||
        !simulation->irq_enabled[interrupt_id]) {
        return false;
    }
    simulation->irq_pending[interrupt_id] = true;
    return true;
}

bool hal_sim_irq_ack(fbr34ker_hal_sim_t *simulation, u32 *interrupt_id)
{
    if (simulation == NULL || interrupt_id == NULL) {
        return false;
    }
    for (u32 index = 0U; index < FBR34KER_HAL_SIM_IRQ_CAPACITY; ++index) {
        if (simulation->irq_pending[index] && simulation->irq_enabled[index]) {
            simulation->irq_pending[index] = false;
            *interrupt_id = index;
            return true;
        }
    }
    return false;
}

bool hal_sim_framebuffer_clear(fbr34ker_hal_sim_t *simulation, u32 color)
{
    if (simulation == NULL ||
        (simulation->features & PLATFORM_FEATURE_FRAMEBUFFER) == 0U) {
        return false;
    }
    simulation->framebuffer_color = color;
    ++simulation->framebuffer_writes;
    return true;
}

bool hal_sim_watchdog_configure(fbr34ker_hal_sim_t *simulation, u64 timeout_ms)
{
    if (simulation == NULL || timeout_ms == 0U ||
        (simulation->features & PLATFORM_FEATURE_WATCHDOG_CONFIGURE) == 0U) {
        return false;
    }
    simulation->watchdog_armed = true;
    simulation->watchdog_deadline_ms = simulation->time_ms + timeout_ms;
    return true;
}

bool hal_sim_watchdog_kick(fbr34ker_hal_sim_t *simulation)
{
    if (simulation == NULL || !simulation->watchdog_armed ||
        (simulation->features & PLATFORM_FEATURE_WATCHDOG_KICK) == 0U) {
        return false;
    }
    const u64 interval = simulation->watchdog_deadline_ms > simulation->time_ms
        ? simulation->watchdog_deadline_ms - simulation->time_ms : 1U;
    simulation->watchdog_deadline_ms = simulation->time_ms + interval;
    ++simulation->watchdog_kicks;
    return true;
}

bool hal_sim_watchdog_expired(const fbr34ker_hal_sim_t *simulation)
{
    return simulation != NULL && simulation->watchdog_armed &&
           simulation->time_ms >= simulation->watchdog_deadline_ms;
}

bool hal_sim_power_request(fbr34ker_hal_sim_t *simulation, fbr34ker_hal_power_state_t state)
{
    if (simulation == NULL || state > FBR34KER_HAL_POWER_RESET ||
        (simulation->features & PLATFORM_FEATURE_POWER) == 0U) {
        return false;
    }
    simulation->power_state = state;
    return true;
}
