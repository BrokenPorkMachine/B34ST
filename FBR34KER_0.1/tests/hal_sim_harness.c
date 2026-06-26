#include "fbr34ker/hal_sim.h"
#include "fbr34ker/platform.h"
#include "fbr34ker/string.h"

int main(void)
{
    const u64 features = PLATFORM_FEATURE_CONSOLE_OUTPUT | PLATFORM_FEATURE_TIMER |
                         PLATFORM_FEATURE_INTERRUPTS | PLATFORM_FEATURE_FRAMEBUFFER |
                         PLATFORM_FEATURE_WATCHDOG_CONFIGURE |
                         PLATFORM_FEATURE_WATCHDOG_KICK | PLATFORM_FEATURE_POWER;
    fbr34ker_hal_sim_t simulation;
    hal_sim_init(&simulation, features);
    if (!hal_sim_console_putc(&simulation, 'O') ||
        !hal_sim_console_putc(&simulation, 'K') ||
        fm_strcmp(simulation.console, "OK") != 0) return 1;
    if (!hal_sim_irq_enable(&simulation, 7U, true) ||
        !hal_sim_irq_raise(&simulation, 7U)) return 2;
    u32 interrupt_id = 0U;
    if (!hal_sim_irq_ack(&simulation, &interrupt_id) || interrupt_id != 7U) return 3;
    if (!hal_sim_framebuffer_clear(&simulation, 0x112233U) ||
        simulation.framebuffer_writes != 1U) return 4;
    if (!hal_sim_watchdog_configure(&simulation, 100U)) return 5;
    hal_sim_advance(&simulation, 50U);
    if (hal_sim_watchdog_expired(&simulation) || !hal_sim_watchdog_kick(&simulation)) return 6;
    hal_sim_advance(&simulation, 51U);
    if (!hal_sim_watchdog_expired(&simulation)) return 7;
    if (!hal_sim_power_request(&simulation, FBR34KER_HAL_POWER_RESET) ||
        simulation.power_state != FBR34KER_HAL_POWER_RESET) return 8;
    return 0;
}
