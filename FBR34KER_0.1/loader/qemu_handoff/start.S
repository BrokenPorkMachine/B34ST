.section .text.boot, "ax"
.align 7
.global _start
.type _start, %function
_start:
    mov x19, x0

    /* QEMU uses GICv3; allow the generic image to use ICC_*_EL1 registers. */
    mrs x1, CurrentEL
    cmp x1, #0x8
    b.ne 0f
    mrs x1, ICC_SRE_EL2
    mov x2, #0x9
    orr x1, x1, x2
    msr ICC_SRE_EL2, x1
    isb
0:
    adrp x1, __loader_stack_top
    add  x1, x1, :lo12:__loader_stack_top
    mov sp, x1

    adrp x1, __loader_bss_start
    add  x1, x1, :lo12:__loader_bss_start
    adrp x2, __loader_bss_end
    add  x2, x2, :lo12:__loader_bss_end
1:
    cmp x1, x2
    b.hs 2f
    str xzr, [x1], #8
    b 1b
2:
    mov x0, x19
    bl qemu_loader_main
3:
    wfe
    b 3b
.size _start, . - _start
