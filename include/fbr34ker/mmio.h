#pragma once
// SPDX-License-Identifier: BSD-2-Clause
#include "fbr34ker/types.h"

#define FBR34KER_MMIO_MAX_WINDOWS 32U
#define FBR34KER_MMIO_NAME_CAPACITY 48U

#define FBR34KER_MMIO_READ        (1U << 0)
#define FBR34KER_MMIO_WRITE       (1U << 1)
#define FBR34KER_MMIO_PROBE_SAFE  (1U << 2)

typedef struct {
    char name[FBR34KER_MMIO_NAME_CAPACITY];
    u64 base;
    u64 size;
    u32 permissions;
    u32 access_width_mask;
} fbr34ker_mmio_window_t;

typedef bool (*fbr34ker_mmio_backend_read_t)(u64 address, u32 width,
                                               u64 *value, void *context);
typedef bool (*fbr34ker_mmio_backend_write_t)(u64 address, u32 width,
                                                u64 value, void *context);

typedef struct {
    u64 reads;
    u64 writes;
    u64 rejected;
    u64 backend_failures;
    u64 contained_faults;
    u32 window_count;
    bool immutable;
    bool initialized;
} fbr34ker_mmio_stats_t;

void mmio_init(bool immutable);
void mmio_shutdown(void);
bool mmio_ready(void);
bool mmio_healthy(void);
bool mmio_register_window(const char *name, u64 base, u64 size,
                          u32 permissions, u32 access_width_mask);
u32 mmio_window_count(void);
bool mmio_window_at(u32 index, fbr34ker_mmio_window_t *window);
bool mmio_address_allowed(u64 address, u32 width, bool write,
                          bool require_probe_safe);
void mmio_set_backend(fbr34ker_mmio_backend_read_t read_backend,
                      fbr34ker_mmio_backend_write_t write_backend,
                      void *context);
bool mmio_read8(u64 address, u8 *value);
bool mmio_read16(u64 address, u16 *value);
bool mmio_read32(u64 address, u32 *value);
bool mmio_probe_read32(u64 address, u32 *value);
bool mmio_handle_fault(u64 esr, u64 far, u64 *return_address);
bool mmio_read64(u64 address, u64 *value);
bool mmio_write8(u64 address, u8 value);
bool mmio_write16(u64 address, u16 value);
bool mmio_write32(u64 address, u32 value);
bool mmio_write64(u64 address, u64 value);
bool mmio_update32(u64 address, u32 clear_mask, u32 set_mask, u32 *result);
fbr34ker_mmio_stats_t mmio_stats(void);
