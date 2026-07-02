#include "fbr34ker/bringup_report.h"
#include "fbr34ker/board.h"
#include "fbr34ker/device_tree.h"
#include "fbr34ker/format.h"
#include "fbr34ker/hardware_probe.h"
#include "fbr34ker/mmio.h"
#include "fbr34ker/physical_memory.h"
#include "fbr34ker/platform.h"
#include "fbr34ker/string.h"
#include "fbr34ker/timer.h"
#include <stdarg.h>

// SPDX-License-Identifier: BSD-2-Clause
static fbr34ker_bringup_record_t records[FBR34KER_BRINGUP_MAX_RECORDS];
static fbr34ker_bringup_summary_t summary;

static void copy_text(char *destination, usize capacity, const char *source)
{
    usize index = 0U;
    if (destination == NULL || capacity == 0U) return;
    if (source != NULL) {
        while (index + 1U < capacity && source[index] != '\0') {
            destination[index] = source[index];
            ++index;
        }
    }
    destination[index] = '\0';
}

static void add_record(const char *name, fbr34ker_bringup_status_t status,
                       const char *detail, u64 value0, u64 value1)
{
    if (summary.records >= FBR34KER_BRINGUP_MAX_RECORDS) return;
    fbr34ker_bringup_record_t *record = &records[summary.records];
    fm_memset(record, 0, sizeof(*record));
    record->sequence = summary.records + 1U;
    record->status = status;
    copy_text(record->name, sizeof(record->name), name);
    copy_text(record->detail, sizeof(record->detail), detail);
    record->value0 = value0;
    record->value1 = value1;
    ++summary.records;
    switch (status) {
    case FBR34KER_BRINGUP_PASS: ++summary.passed; break;
    case FBR34KER_BRINGUP_FAIL: ++summary.failed; break;
    case FBR34KER_BRINGUP_SKIPPED: ++summary.skipped; break;
    case FBR34KER_BRINGUP_BLOCKED: ++summary.blocked; break;
    case FBR34KER_BRINGUP_NOT_RUN: break;
    default: break;
    }
}

void bringup_report_init(void)
{
    fm_memset(records, 0, sizeof(records));
    fm_memset(&summary, 0, sizeof(summary));
}

bool bringup_report_run(bool active_probe)
{
    bringup_report_init();
    summary.active_probe = active_probe;
    const fbr34ker_board_descriptor_t *board = board_active();
    add_record("board-description", board != NULL && board_healthy()
                   ? FBR34KER_BRINGUP_PASS : FBR34KER_BRINGUP_FAIL,
               board != NULL ? board_source_name(board->source) : "not available",
               board != NULL ? board->device_count : 0U,
               board != NULL ? board->features : 0U);

    const fbr34ker_pmm_stats_t pmm = physical_memory_stats();
    add_record("physical-memory", physical_memory_healthy()
                   ? FBR34KER_BRINGUP_PASS : FBR34KER_BRINGUP_FAIL,
               "page ownership and overlap validation",
               pmm.free_bytes, pmm.reserved_bytes);

    const fbr34ker_mmio_stats_t mmio = mmio_stats();
    add_record("mmio-windows", mmio_healthy()
                   ? FBR34KER_BRINGUP_PASS : FBR34KER_BRINGUP_FAIL,
               mmio.immutable ? "immutable write lock" : "guarded read/write",
               mmio.window_count, mmio.rejected);

    add_record("device-tree", device_tree_valid()
                   ? FBR34KER_BRINGUP_PASS : FBR34KER_BRINGUP_SKIPPED,
               device_tree_valid() ? "validated flattened tree" : "not supplied",
               device_tree_size(), device_tree_reservation_count());

    const u64 features = platform_features();
    add_record("console", (features & PLATFORM_FEATURE_CONSOLE_OUTPUT) != 0U
                   ? FBR34KER_BRINGUP_PASS : FBR34KER_BRINGUP_FAIL,
               platform_console_transport_name(), features, 0U);
    add_record("timer", timer_frequency() != 0U
                   ? FBR34KER_BRINGUP_PASS : FBR34KER_BRINGUP_FAIL,
               "architectural monotonic timer", timer_frequency(), 0U);
    add_record("interrupt-controller",
               (features & PLATFORM_FEATURE_INTERRUPTS) != 0U
                   ? FBR34KER_BRINGUP_PASS : FBR34KER_BRINGUP_SKIPPED,
               platform_interrupt_controller_name(), features, 0U);
    add_record("framebuffer",
               (features & PLATFORM_FEATURE_FRAMEBUFFER) != 0U
                   ? FBR34KER_BRINGUP_PASS : FBR34KER_BRINGUP_SKIPPED,
               "metadata only; no pixels written", features, 0U);
    add_record("watchdog",
               (features & PLATFORM_FEATURE_WATCHDOG_CONFIGURE) != 0U
                   ? FBR34KER_BRINGUP_PASS : FBR34KER_BRINGUP_SKIPPED,
               "capability discovery only", features, 0U);
    add_record("power-control", (features & PLATFORM_FEATURE_POWER) != 0U
                   ? FBR34KER_BRINGUP_PASS : FBR34KER_BRINGUP_SKIPPED,
               "capability discovery only; no action invoked", features, 0U);

    if (active_probe) {
        if (hardware_probe_immutable()) {
            add_record("active-mmio-probe", FBR34KER_BRINGUP_BLOCKED,
                       "immutable probe policy", 0U, 0U);
        } else {
            u32 attempted = 0U;
            u32 passed = 0U;
            for (u32 index = 0U; index < mmio_window_count(); ++index) {
                fbr34ker_mmio_window_t window;
                if (!mmio_window_at(index, &window) ||
                    (window.permissions & FBR34KER_MMIO_PROBE_SAFE) == 0U ||
                    (window.permissions & FBR34KER_MMIO_READ) == 0U ||
                    window.size < 4U) continue;
                ++attempted;
                u32 value;
                if (mmio_probe_read32(window.base, &value)) ++passed;
            }
            add_record("active-mmio-probe",
                       attempted != 0U && passed == attempted
                           ? FBR34KER_BRINGUP_PASS
                           : (attempted == 0U ? FBR34KER_BRINGUP_SKIPPED
                                             : FBR34KER_BRINGUP_FAIL),
                       "read-only allow-listed windows", passed, attempted);
        }
    } else {
        add_record("active-mmio-probe", FBR34KER_BRINGUP_SKIPPED,
                   "metadata mode", 0U, 0U);
    }
    summary.complete = true;
    return summary.failed == 0U;
}

