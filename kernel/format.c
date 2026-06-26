#include "fbr34ker/format.h"
#include "fbr34ker/console.h"
#include "fbr34ker/string.h"

typedef void (*emit_fn)(char value, void *context);

typedef struct {
    char *buffer;
    usize capacity;
    usize position;
    usize total;
} buffer_sink_t;

static void console_emit(char value, void *context)
{
    UNUSED(context);
    console_putc(value);
}

static void buffer_emit(char value, void *context)
{
    buffer_sink_t *sink = (buffer_sink_t *)context;
    if (sink->capacity != 0U && sink->position + 1U < sink->capacity) {
        sink->buffer[sink->position] = value;
        ++sink->position;
    }
    ++sink->total;
}

static void emit_text(emit_fn emit, void *context, const char *text,
                      int *written)
{
    if (text == NULL) {
        text = "(null)";
    }
    while (*text != '\0') {
        emit(*text++, context);
        ++(*written);
    }
}

static void emit_unsigned(emit_fn emit, void *context, u64 value,
                          u32 base, bool uppercase, unsigned width,
                          char padding, int *written)
{
    char digits[65];
    unsigned count = 0U;
    const char *alphabet = uppercase ? "0123456789ABCDEF" : "0123456789abcdef";

    do {
        digits[count++] = alphabet[value % base];
        value /= base;
    } while (value != 0U && count < ARRAY_COUNT(digits));

    while (count < width) {
        emit(padding, context);
        ++(*written);
        --width;
    }
    while (count > 0U) {
        emit(digits[--count], context);
        ++(*written);
    }
}

static int format_core(emit_fn emit, void *context, const char *format,
                       va_list arguments)
{
    int written = 0;

    while (*format != '\0') {
        if (*format != '%') {
            emit(*format++, context);
            ++written;
            continue;
        }

        ++format;
        if (*format == '%') {
            emit('%', context);
            ++format;
            ++written;
            continue;
        }

        char padding = ' ';
        if (*format == '0') {
            padding = '0';
            ++format;
        }

        unsigned width = 0U;
        while (*format >= '0' && *format <= '9') {
            width = (width * 10U) + (unsigned)(*format - '0');
            ++format;
        }

        unsigned length = 0U;
        while (*format == 'l' && length < 2U) {
            ++length;
            ++format;
        }

        switch (*format) {
        case 'c': {
            const char value = (char)va_arg(arguments, int);
            emit(value, context);
            ++written;
            break;
        }
        case 's':
            emit_text(emit, context, va_arg(arguments, const char *), &written);
            break;
        case 'd':
        case 'i': {
            const i64 signed_value = length != 0U
                ? va_arg(arguments, i64)
                : (i64)va_arg(arguments, int);
            u64 magnitude;
            if (signed_value < 0) {
                emit('-', context);
                ++written;
                magnitude = (u64)(-(signed_value + 1)) + 1U;
            } else {
                magnitude = (u64)signed_value;
            }
            emit_unsigned(emit, context, magnitude, 10U, false, width,
                          padding, &written);
            break;
        }
        case 'u': {
            const u64 value = length != 0U
                ? va_arg(arguments, u64)
                : (u64)va_arg(arguments, unsigned int);
            emit_unsigned(emit, context, value, 10U, false, width,
                          padding, &written);
            break;
        }
        case 'x':
        case 'X': {
            const bool uppercase = *format == 'X';
            const u64 value = length != 0U
                ? va_arg(arguments, u64)
                : (u64)va_arg(arguments, unsigned int);
            emit_unsigned(emit, context, value, 16U, uppercase, width,
                          padding, &written);
            break;
        }
        case 'p': {
            const u64 value = (u64)(usize)va_arg(arguments, void *);
            emit_text(emit, context, "0x", &written);
            emit_unsigned(emit, context, value, 16U, false, 16U, '0',
                          &written);
            break;
        }
        case '\0':
            return written;
        default:
            emit('%', context);
            emit(*format, context);
            written += 2;
            break;
        }
        ++format;
    }
    return written;
}

int fm_vprintf(const char *format, va_list arguments)
{
    va_list copy;
    va_copy(copy, arguments);
    const int result = format_core(console_emit, NULL, format, copy);
    va_end(copy);
    return result;
}

int fm_printf(const char *format, ...)
{
    va_list arguments;
    va_start(arguments, format);
    const int result = fm_vprintf(format, arguments);
    va_end(arguments);
    return result;
}

int fm_vsnprintf(char *buffer, usize capacity, const char *format,
                 va_list arguments)
{
    buffer_sink_t sink = {
        .buffer = buffer,
        .capacity = capacity,
        .position = 0U,
        .total = 0U,
    };

    va_list copy;
    va_copy(copy, arguments);
    (void)format_core(buffer_emit, &sink, format, copy);
    va_end(copy);

    if (capacity != 0U) {
        const usize terminator = sink.position < capacity ? sink.position
                                                          : capacity - 1U;
        buffer[terminator] = '\0';
    }
    return (int)sink.total;
}

int fm_snprintf(char *buffer, usize capacity, const char *format, ...)
{
    va_list arguments;
    va_start(arguments, format);
    const int result = fm_vsnprintf(buffer, capacity, format, arguments);
    va_end(arguments);
    return result;
}
