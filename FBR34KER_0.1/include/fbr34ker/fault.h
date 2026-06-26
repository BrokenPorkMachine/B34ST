#pragma once
#include "fbr34ker/types.h"

#define FBR34KER_FAULT_SOURCE_CAPACITY 32U

typedef enum {
    FBR34KER_FAULT_COMPONENT_START = 0,
    FBR34KER_FAULT_DRIVER_PROBE,
    FBR34KER_FAULT_DRIVER_START,
    FBR34KER_FAULT_SERVICE_REGISTER,
    FBR34KER_FAULT_EVENT_PUBLISH,
    FBR34KER_FAULT_TIMEOUT,
    FBR34KER_FAULT_POINT_COUNT
} fbr34ker_fault_point_t;

typedef struct {
    bool enabled;
    fbr34ker_fault_point_t point;
    char source[FBR34KER_FAULT_SOURCE_CAPACITY];
    u32 trigger_after;
    u32 remaining;
    u64 checks;
    u64 injections;
} fbr34ker_fault_status_t;

void fault_injection_init(void);
void fault_injection_shutdown(void);
bool fault_injection_available(void);
bool fault_injection_arm(fbr34ker_fault_point_t point, const char *source,
                         u32 trigger_after, u32 count);
void fault_injection_disarm(void);
bool fault_injection_should_fail(fbr34ker_fault_point_t point, const char *source);
fbr34ker_fault_status_t fault_injection_status(void);
const char *fault_point_name(fbr34ker_fault_point_t point);
bool fault_point_parse(const char *name, fbr34ker_fault_point_t *point);
