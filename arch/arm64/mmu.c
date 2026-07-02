#include "fbr34ker/mmu.h"
#include "fbr34ker/mmio.h"
#include "fbr34ker/string.h"
#include "fbr34ker/log.h"
#include "fbr34ker/event.h"

// SPDX-License-Identifier: BSD-2-Clause
static mmu_status_t state;

static u64 page_table_alloc(void)
{
    if (state.page_table_pool_size < MMU_PAGE_SIZE) {
        return 0U;
    }
    u64 addr = state.page_table_pool;
    state.page_table_pool += MMU_PAGE_SIZE;
    state.page_table_pool_size -= MMU_PAGE_SIZE;
    fm_memset((void *)(usize)addr, 0, MMU_PAGE_SIZE);
    return addr;
}

bool mmu_allocate_page_table_pool(u64 base, usize size)
{
    if (base == 0U || size < (MMU_PAGE_SIZE * 4U)) {
        return false;
    }
    state.page_table_pool = base;
    state.page_table_pool_size = size;
    fm_memset((void *)(usize)base, 0, size);
    return true;
}

static u64 *get_pte_ptr(u64 *table, u64 index)
{
    return &table[index];
}

static bool setup_level0_table(u64 *root, u64 virt, u64 phys, u64 size, u64 attrs)
{
    for (u64 offset = 0U; offset < size;) {
        u64 l0_index = (virt + offset) >> 39;
        l0_index &= 0x1FFU;
        u64 *l0_entry = get_pte_ptr(root, l0_index);
        u64 block_size = 1ULL << 39;
        if ((*l0_entry & MMU_PTE_TYPE_MASK) == MMU_PTE_TYPE_FAULT) {
            if (size - offset >= block_size && (phys == 0U || (phys & (block_size - 1)) == 0U)) {
                *l0_entry = MMU_BLOCK_DESCRIPTOR(phys + offset, attrs);
                offset += block_size;
                continue;
            }
            u64 *l1_table = (u64 *)(usize)page_table_alloc();
            if (l1_table == NULL) return false;
            *l0_entry = MMU_TABLE_DESCRIPTOR((u64)(usize)l1_table);
        }
        u64 *l1_table = (u64 *)(usize)(*l0_entry & ~0xFFFULL);
        if (l1_table == NULL) return false;

        for (; offset < size;) {
            u64 l1_index = (virt + offset) >> 30;
            l1_index &= 0x1FFU;
            u64 *l1_entry = get_pte_ptr(l1_table, l1_index);
            u64 l1_block_size = 1ULL << 30;
            if ((*l1_entry & MMU_PTE_TYPE_MASK) == MMU_PTE_TYPE_FAULT) {
                if (size - offset >= l1_block_size && (phys == 0U || (phys & (l1_block_size - 1)) == 0U)) {
                    *l1_entry = MMU_BLOCK_DESCRIPTOR(phys + offset, attrs);
                    offset += l1_block_size;
                    continue;
                }
                u64 *l2_table = (u64 *)(usize)page_table_alloc();
                if (l2_table == NULL) return false;
                *l1_entry = MMU_TABLE_DESCRIPTOR((u64)(usize)l2_table);
            }
            u64 *l2_table = (u64 *)(usize)(*l1_entry & ~0xFFFULL);
            if (l2_table == NULL) return false;

            for (; offset < size;) {
                u64 l2_index = (virt + offset) >> 21;
                l2_index &= 0x1FFU;
                u64 *l2_entry = get_pte_ptr(l2_table, l2_index);
                u64 l2_block_size = 1ULL << 21;
                if ((*l2_entry & MMU_PTE_TYPE_MASK) == MMU_PTE_TYPE_FAULT) {
                    if (size - offset >= l2_block_size && (phys == 0U || (phys & (l2_block_size - 1)) == 0U)) {
                        *l2_entry = MMU_BLOCK_DESCRIPTOR(phys + offset, attrs);
                        offset += l2_block_size;
                        continue;
                    }
                    u64 *l3_table = (u64 *)(usize)page_table_alloc();
                    if (l3_table == NULL) return false;
                    *l2_entry = MMU_TABLE_DESCRIPTOR((u64)(usize)l3_table);
                }
                u64 *l3_table = (u64 *)(usize)(*l2_entry & ~0xFFFULL);
                if (l3_table == NULL) return false;

                for (; offset < size;) {
                    u64 l3_index = (virt + offset) >> 12;
                    l3_index &= 0x1FFU;
                    u64 *l3_entry = get_pte_ptr(l3_table, l3_index);
                    u64 page_size = MMU_PAGE_SIZE;
                    if ((*l3_entry & MMU_PTE_TYPE_MASK) == MMU_PTE_TYPE_FAULT) {
                        *l3_entry = MMU_PAGE_DESCRIPTOR(phys + offset, attrs);
                    }
                    offset += page_size;
                    if (offset >= size) break;
                }
                if (offset >= size) break;
            }
            if (offset >= size) break;
        }
    }
    return true;
}

