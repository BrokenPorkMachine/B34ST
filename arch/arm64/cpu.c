#include "fbr34ker/exception.h"

u64 cpu_current_el(void)
{
    u64 value;
    __asm__ volatile("mrs %0, CurrentEL" : "=r"(value));
    return (value >> 2U) & 0x3U;
}

void cpu_read_system_registers(cpu_system_registers_t *registers)
{
    if (registers == NULL) {
        return;
    }
    registers->current_el = cpu_current_el();
    __asm__ volatile("mrs %0, daif" : "=r"(registers->daif));
    __asm__ volatile("mrs %0, mpidr_el1" : "=r"(registers->mpidr_el1));
    __asm__ volatile("mrs %0, sctlr_el1" : "=r"(registers->sctlr_el1));
    __asm__ volatile("mrs %0, tcr_el1" : "=r"(registers->tcr_el1));
    __asm__ volatile("mrs %0, ttbr0_el1" : "=r"(registers->ttbr0_el1));
    __asm__ volatile("mrs %0, ttbr1_el1" : "=r"(registers->ttbr1_el1));
    __asm__ volatile("mrs %0, mair_el1" : "=r"(registers->mair_el1));
    __asm__ volatile("mrs %0, vbar_el1" : "=r"(registers->vbar_el1));
    __asm__ volatile("mrs %0, cntfrq_el0" : "=r"(registers->cntfrq_el0));
}

NORETURN void cpu_halt_forever(void)
{
    __asm__ volatile("msr daifset, #0xf" ::: "memory");
    for (;;) {
        __asm__ volatile("wfe");
    }
}
