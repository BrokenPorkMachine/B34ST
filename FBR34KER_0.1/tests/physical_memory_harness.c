#include "fbr34ker/device_tree.h"
#include "fbr34ker/physical_memory.h"
#include "fbr34ker/platform.h"
#include "fbr34ker/types.h"

static const memory_region_t regions[] = {
    {.base=0x100000ULL,.size=0x100000ULL,.type=MEMORY_REGION_USABLE,.name="ram-a"},
    {.base=0x300000ULL,.size=0x100000ULL,.type=MEMORY_REGION_USABLE,.name="ram-b"},
    {.base=0x180000ULL,.size=0x20000ULL,.type=MEMORY_REGION_MONITOR,.name="monitor"},
};
u64 platform_memory_regions(const memory_region_t **out){if(out)*out=regions;return ARRAY_COUNT(regions);}
bool device_tree_valid(void){return true;}
u32 device_tree_reservation_count(void){return 1U;}
bool device_tree_reservation_at(u32 index,u64 *base,u64 *size){if(index!=0U||!base||!size)return false;*base=0x320000ULL;*size=0x10000ULL;return true;}

int main(void)
{
    physical_memory_init();
    if (!physical_memory_healthy()) return 1;
    fbr34ker_pmm_stats_t stats=physical_memory_stats();
    if (stats.usable_ranges!=2U || stats.reserved_ranges!=2U) return 2;
    u64 first=0U, second=0U;
    if (!physical_memory_allocate_pages(8U,8U,"first",&first) || (first & 0x7fffU)!=0U) return 3;
    if (!physical_memory_allocate_pages(16U,1U,"second",&second) || second==first) return 4;
    if (!physical_memory_free_pages(first,8U)) return 5;
    if (physical_memory_free_pages(first,8U)) return 6;
    return physical_memory_healthy()?0:7;
}
