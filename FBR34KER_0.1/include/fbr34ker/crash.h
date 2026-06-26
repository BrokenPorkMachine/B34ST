#pragma once
#include "fbr34ker/exception.h"
#include "fbr34ker/types.h"

#define FBR34KER_CRASH_BACKTRACE_DEPTH 16U

typedef struct {
    u32 magic;
    u16 version;
    u16 size;
    u32 checksum;
    u32 capture_count;
    u64 timestamp_ms;
    exception_frame_t frame;
    u32 backtrace_count;
    u32 reserved;
    u64 backtrace[FBR34KER_CRASH_BACKTRACE_DEPTH];
} fbr34ker_crash_record_t;

void crash_init(void);
bool crash_available(void);
void crash_capture(const exception_frame_t *frame);
void crash_print(void);
void crash_clear(void);
usize crash_export_text(char *buffer, usize capacity);
usize crash_export_json(char *buffer, usize capacity);
const fbr34ker_crash_record_t *crash_record(void);
