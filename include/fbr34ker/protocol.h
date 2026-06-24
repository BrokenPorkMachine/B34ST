#pragma once
#include "fbr34ker/types.h"

#define FBR34KER_PROTOCOL_MAGIC 0x334d461eU /* bytes: 1e 'F' 'M' '3' */
#define FBR34KER_PROTOCOL_VERSION 1U
#define FBR34KER_PROTOCOL_HEADER_SIZE 20U
#define FBR34KER_PROTOCOL_MAX_PAYLOAD (64U * 1024U)
#define FBR34KER_PROTOCOL_MAX_RESPONSE (16U * 1024U)

#define FBR34KER_PROTOCOL_FLAG_ACK   (1U << 0)
#define FBR34KER_PROTOCOL_FLAG_ERROR (1U << 1)
#define FBR34KER_PROTOCOL_FLAG_EVENT (1U << 2)

typedef enum {
    FBR34KER_PROTOCOL_PING = 0x01,
    FBR34KER_PROTOCOL_HELLO = 0x02,
    FBR34KER_PROTOCOL_COMMAND = 0x03,
    FBR34KER_PROTOCOL_MODULE_PUT = 0x04,
    FBR34KER_PROTOCOL_MODULE_RUN = 0x05,
    FBR34KER_PROTOCOL_MODULE_UNLOAD = 0x06,
    FBR34KER_PROTOCOL_LOG_GET = 0x07,
    FBR34KER_PROTOCOL_CRASH_GET = 0x08,
    FBR34KER_PROTOCOL_EVENT_GET = 0x09,
    FBR34KER_PROTOCOL_REBOOT = 0x0a,
    FBR34KER_PROTOCOL_HALT = 0x0b,
} fbr34ker_protocol_type_t;

void protocol_init(void);
bool protocol_handle_start_byte(u8 first_byte);
void protocol_emit_event(const char *source, const char *message);
NORETURN void protocol_crash_loop(void);
