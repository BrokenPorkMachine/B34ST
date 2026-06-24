#pragma once
#include "fbr34ker/types.h"

#define FBR34KER_DRIVER_CAPACITY 16U
#define FBR34KER_DRIVER_NAME_CAPACITY 32U

typedef enum {
    FBR34KER_DRIVER_REGISTERED = 0,
    FBR34KER_DRIVER_MATCHED,
    FBR34KER_DRIVER_PROBED,
    FBR34KER_DRIVER_ACTIVE,
    FBR34KER_DRIVER_BLOCKED,
    FBR34KER_DRIVER_FAILED,
    FBR34KER_DRIVER_STOPPED
} fbr34ker_driver_state_t;

typedef bool (*fbr34ker_driver_probe_fn)(void);
typedef bool (*fbr34ker_driver_start_fn)(void);
typedef void (*fbr34ker_driver_stop_fn)(void);

typedef struct {
    const char *name;
    const char *owner;
    u32 priority;
    u64 required_features;
    const char *dependency_service;
    u32 dependency_min_version;
    u64 dependency_features;
    const char *provided_service;
    fbr34ker_driver_probe_fn probe;
    fbr34ker_driver_start_fn start;
    fbr34ker_driver_stop_fn stop;
} fbr34ker_driver_descriptor_t;

typedef struct {
    char name[FBR34KER_DRIVER_NAME_CAPACITY];
    char owner[24];
    char dependency_service[32];
    char provided_service[32];
    u32 priority;
    u32 dependency_min_version;
    u64 required_features;
    u64 dependency_features;
    fbr34ker_driver_state_t state;
    u64 transitions;
} fbr34ker_driver_info_t;

void driver_manager_init(void);
void driver_manager_shutdown(void);
bool driver_manager_ready(void);
bool driver_register(const fbr34ker_driver_descriptor_t *descriptor);
bool driver_start_all(u64 platform_features);
void driver_stop_all(void);
u64 driver_count(void);
bool driver_at(u64 index, fbr34ker_driver_info_t *information);
bool driver_manager_healthy(void);
const char *driver_state_name(fbr34ker_driver_state_t state);
