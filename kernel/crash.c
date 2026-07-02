#include "fbr34ker/crash.h"
#include "fbr34ker/boot_evidence.h"
#include "fbr34ker/crc32.h"
#include "fbr34ker/format.h"
#include "fbr34ker/string.h"
#include "fbr34ker/timer.h"
#include <stdarg.h>

#define CRASH_MAGIC 0x43525348U
#define CRASH_VERSION 1U

// SPDX-License-Identifier: BSD-2-Clause
extern u8 __stack_bottom[];
extern u8 __stack_top[];

static fbr34ker_crash_record_t persistent_record
    __attribute__((section(".crashlog"), aligned(16)));

static u32 record_checksum(const fbr34ker_crash_record_t *record)
{
    fbr34ker_crash_record_t copy = *record;
    copy.checksum = 0U;
    return crc32_compute(&copy, sizeof(copy));
}

static bool record_valid(void)
{
    return persistent_record.magic == CRASH_MAGIC &&
           persistent_record.version == CRASH_VERSION &&
           persistent_record.size == sizeof(persistent_record) &&
           persistent_record.checksum == record_checksum(&persistent_record) &&
           persistent_record.backtrace_count <= FBR34KER_CRASH_BACKTRACE_DEPTH;
}

void crash_init(void)
{
    if (!record_valid()) {
        fm_memset(&persistent_record, 0, sizeof(persistent_record));
    }
}

bool crash_available(void)
{
    return record_valid();
}

static bool stack_address_valid(u64 address, usize bytes)
{
    const u64 bottom = (u64)(usize)__stack_bottom;
    const u64 top = (u64)(usize)__stack_top;
    return (address & 7U) == 0U && address >= bottom &&
           address <= top && bytes <= top - address;
}

void crash_capture(const exception_frame_t *frame)
{
    if (frame == NULL) {
        boot_evidence_error(0x43525348U, 0U);
        return;
    }
    boot_evidence_error(0x43525348U, frame->esr);
    u32 previous_count = record_valid() ? persistent_record.capture_count : 0U;
    fm_memset(&persistent_record, 0, sizeof(persistent_record));
    persistent_record.magic = CRASH_MAGIC;
    persistent_record.version = CRASH_VERSION;
    persistent_record.size = sizeof(persistent_record);
    persistent_record.capture_count = previous_count + 1U;
    persistent_record.timestamp_ms = timer_uptime_ms();
    persistent_record.frame = *frame;

    u64 frame_pointer = frame->x[29];
    while (persistent_record.backtrace_count < FBR34KER_CRASH_BACKTRACE_DEPTH &&
           stack_address_valid(frame_pointer, 16U)) {
        const u64 *record = (const u64 *)(usize)frame_pointer;
        const u64 next_frame = record[0];
        const u64 return_address = record[1];
        if (return_address == 0U) {
            break;
        }
        persistent_record.backtrace[persistent_record.backtrace_count++] =
            return_address;
        if (next_frame <= frame_pointer) {
            break;
        }
        frame_pointer = next_frame;
    }
    persistent_record.checksum = record_checksum(&persistent_record);
}

static const char *exception_class_name(u64 esr)
{
    switch ((esr >> 26U) & 0x3fU) {
    case 0x00: return "unknown";
    case 0x15: return "SVC AArch64";
    case 0x16: return "HVC AArch64";
    case 0x18: return "trapped system instruction";
    case 0x20: return "instruction abort from lower EL";
    case 0x21: return "instruction abort from same EL";
    case 0x24: return "data abort from lower EL";
    case 0x25: return "data abort from same EL";
    case 0x2c: return "floating-point exception";
    case 0x3c: return "BRK instruction";
    default: return "unclassified";
    }
}

static const char *fault_status_name(u64 esr)
{
    switch (esr & 0x3fU) {
    case 0x04: return "translation fault level 0";
    case 0x05: return "translation fault level 1";
    case 0x06: return "translation fault level 2";
    case 0x07: return "translation fault level 3";
    case 0x09: return "access flag fault level 1";
    case 0x0a: return "access flag fault level 2";
    case 0x0b: return "access flag fault level 3";
    case 0x0d: return "permission fault level 1";
    case 0x0e: return "permission fault level 2";
    case 0x0f: return "permission fault level 3";
    case 0x10: return "synchronous external abort";
    case 0x21: return "alignment fault";
    default: return "other/unknown fault status";
    }
}