bool mmu_setup_identity_map(u64 phys_base, u64 size)
{
    if (phys_base == 0U || size == 0U) {
        return false;
    }
    u64 root = page_table_alloc();
    if (root == 0U) {
        return false;
    }
    state.ttbr0 = root;
    state.ttbr1 = root;
    u64 attrs = MMU_PTE_PERM_RWX | MMU_PTE_ATTR_NORMAL_WB | MMU_PTE_ATTR_SH_INNER;
    if (!setup_level0_table((u64 *)(usize)root, phys_base, phys_base, size, attrs)) {
        return false;
    }
    log_write(LOG_LEVEL_INFO, "mmu: identity mapped 0x%llx - 0x%llx", phys_base, phys_base + size);
    return true;
}

bool mmu_enable(void)
{
    if (state.ttbr0 == 0U) {
        log_write(LOG_LEVEL_ERROR, "mmu: no page table configured, cannot enable");
        return false;
    }
    u64 tcr = MMU_TCR_T0SZ_48 | MMU_TCR_T1SZ_48 |
              MMU_TCR_TG0_4K | MMU_TCR_TG1_4K |
              MMU_TCR_IPS_4PB | MMU_TCR_HA | MMU_TCR_HD;
    u64 mair = MMU_MAIR_VALUE;
    u64 sctlr = MMU_SCTLR_M | MMU_SCTLR_C | MMU_SCTLR_I | MMU_SCTLR_SA | MMU_SCTLR_A;

    __asm__ volatile("msr tcr_el1, %0" : : "r"(tcr) : "memory");
    __asm__ volatile("msr mair_el1, %0" : : "r"(mair) : "memory");
    __asm__ volatile("msr ttbr0_el1, %0" : : "r"(state.ttbr0) : "memory");
    __asm__ volatile("msr ttbr1_el1, %0" : : "r"(state.ttbr1) : "memory");
    __asm__ volatile("isb" ::: "memory");

    state.tcr_el1 = tcr;
    state.mair_el1 = mair;

    __asm__ volatile("msr sctlr_el1, %0" : : "r"(sctlr) : "memory");
    __asm__ volatile("isb" ::: "memory");

    state.sctlr_el1 = sctlr;
    state.mmu_enabled = true;
    state.initialized = true;

    log_write(LOG_LEVEL_INFO, "mmu: enabled with 4K granule, 48-bit VA, identity map");
    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE, "mmu", 1U, 0U);
    return true;
}

void mmu_disable(void)
{
    if (!state.mmu_enabled) return;
    u64 sctlr;
    __asm__ volatile("mrs %0, sctlr_el1" : "=r"(sctlr));
    sctlr &= ~MMU_SCTLR_M;
    __asm__ volatile("msr sctlr_el1, %0" : : "r"(sctlr) : "memory");
    __asm__ volatile("isb" ::: "memory");
    state.mmu_enabled = false;
    log_write(LOG_LEVEL_WARN, "mmu: disabled");
}

bool mmu_pac_disable(void)
{
    u64 sctlr;
    __asm__ volatile("mrs %0, sctlr_el1" : "=r"(sctlr));
    sctlr &= ~(MMU_SCTLR_EnIA | MMU_SCTLR_EnIB | MMU_SCTLR_EnDA | MMU_SCTLR_EnDB);
    __asm__ volatile("msr sctlr_el1, %0" : : "r"(sctlr) : "memory");
    __asm__ volatile("isb" ::: "memory");
    state.sctlr_el1 = sctlr;
    state.pac_state = MMU_PAC_STATE_DISABLED;
    log_write(LOG_LEVEL_WARN, "mmu: PAC disabled (EnIA/EnIB/EnDA/EnDB cleared)");
    return true;
}

