.section .text.boot, "ax"
.align 7
.global _start
.global fbr34ker_entry
.type _start, %function
.type fbr34ker_entry, %function

_start:
    /* QEMU supplies an FDT pointer in x0; generic loaders supply a handoff. */
    b       fbr34ker_entry

/*
 * Generic monitor entry. x0 may contain a validated handoff structure.
 * QEMU may pass an FDT pointer; an authorized loader may pass a handoff.
 */
fbr34ker_entry:
    mov     x19, x0
    mrs     x0, CurrentEL
    cmp     x0, #0x8
    b.eq    .Lfrom_el2
    cmp     x0, #0x4
    b.eq    .Lenter_el1
    b       .Lunsupported_el

.Lfrom_el2:
    adrp    x1, __stack_top
    add     x1, x1, :lo12:__stack_top
    msr     sp_el1, x1

    /* Run the monitor as AArch64 EL1 and allow access to the virtual timer. */
    mov     x1, #0x80000000
    msr     hcr_el2, x1
    mrs     x1, cnthctl_el2
    orr     x1, x1, #3
    msr     cnthctl_el2, x1
    msr     cntvoff_el2, xzr

#ifdef FBR34KER_ENABLE_GICV3_SRE
    /* Permit EL1 access to the GICv3 system-register interface on QEMU. */
    mrs     x1, ICC_SRE_EL2
    mov     x2, #0x9          /* SRE | Enable */
    orr     x1, x1, x2
    msr     ICC_SRE_EL2, x1
    isb
#endif

    adrp    x1, .Lenter_el1
    add     x1, x1, :lo12:.Lenter_el1
    msr     elr_el2, x1
    mov     x1, #0x3c5          /* Mask DAIF, return to EL1h. */
    msr     spsr_el2, x1
    isb
    eret

.Lenter_el1:
    adrp    x1, __stack_top
    add     x1, x1, :lo12:__stack_top
    mov     sp, x1

    msr     daifset, #0xf
    adrp    x1, vectors
    add     x1, x1, :lo12:vectors
    msr     vbar_el1, x1
    isb

    /* Clear BSS without relying on a C runtime. */
    adrp    x1, __bss_start
    add     x1, x1, :lo12:__bss_start
    adrp    x2, __bss_end
    add     x2, x2, :lo12:__bss_end
.Lclear_bss:
    cmp     x1, x2
    b.hs    .Lbss_done
    str     xzr, [x1], #8
    b       .Lclear_bss
.Lbss_done:
    mov     x0, x19
    bl      kernel_main

.Lunsupported_el:
    wfe
    b       .Lunsupported_el

.size _start, . - _start
.size fbr34ker_entry, . - fbr34ker_entry
