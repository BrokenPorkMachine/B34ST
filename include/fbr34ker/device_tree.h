#pragma once
// SPDX-License-Identifier: BSD-2-Clause
#include "fbr34ker/types.h"

#define DEVICE_TREE_MAX_STRING 256U
#define DEVICE_TREE_MAX_REG_CELLS 4U

typedef struct {
    u32 total_size;
    u32 structure_size;
    u32 strings_size;
    u32 version;
    u32 node_count;
    u32 property_count;
} device_tree_summary_t;

typedef struct {
    u64 address;
    u64 size;
    u32 address_cells;
    u32 size_cells;
} device_tree_reg_t;

bool device_tree_looks_valid(const void *blob, usize available_size);
bool device_tree_init(const void *blob, usize available_size);
bool device_tree_valid(void);
const void *device_tree_blob(void);
usize device_tree_size(void);
bool device_tree_summary(device_tree_summary_t *summary);
bool device_tree_has_node(const char *path);
bool device_tree_get_property(const char *path, const char *property,
                              const void **data, usize *size);
bool device_tree_get_u32(const char *path, const char *property, u32 *value);
bool device_tree_get_u64(const char *path, const char *property, u64 *value);
bool device_tree_get_string(const char *path, const char *property,
                            char *output, usize capacity);
bool device_tree_string_list_contains(const char *path, const char *property,
                                      const char *value);
bool device_tree_resolve_alias(const char *alias, char *output, usize capacity);
bool device_tree_stdout_path(char *output, usize capacity);
bool device_tree_get_reg(const char *path, u32 index, device_tree_reg_t *reg);
bool device_tree_get_cells(const char *path, const char *property,
                           u32 *values, u32 capacity, u32 *count);
bool device_tree_get_clock_frequency(const char *path, u64 *frequency);
u32 device_tree_reservation_count(void);
bool device_tree_reservation_at(u32 index, u64 *address, u64 *size);
bool device_tree_find_compatible_path(const char *compatible,
                                      char *output, usize capacity);
int device_tree_find_compatible(const char *compatible);
int device_tree_print_node(const char *path);
int device_tree_find(const char *term);
int device_tree_print_property(const char *path, const char *property);