static usize append(char *buffer, usize capacity, usize offset,
                    const char *format, ...)
{
    if (buffer == NULL || capacity == 0U || offset >= capacity) {
        return offset;
    }
    va_list arguments;
    va_start(arguments, format);
    const int count = fm_vsnprintf(buffer + offset, capacity - offset,
                                   format, arguments);
    va_end(arguments);
    if (count <= 0) {
        return offset;
    }
    const usize amount = (usize)count;
    return amount >= capacity - offset ? capacity - 1U : offset + amount;
}

usize crash_export_text(char *buffer, usize capacity)
{
    if (buffer == NULL || capacity == 0U) {
        return 0U;
    }
    buffer[0] = '\0';
    if (!record_valid()) {
        return append(buffer, capacity, 0U, "No crash report.\n");
    }
    const fbr34ker_crash_record_t *record = &persistent_record;
    const exception_frame_t *frame = &record->frame;
    usize offset = 0U;
    offset = append(buffer, capacity, offset,
                    "FBR34KER crash report v%u\n"
                    "capture=%u uptime_ms=%llu vector=%llu EL=%llu\n"
                    "ESR=0x%016llx EC=%s ISS=0x%08llx\n"
                    "FAR=0x%016llx ELR=0x%016llx SPSR=0x%016llx SP=0x%016llx\n",
                    record->version, record->capture_count,
                    record->timestamp_ms, frame->vector,
                    (frame->current_el >> 2U) & 3U, frame->esr,
                    exception_class_name(frame->esr), frame->esr & 0x1ffffffU,
                    frame->far, frame->elr, frame->spsr,
                    frame->stack_pointer);
    const u64 exception_class = (frame->esr >> 26U) & 0x3fU;
    if (exception_class == 0x20U || exception_class == 0x21U ||
        exception_class == 0x24U || exception_class == 0x25U) {
        offset = append(buffer, capacity, offset, "fault=%s write=%s\n",
                        fault_status_name(frame->esr),
                        (frame->esr & (1ULL << 6U)) != 0U ? "yes" : "no");
    }
    for (u32 index = 0U; index < 31U; ++index) {
        offset = append(buffer, capacity, offset, "x%02u=0x%016llx%s",
                        index, frame->x[index],
                        (index & 1U) != 0U ? "\n" : "  ");
    }
    offset = append(buffer, capacity, offset, "\nbacktrace (%u):\n",
                    record->backtrace_count);
    for (u32 index = 0U; index < record->backtrace_count; ++index) {
        offset = append(buffer, capacity, offset, "  #%u 0x%016llx\n",
                        index, record->backtrace[index]);
    }
    return offset;
}

usize crash_export_json(char *buffer, usize capacity)
{
    if (buffer == NULL || capacity == 0U) {
        return 0U;
    }
    if (!record_valid()) {
        return append(buffer, capacity, 0U,
                      "{\"schema\":1,\"available\":false}\n");
    }
    const fbr34ker_crash_record_t *record = &persistent_record;
    const exception_frame_t *frame = &record->frame;
    usize offset = append(buffer, capacity, 0U,
        "{\"schema\":1,\"available\":true,\"capture\":%u,"
        "\"uptime_ms\":%llu,\"vector\":%llu,\"current_el\":%llu,"
        "\"esr\":%llu,\"far\":%llu,\"elr\":%llu,"
        "\"spsr\":%llu,\"sp\":%llu,\"registers\":[",
        record->capture_count, record->timestamp_ms, frame->vector,
        (frame->current_el >> 2U) & 3U, frame->esr, frame->far, frame->elr,
        frame->spsr, frame->stack_pointer);
    for (u32 index = 0U; index < 31U; ++index) {
        offset = append(buffer, capacity, offset, "%s%llu",
                        index == 0U ? "" : ",", frame->x[index]);
    }
    offset = append(buffer, capacity, offset, "],\"backtrace\":[");
    for (u32 index = 0U; index < record->backtrace_count; ++index) {
        offset = append(buffer, capacity, offset, "%s%llu",
                        index == 0U ? "" : ",", record->backtrace[index]);
    }
    return append(buffer, capacity, offset, "]}\n");
}

void crash_print(void)
{
    char text[8192];
    (void)crash_export_text(text, sizeof(text));
    fm_printf("%s", text);
}

void crash_clear(void)
{
    fm_memset(&persistent_record, 0, sizeof(persistent_record));
}

const fbr34ker_crash_record_t *crash_record(void)
{
    return record_valid() ? &persistent_record : NULL;
}
