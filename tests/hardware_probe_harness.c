#include "fbr34ker/device_tree.h"
#include "fbr34ker/handoff.h"
#include "fbr34ker/hardware_probe.h"
#include "fbr34ker/platform.h"
#include "fbr34ker/timer.h"

// SPDX-License-Identifier: BSD-2-Clause
static const fbr34ker_handoff_t handoff = {0};
static const memory_region_t valid_regions[] = {
    { .base = 0x40000000ULL, .size = 0x00100000ULL, .type = MEMORY_REGION_RESERVED, .attributes = 0U, .name = "reserved" },
    { .base = 0x80000000ULL, .size = 0x00200000ULL, .type = MEMORY_REGION_MONITOR, .attributes = 0U, .name = "monitor" },
    { .base = 0x80200000ULL, .size = 0x01000000ULL, .type = MEMORY_REGION_USABLE, .attributes = 0U, .name = "usable" },
};

const fbr34ker_handoff_t *fbr34ker_handoff_active(void) { return &handoff; }
bool device_tree_valid(void) { return true; }
u64 platform_features(void)
{
    return PLATFORM_FEATURE_CONSOLE_OUTPUT | PLATFORM_FEATURE_CONSOLE_INPUT |
           PLATFORM_FEATURE_TIMER | PLATFORM_FEATURE_POWER |
           PLATFORM_FEATURE_FRAMEBUFFER | PLATFORM_FEATURE_INTERRUPTS |
           PLATFORM_FEATURE_WATCHDOG_CONFIGURE | PLATFORM_FEATURE_WATCHDOG_KICK;
}
u64 platform_memory_regions(const memory_region_t **regions)
{
    *regions = valid_regions;
    return ARRAY_COUNT(valid_regions);
}
u64 timer_frequency(void) { return 24000000ULL; }

static int require(bool condition, int code) { return condition ? 0 : code; }

int main(void)
{
    hardware_probe_init();
    int result = 0;
    result |= require(hardware_probe_active(), 1);
    result |= require(hardware_probe_immutable(), 2);
    result |= require(!hardware_probe_modules_allowed(), 4);
    result |= require(!hardware_probe_unlock(), 8);
    result |= require(hardware_probe_memory_map_valid(), 16);
    result |= require(hardware_probe_handoff_state() == HARDWARE_COMPAT_PASS, 32);
    result |= require(hardware_probe_console_output_state() == HARDWARE_COMPAT_PASS, 64);
    result |= require(hardware_probe_timer_state() == HARDWARE_COMPAT_PASS, 128);
    result |= require(hardware_probe_interrupt_state() == HARDWARE_COMPAT_NOT_TESTED, 256);
    result |= require(hardware_probe_framebuffer_state() == HARDWARE_COMPAT_LOCKED, 512);
    result |= require(hardware_probe_module_state() == HARDWARE_COMPAT_LOCKED, 1024);
    result |= require(hardware_probe_mark_validated(HARDWARE_PROBE_FEATURE_INTERRUPTS, true), 2048);
    result |= require(!hardware_probe_interrupt_mutation_allowed(), 4096);
    result |= require(hardware_probe_interrupt_state() == HARDWARE_COMPAT_PASS, 8192);
    return result;
}
