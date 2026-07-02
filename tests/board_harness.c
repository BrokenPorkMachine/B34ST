#include "fbr34ker/board.h"
#include "fbr34ker/device_tree.h"
#include "fbr34ker/platform.h"
#include "fbr34ker/types.h"

// SPDX-License-Identifier: BSD-2-Clause
static const memory_region_t regions[] = {
    {.base=0x40000000ULL,.size=0x10000000ULL,.type=MEMORY_REGION_USABLE,.name="ram"},
    {.base=0x08000000ULL,.size=0x01000000ULL,.type=MEMORY_REGION_MMIO,.name="gic"},
};

const char *platform_name(void) { return "QEMU virt (AArch64)"; }
u64 platform_features(void) { return PLATFORM_FEATURE_CONSOLE_OUTPUT | PLATFORM_FEATURE_TIMER | PLATFORM_FEATURE_INTERRUPTS; }
u64 platform_memory_regions(const memory_region_t **out) { if (out) *out=regions; return ARRAY_COUNT(regions); }
bool device_tree_valid(void) { return false; }
bool device_tree_get_string(const char *p,const char *n,char *o,usize c){UNUSED(p);UNUSED(n);UNUSED(o);UNUSED(c);return false;}
bool device_tree_string_list_contains(const char *p,const char *n,const char *v){UNUSED(p);UNUSED(n);UNUSED(v);return false;}
bool device_tree_find_compatible_path(const char *c,char *o,usize z){UNUSED(c);UNUSED(o);UNUSED(z);return false;}
bool device_tree_get_reg(const char *p,u32 i,device_tree_reg_t *r){UNUSED(p);UNUSED(i);UNUSED(r);return false;}
bool device_tree_get_clock_frequency(const char *p,u64 *f){UNUSED(p);UNUSED(f);return false;}
bool device_tree_get_cells(const char *p,const char *n,u32 *v,u32 c,u32 *count){UNUSED(p);UNUSED(n);UNUSED(v);UNUSED(c);UNUSED(count);return false;}

int main(void)
{
    if (!board_init() || !board_healthy()) return 1;
    const fbr34ker_board_descriptor_t *board = board_active();
    if (board == NULL || board->device_count != 4U ||
        board->memory_base != 0x40000000ULL ||
        board_find_device(FBR34KER_DEVICE_UART,0U) == NULL) return 2;
    char json[4096];
    if (board_export_json(json,sizeof(json)) == 0U || json[0] != '{') return 3;
    board_shutdown();
    return board_ready() ? 4 : 0;
}
