OUTPUT_ARCH(aarch64)
ENTRY(_start)

MEMORY
{
    RAM (rwx) : ORIGIN = 0x40080000, LENGTH = 64M
}

SECTIONS
{
    . = ORIGIN(RAM);
    __image_start = .;

    .text : ALIGN(4096)
    {
        KEEP(*(.text.boot))
        *(.text .text.*)
    } > RAM

    .vectors : ALIGN(2048)
    {
        KEEP(*(.vectors))
    } > RAM

    .fbr34ker_build : ALIGN(16)
    {
        KEEP(*(.fbr34ker.build))
    } > RAM

    .rodata : ALIGN(16)
    {
        *(.rodata .rodata.*)
    } > RAM

    .data : ALIGN(16)
    {
        *(.data .data.*)
    } > RAM

    .crashlog (NOLOAD) : ALIGN(16)
    {
        KEEP(*(.crashlog))
    } > RAM

    .boot_evidence (NOLOAD) : ALIGN(16)
    {
        KEEP(*(.boot_evidence))
    } > RAM

    .bss (NOLOAD) : ALIGN(16)
    {
        __bss_start = .;
        *(.bss .bss.*)
        *(COMMON)
        . = ALIGN(16);
        __bss_end = .;
    } > RAM

    .stack_guard_low (NOLOAD) : ALIGN(4096)
    {
        __stack_guard_low_start = .;
        . += 4K;
        __stack_guard_low_end = .;
    } > RAM

    .stack (NOLOAD) : ALIGN(4096)
    {
        __stack_bottom = .;
        . += 64K;
        __stack_top = .;
    } > RAM

    .stack_guard_high (NOLOAD) : ALIGN(4096)
    {
        __stack_guard_high_start = .;
        . += 4K;
        __stack_guard_high_end = .;
    } > RAM

    .heap (NOLOAD) : ALIGN(4096)
    {
        __heap_start = .;
        . += 4M;
        __heap_end = .;
    } > RAM

    __image_end = .;

    /DISCARD/ :
    {
        *(.comment)
        *(.note*)
        *(.eh_frame*)
    }
}
