#include "fbr34ker/framebuffer_console.h"
#include "fbr34ker/handoff.h"
#include "fbr34ker/hardware_probe.h"
#include "fbr34ker/platform.h"
#include "fbr34ker/string.h"

#define GLYPH_WIDTH 5U
#define CELL_WIDTH 6U
#define CELL_HEIGHT 8U

typedef struct {
    platform_framebuffer_t framebuffer;
    bool available;
    bool enabled;
    u32 column;
    u32 row;
    u32 foreground;
    u32 background;
    u64 rendered;
    u64 scrolls;
} framebuffer_console_state_t;

static framebuffer_console_state_t state;

static const u8 digit_font[10][5] = {
    {0x3e,0x51,0x49,0x45,0x3e}, {0x00,0x42,0x7f,0x40,0x00},
    {0x42,0x61,0x51,0x49,0x46}, {0x21,0x41,0x45,0x4b,0x31},
    {0x18,0x14,0x12,0x7f,0x10}, {0x27,0x45,0x45,0x45,0x39},
    {0x3c,0x4a,0x49,0x49,0x30}, {0x01,0x71,0x09,0x05,0x03},
    {0x36,0x49,0x49,0x49,0x36}, {0x06,0x49,0x49,0x29,0x1e},
};

static const u8 letter_font[26][5] = {
    {0x7e,0x11,0x11,0x11,0x7e}, {0x7f,0x49,0x49,0x49,0x36},
    {0x3e,0x41,0x41,0x41,0x22}, {0x7f,0x41,0x41,0x22,0x1c},
    {0x7f,0x49,0x49,0x49,0x41}, {0x7f,0x09,0x09,0x09,0x01},
    {0x3e,0x41,0x49,0x49,0x7a}, {0x7f,0x08,0x08,0x08,0x7f},
    {0x00,0x41,0x7f,0x41,0x00}, {0x20,0x40,0x41,0x3f,0x01},
    {0x7f,0x08,0x14,0x22,0x41}, {0x7f,0x40,0x40,0x40,0x40},
    {0x7f,0x02,0x0c,0x02,0x7f}, {0x7f,0x04,0x08,0x10,0x7f},
    {0x3e,0x41,0x41,0x41,0x3e}, {0x7f,0x09,0x09,0x09,0x06},
    {0x3e,0x41,0x51,0x21,0x5e}, {0x7f,0x09,0x19,0x29,0x46},
    {0x46,0x49,0x49,0x49,0x31}, {0x01,0x01,0x7f,0x01,0x01},
    {0x3f,0x40,0x40,0x40,0x3f}, {0x1f,0x20,0x40,0x20,0x1f},
    {0x3f,0x40,0x38,0x40,0x3f}, {0x63,0x14,0x08,0x14,0x63},
    {0x07,0x08,0x70,0x08,0x07}, {0x61,0x51,0x49,0x45,0x43},
};

