#pragma once
#include "fbr34ker/types.h"

typedef enum {
    GIC_KIND_NONE = 0,
    GIC_KIND_V2 = 2,
    GIC_KIND_V3 = 3,
} gic_kind_t;

typedef struct {
    gic_kind_t kind;
    u64 distributor_base;
    u64 cpu_or_redistributor_base;
    u32 interrupt_count;
    bool initialized;
} gic_info_t;

bool gic_initialize_v2(u64 distributor_base, u64 cpu_base);
bool gic_initialize_v3(u64 distributor_base, u64 redistributor_base);
bool gic_initialize_from_fdt(void);
bool gic_available(void);
u32 gic_acknowledge(void);
void gic_complete(u32 interrupt_id);
bool gic_set_enabled(u32 interrupt_id, bool enabled);
bool gic_self_test(void);
gic_info_t gic_info(void);
const char *gic_kind_name(gic_kind_t kind);
