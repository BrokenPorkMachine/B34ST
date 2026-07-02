#pragma once
// SPDX-License-Identifier: BSD-2-Clause
#include "fbr34ker/types.h"

/*
 * Transport-neutral deployment receiver contract.  The monitor itself does
 * not implement this mutation protocol; authorized loader ports may implement
 * it while enforcing their board deployment profile before accepting data.
 */
#define FBR34KER_DEPLOY_MAGIC 0x50444246U /* "FBDP" little-endian */
#define FBR34KER_DEPLOY_VERSION 1U
#define FBR34KER_DEPLOY_HEADER_SIZE 20U
#define FBR34KER_DEPLOY_MAX_PAYLOAD (64U * 1024U)
#define FBR34KER_DEPLOY_MAX_CHUNK 4096U

#define FBR34KER_DEPLOY_FLAG_ACK   (1U << 0)
#define FBR34KER_DEPLOY_FLAG_ERROR (1U << 1)
#define FBR34KER_DEPLOY_FLAG_EVENT (1U << 2)

typedef enum {
    FBR34KER_DEPLOY_PING = 0x01,
    FBR34KER_DEPLOY_HELLO = 0x02,
    FBR34KER_DEPLOY_CAPABILITIES = 0x03,
    FBR34KER_DEPLOY_BEGIN = 0x10,
    FBR34KER_DEPLOY_QUERY_PROGRESS = 0x11,
    FBR34KER_DEPLOY_PUT_CHUNK = 0x12,
    FBR34KER_DEPLOY_COMMIT_ARTIFACT = 0x13,
    FBR34KER_DEPLOY_START = 0x14,
    FBR34KER_DEPLOY_EVIDENCE_GET = 0x20,
    FBR34KER_DEPLOY_RESET_SESSION = 0x21,
    FBR34KER_DEPLOY_RECOVER_SESSION = 0x22,
} fbr34ker_deploy_message_t;

typedef struct PACKED {
    u32 magic;
    u8 version;
    u8 message_type;
    u16 flags;
    u32 sequence;
    u32 payload_size;
    u32 crc32;
} fbr34ker_deploy_header_t;

STATIC_ASSERT(sizeof(fbr34ker_deploy_header_t) == FBR34KER_DEPLOY_HEADER_SIZE,
              "deployment frame header size changed");
