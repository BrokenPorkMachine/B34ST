.section .vectors, "ax"
.align 11
.global vectors
.type vectors, %object

/* Preserve x16/x17 before using x16 as the vector-number scratch register. */
.macro VECTOR_SLOT number
    .align 7
    sub     sp, sp, #16
    stp     x16, x17, [sp]
    mov     x16, #\number
    b       .Lexception_entry
    .space 112
.endm

vectors:
    VECTOR_SLOT 0
    VECTOR_SLOT 1
    VECTOR_SLOT 2
    VECTOR_SLOT 3
    VECTOR_SLOT 4
    VECTOR_SLOT 5
    VECTOR_SLOT 6
    VECTOR_SLOT 7
    VECTOR_SLOT 8
    VECTOR_SLOT 9
    VECTOR_SLOT 10
    VECTOR_SLOT 11
    VECTOR_SLOT 12
    VECTOR_SLOT 13
    VECTOR_SLOT 14
    VECTOR_SLOT 15
.size vectors, . - vectors

.section .text, "ax"
.align 4
.Lexception_entry:
    /* 304-byte frame plus the 16-byte x16/x17 save made by the vector slot. */
    sub     sp, sp, #304
    stp     x0,  x1,  [sp, #0]
    stp     x2,  x3,  [sp, #16]
    stp     x4,  x5,  [sp, #32]
    stp     x6,  x7,  [sp, #48]
    stp     x8,  x9,  [sp, #64]
    stp     x10, x11, [sp, #80]
    stp     x12, x13, [sp, #96]
    stp     x14, x15, [sp, #112]

    ldp     x0, x1, [sp, #304]
    stp     x0, x1, [sp, #128]

    stp     x18, x19, [sp, #144]
    stp     x20, x21, [sp, #160]
    stp     x22, x23, [sp, #176]
    stp     x24, x25, [sp, #192]
    stp     x26, x27, [sp, #208]
    stp     x28, x29, [sp, #224]
    str     x30,      [sp, #240]
    str     x16,      [sp, #248]

    mrs     x0, esr_el1
    str     x0, [sp, #256]
    mrs     x0, far_el1
    str     x0, [sp, #264]
    mrs     x0, elr_el1
    str     x0, [sp, #272]
    mrs     x0, spsr_el1
    str     x0, [sp, #280]
    mrs     x0, CurrentEL
    str     x0, [sp, #288]
    add     x0, sp, #320
    str     x0, [sp, #296]

    mov     x0, sp
    bl      exception_handle

    /* A contained probe may advance the saved return address. */
    ldr     x0, [sp, #272]
    msr     elr_el1, x0
    ldr     x0, [sp, #280]
    msr     spsr_el1, x0
    isb

    /* Interrupt handlers may return. Restore the complete exception frame. */
    ldp     x0,  x1,  [sp, #0]
    ldp     x2,  x3,  [sp, #16]
    ldp     x4,  x5,  [sp, #32]
    ldp     x6,  x7,  [sp, #48]
    ldp     x8,  x9,  [sp, #64]
    ldp     x10, x11, [sp, #80]
    ldp     x12, x13, [sp, #96]
    ldp     x14, x15, [sp, #112]
    ldp     x16, x17, [sp, #128]
    ldp     x18, x19, [sp, #144]
    ldp     x20, x21, [sp, #160]
    ldp     x22, x23, [sp, #176]
    ldp     x24, x25, [sp, #192]
    ldp     x26, x27, [sp, #208]
    ldp     x28, x29, [sp, #224]
    ldr     x30,      [sp, #240]
    add     sp, sp, #320
    eret
