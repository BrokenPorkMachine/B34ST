#pragma once
#include "fbr34ker/types.h"

#define FBR34KER_ARCH_CAP_TRACE (1ULL << 0)
#define FBR34KER_ARCH_CAP_EVENT_BUS (1ULL << 1)
#define FBR34KER_ARCH_CAP_SERVICE_REGISTRY (1ULL << 2)
#define FBR34KER_ARCH_CAP_DRIVER_MANAGER (1ULL << 3)
#define FBR34KER_ARCH_CAP_PLATFORM_CATALOG (1ULL << 4)
#define FBR34KER_ARCH_CAP_BOARD_DESCRIPTION (1ULL << 5)
#define FBR34KER_ARCH_CAP_MMIO_MANAGER (1ULL << 6)
#define FBR34KER_ARCH_CAP_PHYSICAL_MEMORY (1ULL << 7)
#define FBR34KER_ARCH_CAP_BRINGUP_REPORT (1ULL << 8)

bool architecture_init(void);
void architecture_shutdown(void);
bool architecture_restart(void);
bool architecture_ready(void);
bool architecture_healthy(void);
