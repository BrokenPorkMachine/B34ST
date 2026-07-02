#include "fbr34ker/protocol.h"
#include "fbr34ker/command.h"
#include "fbr34ker/build_info.h"
#include "fbr34ker/console.h"
#include "fbr34ker/crash.h"
#include "fbr34ker/crc32.h"
#include "fbr34ker/format.h"
#include "fbr34ker/hardware_probe.h"
#include "fbr34ker/log.h"
#include "fbr34ker/module.h"
#include "fbr34ker/platform.h"
#include "fbr34ker/string.h"
#include "fbr34ker/timer.h"
#include "fbr34ker/version.h"

#define PROTOCOL_IO_TIMEOUT_MS 30000ULL
#define EVENT_COUNT 16U
#define EVENT_SOURCE_SIZE 24U
#define EVENT_MESSAGE_SIZE 112U

// SPDX-License-Identifier: BSD-2-Clause
typedef struct {
    u64 timestamp_ms;
    char source[EVENT_SOURCE_SIZE];
    char message[EVENT_MESSAGE_SIZE];
} protocol_event_t;

static ALIGNED(16) u8 request_payload[FBR34KER_PROTOCOL_MAX_PAYLOAD];
static ALIGNED(16) u8 response_payload[FBR34KER_PROTOCOL_MAX_RESPONSE];
static ALIGNED(16) u8 cached_frame[FBR34KER_PROTOCOL_HEADER_SIZE +
                                   FBR34KER_PROTOCOL_MAX_RESPONSE];
static usize cached_frame_size;
static u32 cached_sequence;
static u8 cached_type;
static u32 cached_request_crc;
static bool cached_valid;
static bool in_crash_mode;
static u32 active_request_crc;
static protocol_event_t events[EVENT_COUNT];
static usize next_event;
static usize stored_events;

static u16 read_le16(const u8 *data)
{
    return (u16)data[0] | ((u16)data[1] << 8U);
}

static u32 read_le32(const u8 *data)
{
    return (u32)data[0] | ((u32)data[1] << 8U) |
           ((u32)data[2] << 16U) | ((u32)data[3] << 24U);
}

static void write_le16(u8 *data, u16 value)
{
    data[0] = (u8)value;
    data[1] = (u8)(value >> 8U);
}

static void write_le32(u8 *data, u32 value)
{
    data[0] = (u8)value;
    data[1] = (u8)(value >> 8U);
    data[2] = (u8)(value >> 16U);
    data[3] = (u8)(value >> 24U);
}

static void raw_write(const void *data, usize size)
{
    const u8 *bytes = (const u8 *)data;
    for (usize index = 0U; index < size; ++index) {
        platform_uart_putc((char)bytes[index]);
    }
}

static bool raw_read(void *destination, usize size)
{
    u8 *bytes = (u8 *)destination;
    usize received = 0U;
    u64 last_progress = timer_uptime_ms();
    while (received < size) {
        const int value = platform_uart_getc_nonblocking();
        if (value >= 0) {
            bytes[received++] = (u8)value;
            last_progress = timer_uptime_ms();
            continue;
        }
        if (timer_uptime_ms() - last_progress > PROTOCOL_IO_TIMEOUT_MS) {
            return false;
        }
        __asm__ volatile("yield");
    }
    return true;
}

static usize bounded_text(const u8 *payload, usize size, char *output,
                          usize capacity)
{
    if (payload == NULL || output == NULL || capacity == 0U ||
        size == 0U || size >= capacity) {
        return 0U;
    }
    for (usize index = 0U; index < size; ++index) {
        const u8 value = payload[index];
        if (value == 0U || value == '\r' || value == '\n' || value < 0x20U ||
            value > 0x7eU) {
            return 0U;
        }
        output[index] = (char)value;
    }
    output[size] = '\0';
    return size;
}