bool mmu_pac_strip_all(void)
{
    u64 sctlr;
    __asm__ volatile("mrs %0, sctlr_el1" : "=r"(sctlr));
    sctlr &= ~(MMU_SCTLR_EnIA | MMU_SCTLR_EnIB);
    sctlr &= ~(MMU_SCTLR_EnDA | MMU_SCTLR_EnDB);
    __asm__ volatile("msr sctlr_el1, %0" : : "r"(sctlr) : "memory");
    __asm__ volatile("isb" ::: "memory");
    state.sctlr_el1 = sctlr;
    state.pac_state = MMU_PAC_STATE_BYPASSED;
    log_write(LOG_LEVEL_WARN, "mmu: PAC stripped (all pointer auth disabled)");
    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE, "pac-bypass", 1U, 0U);
    return true;
}

bool mmu_aprr_bypass(void)
{
    u64 tcr;
    __asm__ volatile("mrs %0, tcr_el1" : "=r"(tcr));
    tcr |= MMU_TCR_NFD0 | MMU_TCR_NFD1;
    tcr &= ~(MMU_TCR_HA | MMU_TCR_HD);
    __asm__ volatile("msr tcr_el1, %0" : : "r"(tcr) : "memory");
    __asm__ volatile("isb" ::: "memory");
    state.tcr_el1 = tcr;
    state.aprr_state = MMU_APRR_STATE_BYPASSED;
    log_write(LOG_LEVEL_WARN, "mmu: APRR/PPL bypassed (NFD set, HA/HD cleared)");
    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE, "aprr-bypass", 1U, 0U);
    return true;
}

bool mmu_wxn_disable(void)
{
    u64 sctlr;
    __asm__ volatile("mrs %0, sctlr_el1" : "=r"(sctlr));
    sctlr &= ~MMU_SCTLR_WXN;
    __asm__ volatile("msr sctlr_el1, %0" : : "r"(sctlr) : "memory");
    __asm__ volatile("isb" ::: "memory");
    state.sctlr_el1 = sctlr;
    log_write(LOG_LEVEL_WARN, "mmu: W^X disabled (SCTLR_EL1.WXN cleared)");
    return true;
}

bool mmu_configure_tcr(u64 tcr_bits)
{
    __asm__ volatile("msr tcr_el1, %0" : : "r"(tcr_bits) : "memory");
    __asm__ volatile("isb" ::: "memory");
    state.tcr_el1 = tcr_bits;
    return true;
}

bool mmu_configure_mair(u64 mair_value)
{
    __asm__ volatile("msr mair_el1, %0" : : "r"(mair_value) : "memory");
    __asm__ volatile("isb" ::: "memory");
    state.mair_el1 = mair_value;
    return true;
}

bool mmu_write_ttbr0(u64 ttbr0)
{
    __asm__ volatile("msr ttbr0_el1, %0" : : "r"(ttbr0) : "memory");
    __asm__ volatile("isb" ::: "memory");
    state.ttbr0 = ttbr0;
    return true;
}

bool mmu_write_ttbr1(u64 ttbr1)
{
    __asm__ volatile("msr ttbr1_el1, %0" : : "r"(ttbr1) : "memory");
    __asm__ volatile("isb" ::: "memory");
    state.ttbr1 = ttbr1;
    return true;
}

void mmu_read_cpu_config(mmu_config_t *config)
{
    if (config == NULL) return;
    __asm__ volatile("mrs %0, ttbr0_el1" : "=r"(config->ttbr0_el1));
    __asm__ volatile("mrs %0, ttbr1_el1" : "=r"(config->ttbr1_el1));
    __asm__ volatile("mrs %0, tcr_el1" : "=r"(config->tcr_el1));
    __asm__ volatile("mrs %0, mair_el1" : "=r"(config->mair_el1));
    __asm__ volatile("mrs %0, sctlr_el1" : "=r"(config->sctlr_el1));
}

bool mmu_map_range(u64 virt, u64 phys, u64 size, u64 attrs)
{
    if (state.ttbr0 == 0U) return false;
    u64 *root = (u64 *)(usize)state.ttbr0;
    return setup_level0_table(root, virt, phys, size, attrs);
}

