#pragma once
#include <stdint.h>

#ifndef FBR34KER_BRIDGE_PROTOCOL_VERSION
#define FBR34KER_BRIDGE_PROTOCOL_VERSION 1U
#endif
#define FBR34KER_BRIDGE_MAX_MESSAGE_SIZE (1024u * 1024u)
#define FBR34KER_BRIDGE_MAX_CHUNK_SIZE (128u * 1024u)
#define FBR34KER_BRIDGE_MAX_MESSAGES 4096u

/*
 * The host bridge uses one bounded UTF-8 JSON object per line. Every request
 * contains schema_version, sequence, operation, and arguments. Every response
 * echoes sequence and contains ok plus either result or error. This header
 * deliberately publishes limits and identity only; parsing remains outside the
 * freestanding monitor core.
 */
typedef struct fbr34ker_bridge_limits_v1 {
    uint32_t protocol_version;
    uint32_t max_message_size;
    uint32_t max_chunk_size;
    uint32_t max_messages;
} fbr34ker_bridge_limits_v1;

_Static_assert(sizeof(fbr34ker_bridge_limits_v1) == 16u,
               "bridge limit ABI must remain 16 bytes");