u32 bringup_report_count(void) { return summary.records; }

bool bringup_report_at(u32 index, fbr34ker_bringup_record_t *record)
{
    if (record == NULL || index >= summary.records) return false;
    *record = records[index];
    return true;
}

fbr34ker_bringup_summary_t bringup_report_summary(void) { return summary; }

const char *bringup_status_name(fbr34ker_bringup_status_t status)
{
    switch (status) {
    case FBR34KER_BRINGUP_NOT_RUN: return "not-run";
    case FBR34KER_BRINGUP_PASS: return "pass";
    case FBR34KER_BRINGUP_FAIL: return "fail";
    case FBR34KER_BRINGUP_SKIPPED: return "skipped";
    case FBR34KER_BRINGUP_BLOCKED: return "blocked";
    default: return "unknown";
    }
}

static usize append(char *buffer, usize capacity, usize offset,
                    const char *format, ...)
{
    if (buffer == NULL || capacity == 0U || offset >= capacity) return offset;
    va_list arguments;
    va_start(arguments, format);
    const int count = fm_vsnprintf(buffer + offset, capacity - offset,
                                   format, arguments);
    va_end(arguments);
    if (count <= 0) return offset;
    return (usize)count >= capacity - offset ? capacity - 1U
                                             : offset + (usize)count;
}

usize bringup_report_export_json(char *buffer, usize capacity)
{
    if (buffer == NULL || capacity == 0U) return 0U;
    usize offset = append(buffer, capacity, 0U,
        "{\"schema\":1,\"complete\":%s,\"active_probe\":%s,"
        "\"passed\":%u,\"failed\":%u,\"skipped\":%u,\"blocked\":%u,"
        "\"records\":[",
        summary.complete ? "true" : "false",
        summary.active_probe ? "true" : "false",
        summary.passed, summary.failed, summary.skipped, summary.blocked);
    for (u32 index = 0U; index < summary.records; ++index) {
        const fbr34ker_bringup_record_t *record = &records[index];
        offset = append(buffer, capacity, offset,
            "%s{\"sequence\":%u,\"name\":\"%s\",\"status\":\"%s\","
            "\"detail\":\"%s\",\"value0\":%llu,\"value1\":%llu}",
            index == 0U ? "" : ",", record->sequence, record->name,
            bringup_status_name(record->status), record->detail,
            record->value0, record->value1);
    }
    return append(buffer, capacity, offset, "]}\n");
}
