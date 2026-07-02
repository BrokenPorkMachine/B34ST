#include <stdarg.h>

#include "fbr34ker/log.h"
#include "fbr34ker/mmu.h"
#include "fbr34ker/types.h"

// SPDX-License-Identifier: BSD-2-Clause
static bool stub_mmu_ready;

void log_write(log_level_t level, const char *format, ...)
{
    UNUSED(level);
    UNUSED(format);
}

bool mmu_init(void)
{
    stub_mmu_ready = true;
    return true;
}

void mmu_shutdown(void)
{
    stub_mmu_ready = false;
}

bool mmu_allocate_page_table_pool(u64 base, usize size)
{
    UNUSED(base);
    UNUSED(size);
    return true;
}

bool mmu_setup_identity_map(u64 phys_base, u64 size)
{
    UNUSED(phys_base);
    UNUSED(size);
    return true;
}

bool mmu_healthy(void)
{
    return stub_mmu_ready;
}
