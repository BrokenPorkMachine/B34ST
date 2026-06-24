#include "fbr34ker/exception.h"
#include "fbr34ker/crash.h"
#include "fbr34ker/format.h"
#include "fbr34ker/interrupt.h"
#include "fbr34ker/mmio.h"
#include "fbr34ker/protocol.h"
#include "fbr34ker/framebuffer_console.h"

extern u8 vectors[];

static const char *vector_name(u64 vector)
{
    static const char *const names[16] = {
        "current EL SP0 synchronous", "current EL SP0 IRQ",
        "current EL SP0 FIQ",         "current EL SP0 SError",
        "current EL SPx synchronous", "current EL SPx IRQ",
        "current EL SPx FIQ",         "current EL SPx SError",
        "lower EL AArch64 synchronous", "lower EL AArch64 IRQ",
        "lower EL AArch64 FIQ",         "lower EL AArch64 SError",
        "lower EL AArch32 synchronous", "lower EL AArch32 IRQ",
        "lower EL AArch32 FIQ",         "lower EL AArch32 SError",
    };
    return vector < ARRAY_COUNT(names) ? names[vector] : "unknown";
}

void exception_init(void)
{
    const u64 vector_base = (u64)(usize)vectors;
    __asm__ volatile("msr vbar_el1, %0\nisb" :: "r"(vector_base) : "memory");
}

void exception_handle(exception_frame_t *frame)
{
    if (frame == NULL) return;
    if (interrupt_handle_vector(frame->vector)) {
        return;
    }
    if (mmio_handle_fault(frame->esr, frame->far, &frame->elr)) {
        return;
    }
    crash_capture(frame);
    framebuffer_console_panic("UNHANDLED ARM64 EXCEPTION");
    fm_printf("\n\n*** FBR34KER exception ***\n");
    fm_printf("Vector: %llu (%s)\n", frame->vector,
              vector_name(frame->vector));
    crash_print();
    fm_printf("Crash console active. Use framed CRASH_GET, 'r' to reboot, "
              "or 'h' to halt.\n");
    protocol_crash_loop();
}
