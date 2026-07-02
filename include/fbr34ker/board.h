#pragma once
// SPDX-License-Identifier: BSD-2-Clause
#include "fbr34ker/types.h"

#define FBR34KER_BOARD_MAX_DEVICES 16U
#define FBR34KER_BOARD_NAME_CAPACITY 48U
#define FBR34KER_BOARD_COMPAT_CAPACITY 64U

typedef enum {
    FBR34KER_BOARD_SOURCE_FALLBACK = 0,
    FBR34KER_BOARD_SOURCE_BUILTIN,
    FBR34KER_BOARD_SOURCE_DEVICE_TREE,
    FBR34KER_BOARD_SOURCE_HANDOFF,
} fbr34ker_board_source_t;

typedef enum {
    FBR34KER_DEVICE_UART = 0,
    FBR34KER_DEVICE_TIMER,
    FBR34KER_DEVICE_INTERRUPT_CONTROLLER,
    FBR34KER_DEVICE_WATCHDOG,
    FBR34KER_DEVICE_POWER,
    FBR34KER_DEVICE_FRAMEBUFFER,
    FBR34KER_DEVICE_USB,
    FBR34KER_DEVICE_I2C,
    FBR34KER_DEVICE_COUNT
} fbr34ker_device_type_t;

#define FBR34KER_DEVICE_FLAG_MMIO_READ       (1U << 0)
#define FBR34KER_DEVICE_FLAG_MMIO_WRITE      (1U << 1)
#define FBR34KER_DEVICE_FLAG_PROBE_SAFE      (1U << 2)
#define FBR34KER_DEVICE_FLAG_ARCHITECTURAL   (1U << 3)
#define FBR34KER_DEVICE_FLAG_FROM_DTB        (1U << 4)
#define FBR34KER_DEVICE_FLAG_REQUIRED        (1U << 5)

typedef struct {
    char name[FBR34KER_BOARD_NAME_CAPACITY];
    char compatible[FBR34KER_BOARD_COMPAT_CAPACITY];
    fbr34ker_device_type_t type;
    u32 flags;
    u64 base;
    u64 size;
    u64 clock_hz;
    u32 interrupt;
    u32 reserved;
} fbr34ker_board_device_t;

typedef struct {
    char identifier[FBR34KER_BOARD_NAME_CAPACITY];
    char name[FBR34KER_BOARD_NAME_CAPACITY];
    char compatible[FBR34KER_BOARD_COMPAT_CAPACITY];
    fbr34ker_board_source_t source;
    u64 features;
    u64 memory_base;
    u64 memory_size;
    u32 device_count;
    bool matched;
    bool device_tree_applied;
    fbr34ker_board_device_t devices[FBR34KER_BOARD_MAX_DEVICES];
} fbr34ker_board_descriptor_t;

bool board_init(void);
void board_shutdown(void);
bool board_ready(void);
bool board_healthy(void);
const fbr34ker_board_descriptor_t *board_active(void);
u32 board_device_count(void);
bool board_device_at(u32 index, fbr34ker_board_device_t *device);
const fbr34ker_board_device_t *board_find_device(fbr34ker_device_type_t type,
                                                  u32 occurrence);
const char *board_source_name(fbr34ker_board_source_t source);
const char *board_device_type_name(fbr34ker_device_type_t type);
usize board_export_json(char *buffer, usize capacity);
bool board_add_device(const char *name, const char *compatible,
                       fbr34ker_device_type_t type, u32 flags,
                       u64 base, u64 size, u64 clock_hz, u32 interrupt);
