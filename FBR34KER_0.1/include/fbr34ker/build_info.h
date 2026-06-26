#pragma once
#include "fbr34ker/types.h"

#define FBR34KER_BUILD_INFO_MAGIC 0x32494246U /* "FBI2" little-endian */
#define FBR34KER_BUILD_INFO_VERSION 1U

#ifndef FBR34KER_BUILD_TARGET
#define FBR34KER_BUILD_TARGET "unknown"
#endif

#ifndef FBR34KER_SOURCE_ID
#define FBR34KER_SOURCE_ID "release-source"
#endif

typedef struct PACKED {
    u32 magic;
    u16 format_version;
    u16 structure_size;
    char monitor_name[16];
    char monitor_version[24];
    char build_channel[24];
    char build_target[24];
    char source_id[32];
    u32 protocol_version;
    u32 handoff_version;
    u32 module_abi;
    u32 module_format_version;
    u32 bytecode_version;
} fbr34ker_build_info_t;

const fbr34ker_build_info_t *fbr34ker_build_info(void);
