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

static usize text_length(const char *text)
{
    if (text == NULL) {
        return sizeof("(null)") - 1U;
    }
    usize length = 0U;
    while (text[length] != '\0') {
        ++length;
    }
    return length;
}

static void emit_padding(emit_fn emit, void *context, unsigned count,
                         char padding, int *written)
{
    while (count > 0U) {
        emit(padding, context);
        ++(*written);
        --count;
    }
}

static void emit_padded_text(emit_fn emit, void *context, const char *text,
                             unsigned width, bool left_align, int *written)
{
    const usize length = text_length(text);
    const unsigned padding = length < (usize)width
        ? width - (unsigned)length
        : 0U;
    if (!left_align) {
        emit_padding(emit, context, padding, ' ', written);
    }
    emit_text(emit, context, text, written);
    if (left_align) {
        emit_padding(emit, context, padding, ' ', written);
    }
}

static void emit_unsigned(emit_fn emit, void *context, u64 value,
                          u32 base, bool uppercase, unsigned width,
                          char padding, bool left_align, char prefix,
                          int *written)
{
    char digits[65];
    unsigned count = 0U;
    const char *alphabet = uppercase ? "0123456789ABCDEF" : "0123456789abcdef";

    if (base == 0U) return;

    do {
        digits[count++] = alphabet[value % base];
        value /= base;
    } while (value != 0U && count < ARRAY_COUNT(digits));

    const unsigned field_count = count + (prefix != '\0' ? 1U : 0U);
    const unsigned padding_count = field_count < width
        ? width - field_count
        : 0U;
    if (!left_align && padding == ' ') {
        emit_padding(emit, context, padding_count, padding, written);
    }
    if (prefix != '\0') {
        emit(prefix, context);
        ++(*written);
    }
    if (!left_align && padding != ' ') {
        emit_padding(emit, context, padding_count, padding, written);
    }
    while (count > 0U) {
        emit(digits[--count], context);
        ++(*written);
    }
    if (left_align) {
        emit_padding(emit, context, padding_count, ' ', written);
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
        bool left_align = false;
        bool parsing_flags = true;
        while (parsing_flags) {
            switch (*format) {
            case '-':
                left_align = true;
                ++format;
                break;
            case '0':
                padding = '0';
                ++format;
                break;
            default:
                parsing_flags = false;
                break;
            }
        }
        if (left_align) {
            padding = ' ';
        }

        u32 width = 0U;
        while (*format >= '0' && *format <= '9') {
            if (width > 65535U) break;
            width = (width * 10U) + (u32)(*format - '0');
            ++format;
        }

        unsigned length = 0U;
        if (*format == 'z') {
            length = 3U;
            ++format;
        } else {
            while (*format == 'l' && length < 2U) {
                ++length;
                ++format;
            }
        }

        switch (*format) {
        case 'c': {
            const char value = (char)va_arg(arguments, int);
            if (!left_align && width > 1U) {
                emit_padding(emit, context, width - 1U, ' ', &written);
            }
            emit(value, context);
            ++written;
            if (left_align && width > 1U) {
                emit_padding(emit, context, width - 1U, ' ', &written);
            }
            break;
        }
        case 's':
            emit_padded_text(emit, context,
                             va_arg(arguments, const char *), width,
                             left_align, &written);
            break;
        case 'd':
        case 'i': {
            i64 signed_value;
            if (length == 3U) {
                signed_value = (i64)va_arg(arguments, isize);
            } else if (length != 0U) {
                signed_value = va_arg(arguments, i64);
            } else {
                signed_value = (i64)va_arg(arguments, int);
            }
            u64 magnitude;
            char prefix = '\0';
            if (signed_value < 0) {
                prefix = '-';
                magnitude = (u64)(-(signed_value + 1)) + 1U;
            } else {
                magnitude = (u64)signed_value;
            }
            emit_unsigned(emit, context, magnitude, 10U, false, width,
                          padding, left_align, prefix, &written);
            break;
        }
        case 'u': {
            u64 value;
            if (length == 3U) {
                value = (u64)va_arg(arguments, usize);
            } else if (length != 0U) {
                value = va_arg(arguments, u64);
            } else {
                value = (u64)va_arg(arguments, unsigned int);
            }
            emit_unsigned(emit, context, value, 10U, false, width,
                          padding, left_align, '\0', &written);
            break;
        }
        case 'x':
        case 'X': {
            const bool uppercase = *format == 'X';
            u64 value;
            if (length == 3U) {
                value = (u64)va_arg(arguments, usize);
            } else if (length != 0U) {
                value = va_arg(arguments, u64);
            } else {
                value = (u64)va_arg(arguments, unsigned int);
            }
            emit_unsigned(emit, context, value, 16U, uppercase, width,
                          padding, left_align, '\0', &written);
            break;
        }
        case 'p': {
            const u64 value = (u64)(usize)va_arg(arguments, void *);
            emit_text(emit, context, "0x", &written);
            emit_unsigned(emit, context, value, 16U, false, 16U, '0',
                          false, '\0', &written);
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
