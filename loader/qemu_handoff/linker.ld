OUTPUT_ARCH(aarch64)
ENTRY(_start)
MEMORY
{
    LOADER (rwx) : ORIGIN = 0x40080000, LENGTH = 512K
}
SECTIONS
{
    . = ORIGIN(LOADER);
    __loader_start = .;
    .text : ALIGN(4096) { KEEP(*(.text.boot)) *(.text .text.*) } > LOADER
    .rodata : ALIGN(16) { *(.rodata .rodata.*) } > LOADER
    .data : ALIGN(16) { *(.data .data.*) } > LOADER
    .bss (NOLOAD) : ALIGN(16)
    {
        __loader_bss_start = .;
        *(.bss .bss.*) *(COMMON)
        . = ALIGN(16);
        __loader_bss_end = .;
    } > LOADER
    .stack (NOLOAD) : ALIGN(4096)
    {
        __loader_stack_bottom = .;
        . += 32K;
        __loader_stack_top = .;
    } > LOADER
    __loader_end = .;
    /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
ASSERT(__loader_end <= ORIGIN(LOADER) + LENGTH(LOADER), "QEMU handoff loader exceeds reserved window")