static void glyph_for(char value, u8 columns[5])
{
    fm_memset(columns, 0, 5U);
    if (value >= 'a' && value <= 'z') value = (char)(value - 'a' + 'A');
    if (value >= '0' && value <= '9') {
        fm_memcpy(columns, digit_font[(u32)(value - '0')], 5U);
        return;
    }
    if (value >= 'A' && value <= 'Z') {
        fm_memcpy(columns, letter_font[(u32)(value - 'A')], 5U);
        return;
    }
    switch (value) {
    case ' ': return;
    case '.': columns[2] = 0x60; return;
    case ',': columns[2] = 0x40; columns[1] = 0x20; return;
    case ':': columns[2] = 0x36; return;
    case ';': columns[2] = 0x46; columns[1] = 0x20; return;
    case '-': columns[1]=columns[2]=columns[3]=0x08; return;
    case '_': for (u32 i=0;i<5U;++i) columns[i]=0x40; return;
    case '/': columns[0]=0x20; columns[1]=0x10; columns[2]=0x08; columns[3]=0x04; columns[4]=0x02; return;
    case '\\': columns[0]=0x02; columns[1]=0x04; columns[2]=0x08; columns[3]=0x10; columns[4]=0x20; return;
    case '>': columns[1]=0x41; columns[2]=0x22; columns[3]=0x14; columns[4]=0x08; return;
    case '<': columns[0]=0x08; columns[1]=0x14; columns[2]=0x22; columns[3]=0x41; return;
    case '=': columns[1]=columns[2]=columns[3]=0x14; return;
    case '+': columns[2]=0x3e; columns[1]=columns[3]=0x08; return;
    case '!': columns[2]=0x5f; return;
    case '?': columns[0]=0x02; columns[1]=0x01; columns[2]=0x51; columns[3]=0x09; columns[4]=0x06; return;
    case '[': columns[1]=0x7f; columns[2]=0x41; return;
    case ']': columns[2]=0x41; columns[3]=0x7f; return;
    case '(': columns[2]=0x1c; columns[1]=0x22; columns[0]=0x41; return;
    case ')': columns[2]=0x1c; columns[3]=0x22; columns[4]=0x41; return;
    case '#': columns[0]=0x14; columns[1]=0x7f; columns[2]=0x14; columns[3]=0x7f; columns[4]=0x14; return;
    default:
        columns[0]=columns[4]=0x7f;
        columns[1]=columns[2]=columns[3]=0x41;
        return;
    }
}

static bool framebuffer_valid(const platform_framebuffer_t *fb)
{
    if (fb == NULL || fb->base == 0U || fb->width < CELL_WIDTH ||
        fb->height < CELL_HEIGHT || fb->pixels_per_row < fb->width) return false;
    if (fb->pixel_format == FBR34KER_PIXEL_FORMAT_RGB565) return fb->bytes_per_pixel == 2U;
    return fb->bytes_per_pixel == 4U &&
        (fb->pixel_format == FBR34KER_PIXEL_FORMAT_XRGB8888 ||
         fb->pixel_format == FBR34KER_PIXEL_FORMAT_ARGB8888 ||
         fb->pixel_format == FBR34KER_PIXEL_FORMAT_BGRA8888);
}

static void write_pixel(u32 x, u32 y, u32 rgb)
{
    if (x >= state.framebuffer.width || y >= state.framebuffer.height) return;
    u8 *pixel = (u8 *)(usize)state.framebuffer.base +
        ((usize)y * state.framebuffer.pixels_per_row + x) *
        state.framebuffer.bytes_per_pixel;
    const u8 red = (u8)(rgb >> 16U);
    const u8 green = (u8)(rgb >> 8U);
    const u8 blue = (u8)rgb;
    if (state.framebuffer.pixel_format == FBR34KER_PIXEL_FORMAT_RGB565) {
        const u16 value = (u16)(((u16)(red >> 3U) << 11U) |
                                ((u16)(green >> 2U) << 5U) |
                                (u16)(blue >> 3U));
        pixel[0] = (u8)value;
        pixel[1] = (u8)(value >> 8U);
    } else if (state.framebuffer.pixel_format == FBR34KER_PIXEL_FORMAT_BGRA8888) {
        pixel[0] = red; pixel[1] = green; pixel[2] = blue; pixel[3] = 0xffU;
    } else {
        pixel[0] = blue; pixel[1] = green; pixel[2] = red;
        pixel[3] = state.framebuffer.pixel_format == FBR34KER_PIXEL_FORMAT_ARGB8888 ? 0xffU : 0U;
    }
}

static void clear_rows(u32 first, u32 count)
{
    const u32 end = first + count < state.framebuffer.height
        ? first + count : state.framebuffer.height;
    for (u32 y = first; y < end; ++y) {
        for (u32 x = 0U; x < state.framebuffer.width; ++x) write_pixel(x, y, state.background);
    }
}

