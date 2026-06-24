#pragma once
#include "fbr34ker/types.h"

#define FBR34KER_BOOT_EVIDENCE_MAGIC 0x46424556U
#define FBR34KER_BOOT_EVIDENCE_VERSION 1U

typedef enum {
    FBR34KER_BOOT_STAGE_RESET = 0,
    FBR34KER_BOOT_STAGE_CONTEXT,
    FBR34KER_BOOT_STAGE_PLATFORM,
    FBR34KER_BOOT_STAGE_RUNTIME,
    FBR34KER_BOOT_STAGE_ARCHITECTURE,
    FBR34KER_BOOT_STAGE_INTERACTIVE,
    FBR34KER_BOOT_STAGE_SHUTDOWN,
    FBR34KER_BOOT_STAGE_FAULT,
} fbr34ker_boot_stage_t;

typedef struct {
    u32 magic;
    u16 version;
    u16 size;
    u32 checksum;
    u32 boot_count;
    u32 previous_stage;
    u32 current_stage;
    u32 previous_clean;
    u32 clean_shutdown;
    u32 last_error;
    u64 last_value;
    u64 stage_sequence;
} fbr34ker_boot_evidence_t;

void boot_evidence_init(void);
void boot_evidence_stage(fbr34ker_boot_stage_t stage);
void boot_evidence_error(u32 error, u64 value);
void boot_evidence_clean_shutdown(void);
const fbr34ker_boot_evidence_t *boot_evidence_record(void);
const char *boot_stage_name(fbr34ker_boot_stage_t stage);
usize boot_evidence_export_json(char *buffer, usize capacity);
