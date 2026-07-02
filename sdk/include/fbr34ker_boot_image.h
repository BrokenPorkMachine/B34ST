#pragma once
// SPDX-License-Identifier: BSD-2-Clause
#include <stddef.h>
#include <stdint.h>

#define FBR34KER_BOOT_IMAGE_MAGIC 0x49524246U
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

typedef struct __attribute__((packed)) {
    uint32_t magic;
    uint16_t format_version;
    uint16_t header_size;
    uint32_t flags;
    uint32_t family;
    uint32_t component_count;
    uint32_t manifest_capacity;
    uint64_t total_size;
    uint64_t manifest_offset;
    uint64_t manifest_size;
    uint64_t payload_offset;
    uint64_t payload_size;
    uint8_t manifest_sha256[32];
    uint8_t payload_sha256[32];
} fbr34ker_boot_image_header_t;

_Static_assert(sizeof(fbr34ker_boot_image_header_t) == FBR34KER_BOOT_IMAGE_HEADER_SIZE,
               "FBRI header ABI size changed");
_Static_assert(offsetof(fbr34ker_boot_image_header_t, manifest_sha256) == 64U,
               "FBRI manifest hash offset changed");
_Static_assert(offsetof(fbr34ker_boot_image_header_t, payload_sha256) == 96U,
               "FBRI payload hash offset changed");
