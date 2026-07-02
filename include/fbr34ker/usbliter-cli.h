#pragma once
// SPDX-License-Identifier: BSD-2-Clause
#include "fbr34ker/types.h"
#include "fbr34ker/usbliter8_v1_exploit.h"
#include "fbr34ker/usbliter8_v2_exploit.h"
#include "fbr34ker/log.h"
#include "fbr34ker/event.h"

// Core Orchestrator Implementation
// Intelligent USBliter8 Version Management System
// Integrates V1 and V2 with automatic fallbacks and reliability tracking

#define ORCHESTRATOR_VERSION "2.1.0"
#define MAX_FALLBACK_ATTEMPTS 3
#define RELIABILITY_THRESHOLD 0.7
#define MIN_EXECUTION_ATTEMPTS 5

// Orchestrator states for version management
typedef enum {
    ORCHESTRATOR_STATE_INITIALIZING = 0,
    ORCHESTRATOR_STATE_MONITORING,
    ORCHESTRATOR_STATE_EXECUTING,
    ORCHESTRATOR_STATE_FALLBACK,
    ORCHESTRATOR_STATE_OPTIMIZING,
    ORCHESTRATOR_STATE_TERMINATED
} orchestrator_state_t;

// Version selection strategies
typedef enum {
    VERSION_SELECTION_AUTO = 0,
    VERSION_SELECTION_PREFER_V1,
    VERSION_SELECTION_PREFER_V2,
    VERSION_SELECTION_RELIABILITY_BASED,
    VERSION_SELECTION_PER_CPUID
} version_selection_strategy_t;

// Reliability tracking structure
typedef struct {
    u16 cpid;
    u32 execution_successes;
    u32 execution_failures;
    u32 fallback_attempts;
    u32 patch_applications;
    u64 total_execution_time_ms;
    u8 version_preference;  // V1 or V2
    bool is_reliable;
    f64 reliability_score;
    f64 average_execution_time;
    u64 last_successful_execution;
    u64 consecutive_failures;
} version_reliability_t;

// Orchestrator state structure
typedef struct {
    orchestrator_state_t state;
    version_selection_strategy_t selection_strategy;
    u32 orchestrator_id;
    u64 start_timestamp;
    bool v1_available;
    bool v2_available;
    version_reliability_t* reliability_data;
    usize reliability_capacity;
    usbliter8_v1_status_t* v1_status;
    usbliter8_v2_status_t* v2_status;
    u8 current_version;  // 1 or 2
    u8 fallback_count;
    u8 successful_executions;
    bool is_healthy;
    f64 overall_system_health;
} usbliter8_orchestrator_t;

// Global orchestrator instance
static usbliter8_orchestrator_t g_orchestrator;

// Core orchestrator functions
void usbliter8_orchestrator_init(void);
void usbliter8_orchestrator_cleanup(void);
bool usbliter8_orchestrator_is_ready(void);

// Version management functions
bool usbliter8_orchestrator_select_version(u16 cpid);
bool usbliter8_orchestrator_execute_with_fallback(u16 cpid, usbliter8_operation_t operation);
bool usbliter8_orchestrator_ensure_version(u8 version);
bool usbliter8_orchestrator_maintain_version_health(void);

// Reliability and performance functions
void usbliter8_orchestrator_record_execution_result(u16 cpid, u8 version, bool success, u64 execution_time_ms, bool was_patch);
bool usbliter8_orchestrator_update_reliability_score(u16 cpid);
bool usbliter8_updater_reliability_data_consistency(void);

// State management functions
void usbliter8_orchestrator_update_state(orchestrator_state_t new_state);
bool usbliter8_orchestrator_is_state_transient(void);
bool usbliter8_orchestrator_should_switch_version(u16 cpid);

// Status and reporting functions
void usbliter8_orchestrator_report_status(void);
bool usbliter8_orchestrator_generate_health_report(void);
bool usbliter8_orchestrator_export_metrics(const char* output_path);

// Configuration and control
void usbliter8_orchestrator_set_selection_strategy(version_selection_strategy_t strategy);
void usbliter8_orchestrator_set_fallback_limit(u8 max_attempts);
void usbliter8_orchestrator_enable_version(u8 version, bool enable);
bool usbliter8_orchestrator_is_version_enabled(u8 version);

// High-level orchestration functions
bool usbliter8_orchestrator_handle_pwndfu(u16 cpid);
bool usbliter8_orchestrator_handle_patch(u16 cpid);
bool usbliter8_orchestrator_handle_load(u16 cpid, u64 address);
bool usbliter8_orchestrator_handle_execute(u64 entry_point);
bool usbliter8_orchestrator_handle_reset(void);

// Event handling
void usbliter8_orchestrator_on_execution_complete(u16 cpid, u8 version, bool success, u64 execution_time_ms);
void usbliter8_orchestrator_on_fallback_triggered(u8 from_version, u8 to_version, u16 cpid);
void usbliter8_orchestrator_on_reliability_change(u16 cpid, f64 new_score);

// Utility functions
static void initialize_reliability_data(void);
static u8 determine_best_version_for_cpid(u16 cpid);
static f64 calculate_cpid_reliability_score(u16 cpid);
static bool should_fallback_due_to_failures(u16 cpid, u8 current_version);
static void cleanup_inactive_reliability_data(void);
static void update_system_health_metrics(void);
static void log_orchestrator_state_change(orchestrator_state_t old_state, orchestrator_state_t new_state);
static void synchronize_state_across_versions(void);
static bool validate_orchestrator_integrity(void);
