#include "fbr34ker/architecture.h"
#include "fbr34ker/board.h"
#include "fbr34ker/device_tree.h"
#include "fbr34ker/driver.h"
#include "fbr34ker/event.h"
#include "fbr34ker/lifecycle.h"
#include "fbr34ker/mmio.h"
#include "fbr34ker/physical_memory.h"
#include "fbr34ker/platform.h"
#include "fbr34ker/service_registry.h"
#include "fbr34ker/trace.h"

static const memory_region_t regions[] = {
    {.base=0x40000000ULL,.size=0x1000000ULL,.type=MEMORY_REGION_USABLE,.name="ram"},
    {.base=0x08000000ULL,.size=0x1000000ULL,.type=MEMORY_REGION_MMIO,.name="gic"},
};

bool hardware_probe_immutable(void) { return false; }
const char *platform_name(void) { return "QEMU virt (AArch64)"; }
const char *platform_console_transport_name(void) { return "test-console"; }
const char *platform_interrupt_controller_name(void) { return "test-gic"; }
u64 platform_features(void)
{
    return PLATFORM_FEATURE_CONSOLE_OUTPUT | PLATFORM_FEATURE_CONSOLE_INPUT |
           PLATFORM_FEATURE_TIMER | PLATFORM_FEATURE_INTERRUPTS |
           PLATFORM_FEATURE_FRAMEBUFFER | PLATFORM_FEATURE_WATCHDOG_CONFIGURE |
           PLATFORM_FEATURE_POWER;
}
u64 platform_memory_regions(const memory_region_t **out) { if (out) *out=regions; return ARRAY_COUNT(regions); }
u64 timer_frequency(void) { return 24000000ULL; }
bool device_tree_valid(void) { return false; }
usize device_tree_size(void) { return 0U; }
u32 device_tree_reservation_count(void) { return 0U; }
bool device_tree_reservation_at(u32 i,u64 *a,u64 *z){UNUSED(i);UNUSED(a);UNUSED(z);return false;}
bool device_tree_get_string(const char *p,const char *n,char *o,usize c){UNUSED(p);UNUSED(n);UNUSED(o);UNUSED(c);return false;}
bool device_tree_string_list_contains(const char *p,const char *n,const char *v){UNUSED(p);UNUSED(n);UNUSED(v);return false;}
bool device_tree_find_compatible_path(const char *c,char *o,usize z){UNUSED(c);UNUSED(o);UNUSED(z);return false;}
bool device_tree_get_reg(const char *p,u32 i,device_tree_reg_t *r){UNUSED(p);UNUSED(i);UNUSED(r);return false;}
bool device_tree_get_clock_frequency(const char *p,u64 *f){UNUSED(p);UNUSED(f);return false;}
bool device_tree_get_cells(const char *p,const char *n,u32 *v,u32 c,u32 *count){UNUSED(p);UNUSED(n);UNUSED(v);UNUSED(c);UNUSED(count);return false;}

int main(void)
{
    if (!architecture_init() || !architecture_healthy()) return 1;
    if (lifecycle_component_count() != 10U || service_registry_count() != 8U ||
        driver_count() != 8U) return 2;
    if (!board_healthy() || !mmio_healthy() || !physical_memory_healthy()) return 3;
    if (!service_registry_service_ready("console.output") ||
        !service_registry_service_compatible("watchdog", 1U,
                                             PLATFORM_FEATURE_WATCHDOG_CONFIGURE)) return 4;
    if (event_bus_count() == 0U || trace_count() == 0U) return 5;
    architecture_shutdown();
    if (architecture_ready() || lifecycle_provided_capabilities() != 0U) return 6;
    if (!architecture_restart() || !architecture_healthy()) return 7;
    return 0;
}