static usize event_export(char *buffer, usize capacity)
{
    if (buffer == NULL || capacity == 0U) {
        return 0U;
    }
    buffer[0] = '\0';
    usize offset = 0U;
    if (stored_events == 0U) {
        const int count = fm_snprintf(buffer, capacity, "No host events.\n");
        return count > 0 ? (usize)count : 0U;
    }
    const usize first = stored_events == EVENT_COUNT ? next_event : 0U;
    for (usize index = 0U; index < stored_events; ++index) {
        const protocol_event_t *event = &events[(first + index) % EVENT_COUNT];
        if (offset + 1U >= capacity) {
            break;
        }
        const int count = fm_snprintf(buffer + offset, capacity - offset,
                                      "[%llu ms] %s: %s\n",
                                      event->timestamp_ms, event->source,
                                      event->message);
        if (count <= 0) {
            break;
        }
        const usize amount = (usize)count;
        if (amount >= capacity - offset) {
            offset = capacity - 1U;
            break;
        }
        offset += amount;
    }
    return offset;
}

void protocol_emit_event(const char *source, const char *message)
{
    protocol_event_t *event = &events[next_event];
    event->timestamp_ms = timer_uptime_ms();
    fm_strlcpy(event->source, source != NULL ? source : "monitor",
               sizeof(event->source));
    fm_strlcpy(event->message, message != NULL ? message : "",
               sizeof(event->message));
    next_event = (next_event + 1U) % EVENT_COUNT;
    if (stored_events < EVENT_COUNT) {
        ++stored_events;
    }
}

void protocol_init(void)
{
    cached_frame_size = 0U;
    cached_sequence = 0U;
    cached_type = 0U;
    cached_request_crc = 0U;
    cached_valid = false;
    in_crash_mode = false;
    active_request_crc = 0U;
    next_event = 0U;
    stored_events = 0U;
    fm_memset(events, 0, sizeof(events));
}

static void send_response(u8 request_type, u32 sequence, u16 flags,
                          const void *payload, usize payload_size)
{
    if (payload_size > FBR34KER_PROTOCOL_MAX_RESPONSE) {
        payload_size = FBR34KER_PROTOCOL_MAX_RESPONSE;
        flags |= FBR34KER_PROTOCOL_FLAG_ERROR;
    }
    u8 header[FBR34KER_PROTOCOL_HEADER_SIZE];
    fm_memset(header, 0, sizeof(header));
    write_le32(header, FBR34KER_PROTOCOL_MAGIC);
    header[4] = FBR34KER_PROTOCOL_VERSION;
    header[5] = (u8)(request_type | 0x80U);
    write_le16(header + 6U, (u16)(flags | FBR34KER_PROTOCOL_FLAG_ACK));
    write_le32(header + 8U, sequence);
    write_le32(header + 12U, (u32)payload_size);
    u32 crc = crc32_begin();
    crc = crc32_update(crc, header, 16U);
    crc = crc32_update(crc, payload, payload_size);
    write_le32(header + 16U, crc32_finish(crc));

    cached_frame_size = sizeof(header) + payload_size;
    fm_memcpy(cached_frame, header, sizeof(header));
    if (payload_size != 0U) {
        fm_memcpy(cached_frame + sizeof(header), payload, payload_size);
    }
    cached_sequence = sequence;
    cached_type = request_type;
    cached_request_crc = active_request_crc;
    cached_valid = true;
    raw_write(cached_frame, cached_frame_size);
}

static void send_text(u8 type, u32 sequence, bool error, const char *text)
{
    const usize length = text != NULL ? fm_strlen(text) : 0U;
    send_response(type, sequence,
                  error ? FBR34KER_PROTOCOL_FLAG_ERROR : 0U,
                  text, length);
}

