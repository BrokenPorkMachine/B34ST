#pragma once
#include "fbr34ker/types.h"

#define FBR34KER_BRINGUP_MAX_RECORDS 32U
#define FBR34KER_BRINGUP_NAME_CAPACITY 48U
#define FBR34KER_BRINGUP_DETAIL_CAPACITY 80U

typedef enum {
    FBR34KER_BRINGUP_NOT_RUN = 0,
    FBR34KER_BRINGUP_PASS,
    FBR34KER_BRINGUP_FAIL,
    FBR34KER_BRINGUP_SKIPPED,
    FBR34KER_BRINGUP_BLOCKED,
} fbr34ker_bringup_status_t;

typedef struct {
    u32 sequence;
    fbr34ker_bringup_status_t status;
    char name[FBR34KER_BRINGUP_NAME_CAPACITY];
    char detail[FBR34KER_BRINGUP_DETAIL_CAPACITY];
    u64 value0;
    u64 value1;
} fbr34ker_bringup_record_t;

typedef struct {
    u32 records;
    u32 passed;
    u32 failed;
    u32 skipped;
    u32 blocked;
    bool active_probe;
    bool complete;
} fbr34ker_bringup_summary_t;

void bringup_report_init(void);
bool bringup_report_run(bool active_probe);
u32 bringup_report_count(void);
bool bringup_report_at(u32 index, fbr34ker_bringup_record_t *record);
fbr34ker_bringup_summary_t bringup_report_summary(void);
const char *bringup_status_name(fbr34ker_bringup_status_t status);
usize bringup_report_export_json(char *buffer, usize capacity);
