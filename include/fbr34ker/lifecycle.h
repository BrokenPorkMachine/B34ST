#pragma once
#include "fbr34ker/types.h"

#define FBR34KER_LIFECYCLE_MAX_COMPONENTS 16U
#define FBR34KER_LIFECYCLE_NAME_CAPACITY 48U

typedef enum {
    FBR34KER_PHASE_EARLY = 0,
    FBR34KER_PHASE_CORE,
    FBR34KER_PHASE_PLATFORM,
    FBR34KER_PHASE_SERVICES,
    FBR34KER_PHASE_EXTENSIONS,
    FBR34KER_PHASE_INTERACTIVE,
    FBR34KER_PHASE_COUNT
} fbr34ker_lifecycle_phase_t;

typedef enum {
    FBR34KER_COMPONENT_REGISTERED = 0,
    FBR34KER_COMPONENT_STARTING,
    FBR34KER_COMPONENT_ACTIVE,
    FBR34KER_COMPONENT_BLOCKED,
    FBR34KER_COMPONENT_FAILED,
    FBR34KER_COMPONENT_STOPPING,
    FBR34KER_COMPONENT_STOPPED,
    FBR34KER_COMPONENT_ROLLED_BACK
} fbr34ker_component_state_t;

typedef bool (*fbr34ker_component_start_fn)(void);
typedef void (*fbr34ker_component_stop_fn)(void);
typedef bool (*fbr34ker_component_health_fn)(void);

typedef struct {
    const char *name;
    fbr34ker_lifecycle_phase_t phase;
    u64 requires;
    u64 provides;
    fbr34ker_component_start_fn start;
    fbr34ker_component_stop_fn stop;
    fbr34ker_component_health_fn health;
} fbr34ker_component_descriptor_t;

typedef struct {
    const char *name;
    fbr34ker_lifecycle_phase_t phase;
    fbr34ker_component_state_t state;
    u64 requires;
    u64 provides;
    u64 missing;
    u64 activation_sequence;
    bool healthy;
} fbr34ker_component_info_t;

typedef struct {
    u64 starts;
    u64 successful_starts;
    u64 failures;
    u64 rollbacks;
    u64 stops;
    u64 provided_capabilities;
    char last_failure[FBR34KER_LIFECYCLE_NAME_CAPACITY];
} fbr34ker_lifecycle_stats_t;

void lifecycle_init(void);
bool lifecycle_register(const fbr34ker_component_descriptor_t *descriptor);
bool lifecycle_start(void);
void lifecycle_stop(void);
u64 lifecycle_component_count(void);
bool lifecycle_component_info(u64 index, fbr34ker_component_info_t *information);
u64 lifecycle_provided_capabilities(void);
bool lifecycle_healthy(void);
fbr34ker_lifecycle_stats_t lifecycle_stats(void);
const char *lifecycle_phase_name(fbr34ker_lifecycle_phase_t phase);
const char *lifecycle_state_name(fbr34ker_component_state_t state);