static void dispatch_request(u8 type, u32 sequence, const u8 *payload,
                             usize payload_size)
{
    char text[192];
    switch (type) {
    case FBR34KER_PROTOCOL_PING:
        send_response(type, sequence, 0U, payload, payload_size);
        return;
    case FBR34KER_PROTOCOL_HELLO: {
        const fbr34ker_build_info_t *build = fbr34ker_build_info();
        const int count = fm_snprintf((char *)response_payload,
                                      FBR34KER_PROTOCOL_MAX_RESPONSE,
                                      "%s %s\nbuild=%s\ntarget=%s\nsource=%s\n"
                                      "protocol=%u\nhandoff=%u\nmodule_abi=%u\n"
                                      "fmod=%u\nfmbc=%u\nplatform=%s\n"
                                      "max_payload=%u\ndefensive_mode=%s\n",
                                      build->monitor_name,
                                      build->monitor_version,
                                      build->build_channel,
                                      build->build_target,
                                      build->source_id,
                                      build->protocol_version,
                                      build->handoff_version,
                                      build->module_abi,
                                      build->module_format_version,
                                      build->bytecode_version,
                                      platform_name(),
                                      FBR34KER_PROTOCOL_MAX_PAYLOAD,
                                      hardware_probe_active() ? "yes" : "no");
        send_response(type, sequence, 0U, response_payload,
                      count > 0 ? (usize)count : 0U);
        return;
    }
    case FBR34KER_PROTOCOL_COMMAND: {
        if (in_crash_mode) {
            send_text(type, sequence, true,
                      "command service unavailable in crash mode\n");
            return;
        }
        if (bounded_text(payload, payload_size, text, sizeof(text)) == 0U) {
            send_text(type, sequence, true, "invalid command payload\n");
            return;
        }
        console_capture_begin((char *)response_payload,
                              FBR34KER_PROTOCOL_MAX_RESPONSE, true);
        const int result = shell_execute_line(text);
        const usize captured = console_capture_end();
        send_response(type, sequence,
                      result == 0 ? 0U : FBR34KER_PROTOCOL_FLAG_ERROR,
                      response_payload,
                      captured < FBR34KER_PROTOCOL_MAX_RESPONSE
                          ? captured : FBR34KER_PROTOCOL_MAX_RESPONSE - 1U);
        return;
    }
    case FBR34KER_PROTOCOL_MODULE_PUT: {
        if (in_crash_mode) {
            send_text(type, sequence, true,
                      "module service unavailable in crash mode\n");
            return;
        }
        const char *name = NULL;
        const fbr34ker_module_result_t result = module_load_container(
            payload, payload_size, &name);
        if (result != MODULE_OK) {
            const int count = fm_snprintf(text, sizeof(text), "ERROR %s\n",
                                          module_result_string(result));
            send_response(type, sequence, FBR34KER_PROTOCOL_FLAG_ERROR, text,
                          count > 0 ? (usize)count : 0U);
        } else {
            const int count = fm_snprintf(text, sizeof(text), "OK %s\n", name);
            send_response(type, sequence, 0U, text,
                          count > 0 ? (usize)count : 0U);
        }
        return;
    }
    case FBR34KER_PROTOCOL_MODULE_RUN:
    case FBR34KER_PROTOCOL_MODULE_UNLOAD: {
        if (in_crash_mode ||
            bounded_text(payload, payload_size, text, sizeof(text)) == 0U) {
            send_text(type, sequence, true, "invalid module request\n");
            return;
        }
        console_capture_begin((char *)response_payload,
                              FBR34KER_PROTOCOL_MAX_RESPONSE, true);
        const fbr34ker_module_result_t result = type == FBR34KER_PROTOCOL_MODULE_RUN
            ? module_run_dynamic(text) : module_unload_dynamic(text);
        const usize captured = console_capture_end();
        if (captured == 0U) {
            const int count = fm_snprintf((char *)response_payload,
                                          FBR34KER_PROTOCOL_MAX_RESPONSE,
                                          "%s\n", module_result_string(result));
            send_response(type, sequence,
                          result == MODULE_OK ? 0U : FBR34KER_PROTOCOL_FLAG_ERROR,
                          response_payload, count > 0 ? (usize)count : 0U);
        } else {
            send_response(type, sequence,
                          result == MODULE_OK ? 0U : FBR34KER_PROTOCOL_FLAG_ERROR,
                          response_payload,
                          captured < FBR34KER_PROTOCOL_MAX_RESPONSE
                              ? captured : FBR34KER_PROTOCOL_MAX_RESPONSE - 1U);
        }
        return;
    }
    case FBR34KER_PROTOCOL_LOG_GET: {
        const usize size = log_export_text((char *)response_payload,
                                           FBR34KER_PROTOCOL_MAX_RESPONSE);
        send_response(type, sequence, 0U, response_payload, size);
        return;
    }
    case FBR34KER_PROTOCOL_CRASH_GET: {
        const usize size = crash_export_text((char *)response_payload,
                                             FBR34KER_PROTOCOL_MAX_RESPONSE);
        send_response(type, sequence, 0U, response_payload, size);
        return;
    }
    case FBR34KER_PROTOCOL_EVENT_GET: {
        const usize size = event_export((char *)response_payload,
                                        FBR34KER_PROTOCOL_MAX_RESPONSE);
        send_response(type, sequence, 0U, response_payload, size);
        return;
    }
    case FBR34KER_PROTOCOL_REBOOT:
        if (!hardware_probe_power_actions_allowed()) {
            send_text(type, sequence, true, "power action locked by defensive hardware mode\n");
            return;
        }
        send_text(type, sequence, false, "rebooting\n");
        platform_reboot();
        break;
    case FBR34KER_PROTOCOL_HALT:
        if (!hardware_probe_power_actions_allowed()) {
            send_text(type, sequence, true, "power action locked by defensive hardware mode\n");
            return;
        }
        send_text(type, sequence, false, "halting\n");
        platform_halt();
        break;
    default:
        send_text(type, sequence, true, "unsupported request type\n");
        return;
    }
}

