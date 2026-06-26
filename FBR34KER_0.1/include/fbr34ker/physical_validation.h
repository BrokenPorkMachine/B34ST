#pragma once

#include <stdint.h>

#define FBR34KER_PHYSICAL_VALIDATION_SCHEMA_VERSION 1U

#define FBR34KER_VALIDATION_EVIDENCE_BUNDLE_INTEGRITY (1U << 0)
#define FBR34KER_VALIDATION_EVIDENCE_EXACT_PROFILE    (1U << 1)
#define FBR34KER_VALIDATION_EVIDENCE_CONSOLE_ENTRY    (1U << 2)
#define FBR34KER_VALIDATION_EVIDENCE_BOOT_RECORD      (1U << 3)
#define FBR34KER_VALIDATION_EVIDENCE_SAFE_RESET       (1U << 4)
#define FBR34KER_VALIDATION_EVIDENCE_QEMU_RUNTIME     (1U << 5)
#define FBR34KER_VALIDATION_EVIDENCE_PHYSICAL_RUNTIME (1U << 6)

typedef enum {
    FBR34KER_VALIDATION_MATURITY_SIMULATED = 0,
    FBR34KER_VALIDATION_MATURITY_QEMU_VERIFIED = 1,
    FBR34KER_VALIDATION_MATURITY_BRIDGE_VERIFIED = 2,
    FBR34KER_VALIDATION_MATURITY_CONSOLE_VERIFIED = 3,
    FBR34KER_VALIDATION_MATURITY_BOOT_EVIDENCE_VERIFIED = 4,
    FBR34KER_VALIDATION_MATURITY_PHYSICAL_RUNTIME_VERIFIED = 5,
} fbr34ker_validation_maturity_t;

typedef struct {
    uint32_t size;
    uint32_t schema_version;
    uint32_t evidence_flags;
    uint32_t maturity;
    uint64_t session_id_hi;
    uint64_t session_id_lo;
} fbr34ker_physical_validation_claim_t;

_Static_assert(sizeof(fbr34ker_physical_validation_claim_t) == 32,
               "physical validation claim ABI drift");
