#pragma once
// SPDX-License-Identifier: BSD-2-Clause
#include "fbr34ker/types.h"
#include "fbr34ker/usbliter8_v1_exploit.h"
#include "fbr34ker/usbliter8_v2_exploit.h"
#include "fbr34ker/log.h"

typedef enum {
    USBLITER8_OPERATION_PWNDFU = 0,
    USBLITER8_OPERATION_PATCH = 1,
    USBLITER8_OPERATION_LOAD = 2,
    USBLITER8_OPERATION_EXECUTE = 3,
    USBLITER8_OPERATION_RESET = 4,
} usbliter8_operation_t;

typedef enum {
    HUBSYS_STATUS_NONE_ACTIVE = 0,
    HUBSYS_STATUS_V1_ONLY = 1,
    HUBSYS_STATUS_V2_ONLY = 2,
    HUBSYS_STATUS_BOTH_ACTIVE = 3,
} hubsys_status_code_t;

typedef struct {
    hubsys_status_code_t overall_status;
    bool v1_working;
    bool v2_working;
} hubsys_status_t;

typedef struct {
    int current_mode;
    int fallback_count;
    bool v1_available;
    bool v2_available;
    bool v1_working;
    bool v2_working;
} usbliter8_orchestrator_t;

extern usbliter8_v1_status_t usbliter8_v1_exploit_status(void);
extern usbliter8_v2_status_t usbliter8_v2_exploit_status(void);

extern void usbliter8_orchestrator_init(void);
extern void usbliter8_orchestrator_cleanup(void);
extern bool usbliter8_orchestrator_is_ready(void);

extern usbliter8_v2_status_t usbliter8_orchestrator_status(void);
extern hubsys_status_t usbliter8_get_system_status(void);

extern bool usbliter8_execute_auto(usbliter8_operation_t operation, u64 param1, u64 param2);
extern void usbliter8_switch_mode(int mode);
extern void usbliter8_sync_status(void);