static void scroll(void)
{
    const usize row_bytes = (usize)state.framebuffer.pixels_per_row *
                            state.framebuffer.bytes_per_pixel;
    const usize move_bytes = (usize)(state.framebuffer.height - CELL_HEIGHT) * row_bytes;
    u8 *base = (u8 *)(usize)state.framebuffer.base;
    fm_memmove(base, base + CELL_HEIGHT * row_bytes, move_bytes);
    clear_rows(state.framebuffer.height - CELL_HEIGHT, CELL_HEIGHT);
    if (state.row != 0U) --state.row;
    ++state.scrolls;
}

static void newline(void)
{
    state.column = 0U;
    ++state.row;
    if (state.row >= state.framebuffer.height / CELL_HEIGHT) scroll();
}

void framebuffer_console_init(void)
{
    fm_memset(&state, 0, sizeof(state));
    state.foreground = 0xe8e8e8U;
    state.background = 0x101820U;
    state.available = platform_framebuffer_info(&state.framebuffer) &&
                      framebuffer_valid(&state.framebuffer);
}

bool framebuffer_console_set_enabled(bool enabled)
{
    if (enabled && !hardware_probe_framebuffer_writes_allowed()) return false;
    if (enabled && !state.available) return false;
    state.enabled = enabled;
    return true;
}

bool framebuffer_console_enabled(void)
{
    return state.enabled;
}

void framebuffer_console_putc(char value)
{
    if (!state.enabled || !state.available) return;
    if (value == '\r') { state.column = 0U; return; }
    if (value == '\n') { newline(); (void)platform_framebuffer_flush(); return; }
    if (value == '\t') {
        do { framebuffer_console_putc(' '); } while ((state.column & 3U) != 0U);
        return;
    }
    if ((u8)value < 0x20U || (u8)value > 0x7eU) value = '?';
    if (state.column >= state.framebuffer.width / CELL_WIDTH) newline();
    u8 glyph[5];
    glyph_for(value, glyph);
    const u32 left = state.column * CELL_WIDTH;
    const u32 top = state.row * CELL_HEIGHT;
    for (u32 x = 0U; x < CELL_WIDTH; ++x) {
        for (u32 y = 0U; y < CELL_HEIGHT; ++y) {
            const bool set = x < GLYPH_WIDTH && y < 7U &&
                             (glyph[x] & (1U << y)) != 0U;
            write_pixel(left + x, top + y, set ? state.foreground : state.background);
        }
    }
    ++state.column;
    ++state.rendered;
}

void framebuffer_console_write(const char *text)
{
    if (text == NULL) return;
    while (*text != '\0') framebuffer_console_putc(*text++);
}

bool framebuffer_console_clear(void)
{
    if (!hardware_probe_framebuffer_writes_allowed()) return false;
    if (!state.available) return false;
    clear_rows(0U, state.framebuffer.height);
    state.column = 0U;
    state.row = 0U;
    return platform_framebuffer_flush();
}

void framebuffer_console_panic(const char *message)
{
    if (!hardware_probe_framebuffer_writes_allowed()) return;
    if (!state.available) return;
    state.background = 0x480000U;
    state.foreground = 0xffffffU;
    state.enabled = true;
    (void)framebuffer_console_clear();
    framebuffer_console_write("FBR34KER PANIC\n\n");
    framebuffer_console_write(message != NULL ? message : "UNHANDLED EXCEPTION");
    framebuffer_console_putc('\n');
    (void)platform_framebuffer_flush();
}

framebuffer_console_stats_t framebuffer_console_stats(void)
{
    return (framebuffer_console_stats_t){
        .available = state.available,
        .enabled = state.enabled,
        .columns = state.available ? state.framebuffer.width / CELL_WIDTH : 0U,
        .rows = state.available ? state.framebuffer.height / CELL_HEIGHT : 0U,
        .cursor_column = state.column,
        .cursor_row = state.row,
        .rendered_characters = state.rendered,
        .scroll_count = state.scrolls,
    };
}
