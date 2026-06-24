#include "fbr34ker/console.h"
#include "fbr34ker/platform.h"
#include "fbr34ker/watchdog.h"
#include "fbr34ker/framebuffer_console.h"

static char *capture_buffer;
static usize capture_capacity;
static usize capture_length;
static bool capture_suppress_uart;
static char history_buffer[CONSOLE_HISTORY_CAPACITY];
static usize history_start;
static usize history_length;
static u64 history_total;
static bool semihosting_mirror;

void console_init(void)
{
    history_start = 0U;
    history_length = 0U;
    history_total = 0U;
    platform_init();
    framebuffer_console_init();
    semihosting_mirror = false;
}

static void history_putc(char value)
{
    usize index;
    if (history_length < CONSOLE_HISTORY_CAPACITY) {
        index = (history_start + history_length) % CONSOLE_HISTORY_CAPACITY;
        ++history_length;
    } else {
        index = history_start;
        history_start = (history_start + 1U) % CONSOLE_HISTORY_CAPACITY;
    }
    history_buffer[index] = value;
    ++history_total;
}

static void capture_putc(char value)
{
    if (capture_buffer == NULL || capture_capacity == 0U) {
        return;
    }
    if (capture_length + 1U < capture_capacity) {
        capture_buffer[capture_length] = value;
    }
    ++capture_length;
}

void console_putc(char value)
{
    history_putc(value);
    capture_putc(value);
    framebuffer_console_putc(value);
    if (capture_suppress_uart) {
        return;
    }
    if (value == '\n') {
        platform_uart_putc('\r');
    }
    platform_uart_putc(value);
    if (semihosting_mirror) {
        (void)platform_semihosting_putc(value);
    }
    if (value == '\n') {
        platform_console_flush();
    }
}

void console_write(const char *text)
{
    if (text == NULL) {
        return;
    }
    while (*text != '\0') {
        console_putc(*text++);
    }
}

void console_write_n(const char *text, usize length)
{
    if (text == NULL) {
        return;
    }
    for (usize index = 0U; index < length; ++index) {
        console_putc(text[index]);
    }
}

int console_getc_nonblocking(void)
{
    return platform_uart_getc_nonblocking();
}

char console_getc_blocking(void)
{
    for (;;) {
        const int value = console_getc_nonblocking();
        if (value >= 0) {
            return (char)value;
        }
        watchdog_service();
        __asm__ volatile("yield");
    }
}

void console_capture_begin(char *buffer, usize capacity, bool suppress_uart)
{
    capture_buffer = buffer;
    capture_capacity = capacity;
    capture_length = 0U;
    capture_suppress_uart = suppress_uart;
    if (buffer != NULL && capacity != 0U) {
        buffer[0] = '\0';
    }
}

usize console_capture_end(void)
{
    const usize actual = capture_length;
    if (capture_buffer != NULL && capture_capacity != 0U) {
        const usize terminator = actual < capture_capacity
            ? actual : capture_capacity - 1U;
        capture_buffer[terminator] = '\0';
    }
    capture_buffer = NULL;
    capture_capacity = 0U;
    capture_length = 0U;
    capture_suppress_uart = false;
    return actual;
}


usize console_history_copy(char *buffer, usize capacity)
{
    if (buffer == NULL || capacity == 0U) {
        return history_length;
    }
    const usize copied = history_length < capacity - 1U
        ? history_length : capacity - 1U;
    const usize skip = history_length - copied;
    for (usize index = 0U; index < copied; ++index) {
        buffer[index] = history_buffer[(history_start + skip + index) %
                                       CONSOLE_HISTORY_CAPACITY];
    }
    buffer[copied] = '\0';
    return copied;
}

console_history_stats_t console_history_stats(void)
{
    return (console_history_stats_t){
        .total_characters = history_total,
        .overwritten_characters = history_total > history_length
            ? history_total - history_length : 0U,
        .retained_characters = history_length,
    };
}


bool console_semihosting_set(bool enabled)
{
    if (enabled && !platform_semihosting_available()) {
        return false;
    }
    semihosting_mirror = enabled;
    return true;
}

bool console_semihosting_enabled(void)
{
    return semihosting_mirror;
}
