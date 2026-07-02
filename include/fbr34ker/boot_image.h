#pragma once
// SPDX-License-Identifier: BSD-2-Clause
#include <stddef.h>
#include "fbr34ker/types.h"

#define FBR34KER_BOOT_IMAGE_MAGIC 0x49524246U /* "FBRI" little-endian */
#define FBR34KER_BOOT_IMAGE_FORMAT_VERSION 1U
#define FBR34KER_BOOT_IMAGE_HEADER_SIZE 128U
#define FBR34KER_BOOT_IMAGE_MANIFEST_CAPACITY (16U * 1024U)
#define FBR34KER_BOOT_IMAGE_ALIGNMENT 4096U
#define FBR34KER_BOOT_IMAGE_MAX_COMPONENTS 8U

typedef enum {
    FBR34KER_BOOT_FAMILY_GENERIC = 0,
    FBR34KER_BOOT_FAMILY_A12 = 1,
    FBR34KER_BOOT_FAMILY_A12X = 2,
    FBR34KER_BOOT_FAMILY_A13 = 3,
    FBR34KER_BOOT_FAMILY_A14 = 4,
    FBR34KER_BOOT_FAMILY_M1 = 5,
    FBR34KER_BOOT_FAMILY_A15 = 6,
    FBR34KER_BOOT_FAMILY_M2 = 7,
} fbr34ker_boot_family_t;

typedef struct PACKED {
    u32 magic;
    u16 format_version;
    u16 header_size;
    u32 flags;
    u32 family;
    u32 component_count;
    u32 manifest_capacity;
    u64 total_size;
    u64 manifest_offset;
    u64 manifest_size;
    u64 payload_offset;
    u64 payload_size;
    u8 manifest_sha256[32];
    u8 payload_sha256[32];
} fbr34ker_boot_image_header_t;

STATIC_ASSERT(sizeof(fbr34ker_boot_image_header_t) == FBR34KER_BOOT_IMAGE_HEADER_SIZE,
              "FBRI header ABI size changed");
STATIC_ASSERT(offsetof(fbr34ker_boot_image_header_t, manifest_sha256) == 64U,
              "FBRI manifest hash offset changed");
STATIC_ASSERT(offsetof(fbr34ker_boot_image_header_t, payload_sha256) == 96U,
              "FBRI payload hash offset changed");