static void unmap_level0_table(u64 *root, u64 virt, u64 size)
{
    static const u64 BLOCK_L0 = 1ULL << 39;
    static const u64 BLOCK_L1 = 1ULL << 30;
    static const u64 BLOCK_L2 = 1ULL << 21;
    static const u64 PAGE =      1ULL << 12;
    u64 end = virt + size;

    for (u64 va = virt; va < end;) {
        u64 l0_idx = (va >> 39) & 0x1FFU;
        u64 l0_entry = root[l0_idx];
        u64 l0_end = ((va + BLOCK_L0) & ~(BLOCK_L0 - 1U));
        if (l0_end > end) l0_end = end;

        if ((l0_entry & MMU_PTE_TYPE_MASK) == MMU_PTE_TYPE_FAULT) {
            va = l0_end;
            continue;
        }
        if ((l0_entry & MMU_PTE_TYPE_MASK) == MMU_PTE_TYPE_BLOCK) {
            if (va <= l0_end) {
                root[l0_idx] = 0U;
                va = l0_end;
                continue;
            }
        }

        u64 *l1 = (u64 *)(usize)(l0_entry & ~0xFFFULL);
        for (; va < l0_end;) {
            u64 l1_idx = (va >> 30) & 0x1FFU;
            u64 l1_entry = l1[l1_idx];
            u64 l1_end = ((va + BLOCK_L1) & ~(BLOCK_L1 - 1U));
            if (l1_end > end) l1_end = end;
            if (l1_end > l0_end) l1_end = l0_end;

            if ((l1_entry & MMU_PTE_TYPE_MASK) == MMU_PTE_TYPE_FAULT) {
                va = l1_end;
                continue;
            }
            if ((l1_entry & MMU_PTE_TYPE_MASK) == MMU_PTE_TYPE_BLOCK) {
                l1[l1_idx] = 0U;
                va = l1_end;
                continue;
            }

            u64 *l2 = (u64 *)(usize)(l1_entry & ~0xFFFULL);
            for (; va < l1_end;) {
                u64 l2_idx = (va >> 21) & 0x1FFU;
                u64 l2_entry = l2[l2_idx];
                u64 l2_end = ((va + BLOCK_L2) & ~(BLOCK_L2 - 1U));
                if (l2_end > end) l2_end = end;
                if (l2_end > l1_end) l2_end = l1_end;

                if ((l2_entry & MMU_PTE_TYPE_MASK) == MMU_PTE_TYPE_FAULT) {
                    va = l2_end;
                    continue;
                }
                if ((l2_entry & MMU_PTE_TYPE_MASK) == MMU_PTE_TYPE_BLOCK) {
                    l2[l2_idx] = 0U;
                    va = l2_end;
                    continue;
                }

                u64 *l3 = (u64 *)(usize)(l2_entry & ~0xFFFULL);
                for (; va < l2_end;) {
                    u64 l3_idx = (va >> 12) & 0x1FFU;
                    l3[l3_idx] = 0U;
                    va += PAGE;
                }
            }
        }
    }
}

bool mmu_unmap_range(u64 virt, u64 size)
{
    if (state.ttbr0 == 0U) return false;
    u64 *root = (u64 *)(usize)state.ttbr0;
    unmap_level0_table(root, virt, size);
    return true;
}

bool mmu_init(void)
{
    fm_memset(&state, 0, sizeof(state));
    mmu_read_cpu_config(NULL);
    mmu_config_t config;
    mmu_read_cpu_config(&config);
    state.ttbr0 = config.ttbr0_el1;
    state.ttbr1 = config.ttbr1_el1;
    state.tcr_el1 = config.tcr_el1;
    state.mair_el1 = config.mair_el1;
    state.sctlr_el1 = config.sctlr_el1;
    state.mmu_enabled = (config.sctlr_el1 & MMU_SCTLR_M) != 0U;
    state.initialized = true;
    log_write(LOG_LEVEL_INFO, "mmu: init complete (mmu_enabled=%d)", state.mmu_enabled);
    return true;
}

void mmu_shutdown(void)
{
    fm_memset(&state, 0, sizeof(state));
    state.initialized = false;
}

bool mmu_ready(void)
{
    return state.initialized;
}

bool mmu_healthy(void)
{
    return state.initialized;
}

mmu_status_t mmu_get_status(void)
{
    return state;
}

bool mmu_is_virtual_address(u64 addr)
{
    return (addr >= 0xFFFFFFF000000000ULL) || (addr < 0x800000000ULL);
}

u64 mmu_phys_to_virt(u64 phys)
{
    if (phys >= 0x800000000ULL && phys < 0x1000000000ULL) {
        return phys;
    }
    return phys;
}

u64 mmu_virt_to_phys(u64 virt)
{
    if (virt >= 0xFFFFFFF000000000ULL && virt < 0xFFFFFFF800000000ULL) {
        return virt - 0xFFFFFFF000000000ULL + 0x800000000ULL;
    }
    return virt;
}
