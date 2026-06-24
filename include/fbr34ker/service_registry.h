#pragma once
#include "fbr34ker/types.h"

#define FBR34KER_SERVICE_CAPACITY 16U
#define FBR34KER_SERVICE_NAME_CAPACITY 32U
#define FBR34KER_SERVICE_OWNER_CAPACITY 24U

typedef enum {
    FBR34KER_SERVICE_ABSENT = 0,
    FBR34KER_SERVICE_DISCOVERED,
    FBR34KER_SERVICE_READY,
    FBR34KER_SERVICE_DEGRADED,
    FBR34KER_SERVICE_FAILED,
    FBR34KER_SERVICE_DISABLED
} fbr34ker_service_state_t;

typedef struct {
    char name[FBR34KER_SERVICE_NAME_CAPACITY];
    char owner[FBR34KER_SERVICE_OWNER_CAPACITY];
    u32 version;
    fbr34ker_service_state_t state;
    u64 platform_feature;
    u64 transitions;
} fbr34ker_service_info_t;

void service_registry_init(void);
void service_registry_shutdown(void);
bool service_registry_ready(void);
int service_registry_register(const char *name, const char *owner, u32 version,
                              u64 platform_feature,
                              fbr34ker_service_state_t initial_state);
bool service_registry_set_state(const char *name, fbr34ker_service_state_t state);
bool service_registry_find(const char *name, fbr34ker_service_info_t *information);
bool service_registry_find_compatible(const char *name, u32 minimum_version,
                                      u64 required_features,
                                      fbr34ker_service_info_t *information);
u64 service_registry_count(void);
bool service_registry_at(u64 index, fbr34ker_service_info_t *information);
bool service_registry_service_ready(const char *name);
bool service_registry_service_compatible(const char *name, u32 minimum_version,
                                         u64 required_features);
bool service_registry_healthy(void);
const char *service_state_name(fbr34ker_service_state_t state);