bool protocol_handle_start_byte(u8 first_byte)
{
    if (first_byte != (u8)(FBR34KER_PROTOCOL_MAGIC & 0xffU)) {
        return false;
    }
    u8 header[FBR34KER_PROTOCOL_HEADER_SIZE];
    header[0] = first_byte;
    if (!raw_read(header + 1U, sizeof(header) - 1U)) {
        return true;
    }
    if (read_le32(header) != FBR34KER_PROTOCOL_MAGIC ||
        header[4] != FBR34KER_PROTOCOL_VERSION ||
        (header[5] & 0x80U) != 0U || read_le16(header + 6U) != 0U) {
        return true;
    }
    const u8 type = header[5];
    const u32 sequence = read_le32(header + 8U);
    const usize payload_size = read_le32(header + 12U);
    const u32 expected_crc = read_le32(header + 16U);
    if (payload_size > FBR34KER_PROTOCOL_MAX_PAYLOAD ||
        !raw_read(request_payload, payload_size)) {
        send_text(type, sequence, true, "invalid payload size or timeout\n");
        cached_valid = false;
        return true;
    }
    u32 crc = crc32_begin();
    crc = crc32_update(crc, header, 16U);
    crc = crc32_update(crc, request_payload, payload_size);
    if (crc32_finish(crc) != expected_crc) {
        send_text(type, sequence, true, "CRC-32 mismatch\n");
        cached_valid = false;
        return true;
    }
    if (cached_valid && sequence == cached_sequence && type == cached_type &&
        expected_crc == cached_request_crc) {
        raw_write(cached_frame, cached_frame_size);
        return true;
    }
    active_request_crc = expected_crc;
    dispatch_request(type, sequence, request_payload, payload_size);
    return true;
}

NORETURN void protocol_crash_loop(void)
{
    in_crash_mode = true;
    cached_valid = false;
    cached_frame_size = 0U;
    for (;;) {
        const int value = platform_uart_getc_nonblocking();
        if (value < 0) {
            __asm__ volatile("yield");
            continue;
        }
        if (protocol_handle_start_byte((u8)value)) {
            continue;
        }
        if ((value == 'r' || value == 'R') &&
            hardware_probe_power_actions_allowed()) {
            platform_reboot();
        }
        if ((value == 'h' || value == 'H') &&
            hardware_probe_power_actions_allowed()) {
            platform_halt();
        }
    }
}
