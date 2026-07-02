#include "fbr34ker/lifecycle.h"
#include "fbr34ker/trace.h"

// SPDX-License-Identifier: BSD-2-Clause
static bool first_started;
static bool second_started;
static u32 stop_order[4];
static u32 stop_count;

static bool first_start(void) { first_started = true; return true; }
static bool second_start(void) { second_started = first_started; return second_started; }
static bool failed_start(void) { return false; }
static void first_stop(void) { stop_order[stop_count++] = 1U; }
static void second_stop(void) { stop_order[stop_count++] = 2U; }
static bool healthy(void) { return true; }

static const fbr34ker_component_descriptor_t first = {
    .name = "first", .phase = FBR34KER_PHASE_CORE,
    .provides = 1ULL, .start = first_start, .stop = first_stop,
    .health = healthy,
};
static const fbr34ker_component_descriptor_t second = {
    .name = "second", .phase = FBR34KER_PHASE_SERVICES,
    .requires = 1ULL, .provides = 2ULL,
    .start = second_start, .stop = second_stop, .health = healthy,
};
static const fbr34ker_component_descriptor_t failure = {
    .name = "failure", .phase = FBR34KER_PHASE_EXTENSIONS,
    .requires = 2ULL, .provides = 4ULL, .start = failed_start,
};

int main(void)
{
    trace_init();
    lifecycle_init();
    if (!lifecycle_register(&second) || !lifecycle_register(&first)) return 1;
    if (!lifecycle_start() || !first_started || !second_started) return 2;
    if (!lifecycle_healthy() || lifecycle_provided_capabilities() != 3U) return 3;
    lifecycle_stop();
    if (stop_count != 2U || stop_order[0] != 2U || stop_order[1] != 1U) return 4;

    first_started = false;
    second_started = false;
    stop_count = 0U;
    lifecycle_init();
    if (!lifecycle_register(&failure) || !lifecycle_register(&second) ||
        !lifecycle_register(&first)) return 5;
    if (lifecycle_start()) return 6;
    if (stop_count != 2U || stop_order[0] != 2U || stop_order[1] != 1U) return 7;
    const fbr34ker_lifecycle_stats_t stats = lifecycle_stats();
    if (stats.failures != 1U || stats.rollbacks != 1U ||
        lifecycle_provided_capabilities() != 0U) return 8;
    fbr34ker_component_info_t information;
    if (!lifecycle_component_info(0U, &information) ||
        information.state != FBR34KER_COMPONENT_FAILED) return 9;
    return 0;
}
