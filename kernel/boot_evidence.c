// SPDX-License-Identifier: BSD-2-Clause
#include "fbr34ker/boot_evidence.h"
#include "fbr34ker/crc32.h"
#include "fbr34ker/format.h"
#include "fbr34ker/string.h"

#if defined(FBR34KER_HOST_TEST)
#define FBR34KER_BOOT_EVIDENCE_STORAGE __attribute__((aligned(16)))
#else
#define FBR34KER_BOOT_EVIDENCE_STORAGE \
    __attribute__((section(".boot_evidence"), aligned(16)))
#endif

static fbr34ker_boot_evidence_t persistent_evidence
    FBR34KER_BOOT_EVIDENCE_STORAGE;

static u32 evidence_checksum(const fbr34ker_boot_evidence_t *evidence)
{
    fbr34ker_boot_evidence_t copy = *evidence;
    copy.checksum = 0U;
    return crc32_compute(&copy, sizeof(copy));
}

static bool evidence_valid(void)
{
    return persistent_evidence.magic == FBR34KER_BOOT_EVIDENCE_MAGIC &&
           persistent_evidence.version == FBR34KER_BOOT_EVIDENCE_VERSION &&
           persistent_evidence.size == sizeof(persistent_evidence) &&
           persistent_evidence.current_stage <= FBR34KER_BOOT_STAGE_FAULT &&
           persistent_evidence.checksum == evidence_checksum(&persistent_evidence);
}

static void commit(void)
{
    persistent_evidence.checksum = 0U;
    persistent_evidence.checksum = evidence_checksum(&persistent_evidence);
}

void boot_evidence_init(void)
{
    const bool valid = evidence_valid();
    const u32 previous_boot_count = valid ? persistent_evidence.boot_count : 0U;
    const u32 previous_stage = valid ? persistent_evidence.current_stage
                                     : FBR34KER_BOOT_STAGE_RESET;
    const u32 previous_clean = valid ? persistent_evidence.clean_shutdown : 0U;
    fm_memset(&persistent_evidence, 0, sizeof(persistent_evidence));
    persistent_evidence.magic = FBR34KER_BOOT_EVIDENCE_MAGIC;
    persistent_evidence.version = FBR34KER_BOOT_EVIDENCE_VERSION;
    persistent_evidence.size = sizeof(persistent_evidence);
    persistent_evidence.boot_count = previous_boot_count + 1U;
    persistent_evidence.previous_stage = previous_stage;
    persistent_evidence.current_stage = FBR34KER_BOOT_STAGE_RESET;
    persistent_evidence.previous_clean = previous_clean;
    persistent_evidence.clean_shutdown = 0U;
    persistent_evidence.stage_sequence = 1U;
    commit();
}

void boot_evidence_stage(fbr34ker_boot_stage_t stage)
{
    if (!evidence_valid() || stage > FBR34KER_BOOT_STAGE_FAULT) return;
    persistent_evidence.current_stage = (u32)stage;
    persistent_evidence.clean_shutdown = stage == FBR34KER_BOOT_STAGE_SHUTDOWN ? 1U : 0U;
    ++persistent_evidence.stage_sequence;
    commit();
}

void boot_evidence_error(u32 error, u64 value)
{
    if (!evidence_valid()) return;
    persistent_evidence.current_stage = FBR34KER_BOOT_STAGE_FAULT;
    persistent_evidence.last_error = error;
    persistent_evidence.last_value = value;
    persistent_evidence.clean_shutdown = 0U;
    ++persistent_evidence.stage_sequence;
    commit();
}

void boot_evidence_clean_shutdown(void)
{
    boot_evidence_stage(FBR34KER_BOOT_STAGE_SHUTDOWN);
}

const fbr34ker_boot_evidence_t *boot_evidence_record(void)
{
    return evidence_valid() ? &persistent_evidence : NULL;
}

const char *boot_stage_name(fbr34ker_boot_stage_t stage)
{
    switch (stage) {
    case FBR34KER_BOOT_STAGE_RESET: return "reset";
    case FBR34KER_BOOT_STAGE_CONTEXT: return "context";
    case FBR34KER_BOOT_STAGE_PLATFORM: return "platform";
    case FBR34KER_BOOT_STAGE_RUNTIME: return "runtime";
    case FBR34KER_BOOT_STAGE_ARCHITECTURE: return "architecture";
    case FBR34KER_BOOT_STAGE_INTERACTIVE: return "interactive";
    case FBR34KER_BOOT_STAGE_SHUTDOWN: return "shutdown";
    case FBR34KER_BOOT_STAGE_FAULT: return "fault";
    default: return "unknown";
    }
}

usize boot_evidence_export_json(char *buffer, usize capacity)
{
    if (buffer == NULL || capacity == 0U) return 0U;
    const fbr34ker_boot_evidence_t *record = boot_evidence_record();
    if (record == NULL) return (usize)fm_snprintf(buffer, capacity,
        "{\"schema\":1,\"available\":false}\n");
    return (usize)fm_snprintf(buffer, capacity,
        "{\"schema\":1,\"available\":true,\"boot_count\":%u,"
        "\"previous_stage\":\"%s\",\"previous_clean\":%s,"
        "\"current_stage\":\"%s\",\"clean_shutdown\":%s,"
        "\"last_error\":%u,\"last_value\":%llu,\"sequence\":%llu}\n",
        record->boot_count,
        boot_stage_name((fbr34ker_boot_stage_t)record->previous_stage),
        record->previous_clean != 0U ? "true" : "false",
        boot_stage_name((fbr34ker_boot_stage_t)record->current_stage),
        record->clean_shutdown != 0U ? "true" : "false",
        record->last_error, record->last_value, record->stage_sequence);
}
