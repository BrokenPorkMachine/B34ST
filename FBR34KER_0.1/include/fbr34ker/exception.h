#pragma once
#include "fbr34ker/types.h"


typedef struct {
    u64 current_el;
    u64 daif;
    u64 mpidr_el1;
    u64 sctlr_el1;
    u64 tcr_el1;
    u64 ttbr0_el1;
    u64 ttbr1_el1;
    u64 mair_el1;
    u64 vbar_el1;
    u64 cntfrq_el0;
} cpu_system_registers_t;

typedef struct {
    u64 x[31];
    u64 vector;
    u64 esr;
    u64 far;
    u64 elr;
    u64 spsr;
    u64 current_el;
    u64 stack_pointer;
} exception_frame_t;

void exception_init(void);
void exception_handle(exception_frame_t *frame);
u64 cpu_current_el(void);
void cpu_read_system_registers(cpu_system_registers_t *registers);
NORETURN void cpu_halt_forever(void);
