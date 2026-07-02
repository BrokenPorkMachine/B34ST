#include "fbr34ker/gic.h"
#include "fbr34ker/device_tree.h"
#include "fbr34ker/platform.h"

#define GICD_CTLR 0x0000U
#define GICD_TYPER 0x0004U
#define GICD_ISENABLER 0x0100U
#define GICD_ICENABLER 0x0180U
#define GICC_CTLR 0x0000U
#define GICC_PMR 0x0004U
#define GICC_IAR 0x000cU
#define GICC_EOIR 0x0010U
#define GIC_SPURIOUS_MIN 1020U

// SPDX-License-Identifier: BSD-2-Clause
static gic_info_t active;

static volatile u32 *reg32(u64 base, u32 offset)
{
    return (volatile u32 *)(usize)(base + offset);
}

static u32 read32(u64 base, u32 offset)
{
    return *reg32(base, offset);
}

static void write32(u64 base, u32 offset, u32 value)
{
    *reg32(base, offset) = value;
}

static u32 typer_interrupt_count(u64 distributor_base)
{
    const u32 lines = read32(distributor_base, GICD_TYPER) & 0x1fU;
    const u32 count = (lines + 1U) * 32U;
    return count > 1020U ? 1020U : count;
}

bool gic_initialize_v2(u64 distributor_base, u64 cpu_base)
{
    if ((distributor_base & 3U) != 0U || (cpu_base & 3U) != 0U ||
        distributor_base == 0U || cpu_base == 0U) {
        return false;
    }
    active = (gic_info_t){
        .kind = GIC_KIND_V2,
        .distributor_base = distributor_base,
        .cpu_or_redistributor_base = cpu_base,
        .interrupt_count = typer_interrupt_count(distributor_base),
        .initialized = true,
    };
    write32(distributor_base, GICD_CTLR, 1U);
    write32(cpu_base, GICC_PMR, 0xffU);
    write32(cpu_base, GICC_CTLR, 1U);
    __asm__ volatile("dsb sy\nisb" ::: "memory");
    return true;
}

bool gic_initialize_v3(u64 distributor_base, u64 redistributor_base)
{
    if ((distributor_base & 3U) != 0U || distributor_base == 0U) {
        return false;
    }
    u64 sre;
    __asm__ volatile("mrs %0, ICC_SRE_EL1" : "=r"(sre));
    sre |= 1U;
    __asm__ volatile("msr ICC_SRE_EL1, %0\nisb" :: "r"(sre) : "memory");
    __asm__ volatile("msr ICC_PMR_EL1, %0" :: "r"((u64)0xffU) : "memory");
    __asm__ volatile("msr ICC_IGRPEN1_EL1, %0\nisb" :: "r"((u64)1U) : "memory");
    write32(distributor_base, GICD_CTLR, (1U << 4U) | (1U << 1U));
    __asm__ volatile("dsb sy\nisb" ::: "memory");
    active = (gic_info_t){
        .kind = GIC_KIND_V3,
        .distributor_base = distributor_base,
        .cpu_or_redistributor_base = redistributor_base,
        .interrupt_count = typer_interrupt_count(distributor_base),
        .initialized = true,
    };
    return true;
}

bool gic_initialize_from_fdt(void)
{
    char path[DEVICE_TREE_MAX_STRING];
    device_tree_reg_t distributor;
    device_tree_reg_t second;
    if (device_tree_find_compatible_path("arm,gic-v3", path, sizeof(path)) &&
        device_tree_get_reg(path, 0U, &distributor)) {
        const u64 redist = device_tree_get_reg(path, 1U, &second)
            ? second.address : 0U;
        return gic_initialize_v3(distributor.address, redist);
    }
    static const char *const v2_compatibles[] = {
        "arm,cortex-a15-gic", "arm,cortex-a7-gic", "arm,gic-400"
    };
    for (usize index = 0U; index < ARRAY_COUNT(v2_compatibles); ++index) {
        if (device_tree_find_compatible_path(v2_compatibles[index], path,
                                             sizeof(path)) &&
            device_tree_get_reg(path, 0U, &distributor) &&
            device_tree_get_reg(path, 1U, &second)) {
            return gic_initialize_v2(distributor.address, second.address);
        }
    }
    return false;
}

bool gic_available(void)
{
    return active.initialized;
}

u32 gic_acknowledge(void)
{
    if (!active.initialized) return PLATFORM_INTERRUPT_SPURIOUS;
    u32 id;
    if (active.kind == GIC_KIND_V2) {
        id = read32(active.cpu_or_redistributor_base, GICC_IAR) & 0x3ffU;
    } else {
        u64 value;
        __asm__ volatile("mrs %0, ICC_IAR1_EL1" : "=r"(value));
        id = (u32)(value & 0xffffffU);
    }
    return id >= GIC_SPURIOUS_MIN ? PLATFORM_INTERRUPT_SPURIOUS : id;
}

void gic_complete(u32 interrupt_id)
{
    if (!active.initialized || interrupt_id == PLATFORM_INTERRUPT_SPURIOUS) return;
    if (active.kind == GIC_KIND_V2) {
        write32(active.cpu_or_redistributor_base, GICC_EOIR, interrupt_id);
    } else {
        __asm__ volatile("msr ICC_EOIR1_EL1, %0" :: "r"((u64)interrupt_id) : "memory");
    }
    __asm__ volatile("isb" ::: "memory");
}

bool gic_set_enabled(u32 interrupt_id, bool enabled)
{
    if (!active.initialized || interrupt_id >= active.interrupt_count ||
        interrupt_id >= GIC_SPURIOUS_MIN) {
        return false;
    }
    /* GICv3 SGI/PPI enable registers live in the redistributor. Keep this
       compact driver conservative and support distributor SPIs only. */
    if (active.kind == GIC_KIND_V3 && interrupt_id < 32U) {
        return false;
    }
    const u32 offset = (enabled ? GICD_ISENABLER : GICD_ICENABLER) +
                       (interrupt_id / 32U) * 4U;
    write32(active.distributor_base, offset, 1U << (interrupt_id % 32U));
    __asm__ volatile("dsb sy" ::: "memory");
    return true;
}

bool gic_self_test(void)
{
    if (!active.initialized || active.interrupt_count <= 32U) return false;
    /* Exercise a reversible distributor write without enabling CPU delivery. */
    const u32 probe = active.interrupt_count - 1U;
    return gic_set_enabled(probe, true) && gic_set_enabled(probe, false);
}

gic_info_t gic_info(void)
{
    return active;
}

const char *gic_kind_name(gic_kind_t kind)
{
    switch (kind) {
    case GIC_KIND_NONE: return "none";
    case GIC_KIND_V2: return "GICv2";
    case GIC_KIND_V3: return "GICv3";
    default: return "none";
    }
}
