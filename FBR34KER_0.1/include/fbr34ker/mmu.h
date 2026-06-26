#pragma once
#include "fbr34ker/types.h"

#define MMU_PAGE_SIZE 4096U
#define MMU_TABLE_ENTRIES 512U

#define MMU_TCR_T0SZ_48 16U
#define MMU_TCR_T1SZ_48 16U
#define MMU_TCR_TG0_4K (0ULL << 14)
#define MMU_TCR_TG1_4K (2ULL << 30)
#define MMU_TCR_IPS_4TB (3ULL << 32)
#define MMU_TCR_IPS_64TB (4ULL << 32)
#define MMU_TCR_IPS_4PB (5ULL << 32)
#define MMU_TCR_HA (1ULL << 39)
#define MMU_TCR_HD (1ULL << 40)
#define MMU_TCR_NFD0 (1ULL << 37)
#define MMU_TCR_NFD1 (1ULL << 38)

#define MMU_MAIR_DEVICE_nGnRE 0x04ULL
#define MMU_MAIR_NORMAL_NC 0x44ULL
#define MMU_MAIR_NORMAL_WB 0xFFULL
#define MMU_MAIR_INDX_DEVICE_nGnRE 0
#define MMU_MAIR_INDX_NORMAL_NC 1
#define MMU_MAIR_INDX_NORMAL_WB 2
#define MMU_MAIR_VALUE (MMU_MAIR_DEVICE_nGnRE | (MMU_MAIR_NORMAL_NC << 8) | (MMU_MAIR_NORMAL_WB << 16))

#define MMU_SCTLR_M (1ULL << 0)
#define MMU_SCTLR_A (1ULL << 1)
#define MMU_SCTLR_C (1ULL << 2)
#define MMU_SCTLR_SA (1ULL << 3)
#define MMU_SCTLR_I (1ULL << 12)
#define MMU_SCTLR_WXN (1ULL << 19)
#define MMU_SCTLR_EE (1ULL << 25)
#define MMU_SCTLR_EnIA (1ULL << 31)
#define MMU_SCTLR_EnIB (1ULL << 30)
#define MMU_SCTLR_EnDA (1ULL << 27)
#define MMU_SCTLR_EnDB (1ULL << 28)

#define MMU_PTE_TYPE_MASK 3ULL
#define MMU_PTE_TYPE_FAULT 0ULL
#define MMU_PTE_TYPE_TABLE 3ULL
#define MMU_PTE_TYPE_PAGE 3ULL
#define MMU_PTE_TYPE_BLOCK 1ULL

#define MMU_PTE_ATTR_ACCESS (1ULL << 10)
#define MMU_PTE_ATTR_NG (1ULL << 11)
#define MMU_PTE_ATTR_AF (1ULL << 10)
#define MMU_PTE_ATTR_SH_INNER (3ULL << 8)
#define MMU_PTE_ATTR_SH_OUTER (2ULL << 8)
#define MMU_PTE_ATTR_AP_RW_EL1 (0ULL << 6)
#define MMU_PTE_ATTR_AP_RO_EL1 (2ULL << 6)
#define MMU_PTE_ATTR_AP_RW_ALL (1ULL << 6)
#define MMU_PTE_ATTR_AP_RO_ALL (3ULL << 6)
#define MMU_PTE_ATTR_UXN (1ULL << 54)
#define MMU_PTE_ATTR_PXN (1ULL << 53)
#define MMU_PTE_ATTR_NSTABLE (1ULL << 63)
#define MMU_PTE_ATTR_NS (1ULL << 5)

#define MMU_PTE_ATTR_MAIR_INDX(n) ((u64)(n) << 2)
#define MMU_PTE_ATTR_NORMAL_WB MMU_PTE_ATTR_MAIR_INDX(MMU_MAIR_INDX_NORMAL_WB)
#define MMU_PTE_ATTR_NORMAL_NC MMU_PTE_ATTR_MAIR_INDX(MMU_MAIR_INDX_NORMAL_NC)
#define MMU_PTE_ATTR_DEVICE_NG MMU_PTE_ATTR_MAIR_INDX(MMU_MAIR_INDX_DEVICE_nGnRE)

#define MMU_PTE_PERM_RW (MMU_PTE_ATTR_AF | MMU_PTE_ATTR_AP_RW_EL1 | MMU_PTE_ATTR_PXN | MMU_PTE_ATTR_UXN)
#define MMU_PTE_PERM_RX (MMU_PTE_ATTR_AF | MMU_PTE_ATTR_AP_RO_EL1)
#define MMU_PTE_PERM_RWX (MMU_PTE_ATTR_AF | MMU_PTE_ATTR_AP_RW_EL1)

#define MMU_BLOCK_DESCRIPTOR(addr, attr) ((addr) | (attr) | MMU_PTE_TYPE_BLOCK)
#define MMU_PAGE_DESCRIPTOR(addr, attr) ((addr) | (attr) | MMU_PTE_TYPE_PAGE)
#define MMU_TABLE_DESCRIPTOR(addr) ((addr) | MMU_PTE_TYPE_TABLE)

typedef struct {
    u64 ttbr0_el1;
    u64 ttbr1_el1;
    u64 tcr_el1;
    u64 mair_el1;
    u64 sctlr_el1;
} mmu_config_t;

typedef enum {
    MMU_APRR_STATE_DEFAULT = 0,
    MMU_APRR_STATE_BYPASSED = 1,
    MMU_APRR_STATE_CONFIGURED = 2,
} mmu_aprr_state_t;

typedef enum {
    MMU_PAC_STATE_DEFAULT = 0,
    MMU_PAC_STATE_DISABLED = 1,
    MMU_PAC_STATE_BYPASSED = 2,
} mmu_pac_state_t;

typedef struct {
    bool mmu_enabled;
    bool initialized;
    mmu_aprr_state_t aprr_state;
    mmu_pac_state_t pac_state;
    u64 ttbr0;
    u64 ttbr1;
    u64 tcr_el1;
    u64 mair_el1;
    u64 sctlr_el1;
    u64 page_table_pool;
    usize page_table_pool_size;
} mmu_status_t;

bool mmu_init(void);
void mmu_shutdown(void);
bool mmu_ready(void);
bool mmu_healthy(void);
mmu_status_t mmu_get_status(void);

bool mmu_setup_identity_map(u64 phys_base, u64 size);
bool mmu_enable(void);
void mmu_disable(void);

bool mmu_pac_disable(void);
bool mmu_pac_strip_all(void);
bool mmu_aprr_bypass(void);
bool mmu_wxn_disable(void);

bool mmu_configure_tcr(u64 tcr_bits);
bool mmu_configure_mair(u64 mair_value);
bool mmu_write_ttbr0(u64 ttbr0);
bool mmu_write_ttbr1(u64 ttbr1);

void mmu_read_cpu_config(mmu_config_t *config);
bool mmu_map_range(u64 virt, u64 phys, u64 size, u64 attrs);
bool mmu_unmap_range(u64 virt, u64 size);

bool mmu_allocate_page_table_pool(u64 base, usize size);
bool mmu_is_virtual_address(u64 addr);
u64 mmu_phys_to_virt(u64 phys);
u64 mmu_virt_to_phys(u64 virt);
