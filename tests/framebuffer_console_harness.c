#include "fbr34ker/framebuffer_console.h"
#include "fbr34ker/handoff.h"
#include "fbr34ker/hardware_probe.h"
#include "fbr34ker/platform.h"
#include "fbr34ker/string.h"

// SPDX-License-Identifier: BSD-2-Clause
bool hardware_probe_framebuffer_writes_allowed(void) { return true; }

static u8 storage[96U * 40U * 4U];
static u32 format = FBR34KER_PIXEL_FORMAT_XRGB8888;
static u32 bpp = 4U;
static u64 flushes;

bool platform_framebuffer_info(platform_framebuffer_t *framebuffer)
{
    if (framebuffer == NULL) return false;
    *framebuffer = (platform_framebuffer_t){
        .base = (u64)(usize)storage,
        .size = sizeof(storage),
        .width = 96U,
        .height = 40U,
        .pixels_per_row = 96U,
        .pixel_format = format,
        .bytes_per_pixel = bpp,
        .rotation = 0U,
    };
    return true;
}

bool platform_framebuffer_flush(void)
{
    ++flushes;
    return true;
}

int main(void)
{
    fm_memset(storage, 0, sizeof(storage));
    framebuffer_console_init();
    framebuffer_console_stats_t stats = framebuffer_console_stats();
    if (!stats.available || stats.enabled || stats.columns != 16U || stats.rows != 5U) return 1;
    if (!framebuffer_console_set_enabled(true) || !framebuffer_console_clear()) return 2;
    framebuffer_console_write("HELLO 123\nSECOND\nTHIRD\nFOURTH\nFIFTH\nSIXTH\n");
    stats = framebuffer_console_stats();
    if (!stats.enabled || stats.rendered_characters < 20U || stats.scroll_count == 0U) return 3;
    bool changed = false;
    for (usize index = 0U; index < sizeof(storage); ++index) {
        if (storage[index] != 0U) { changed = true; break; }
    }
    if (!changed || flushes == 0U) return 4;
    framebuffer_console_panic("TEST");
    stats = framebuffer_console_stats();
    if (!stats.enabled || stats.cursor_row == 0U) return 5;

    format = FBR34KER_PIXEL_FORMAT_RGB565;
    bpp = 2U;
    framebuffer_console_init();
    if (!framebuffer_console_set_enabled(true) || !framebuffer_console_clear()) return 6;
    framebuffer_console_write("RGB565");
    return 0;
}
