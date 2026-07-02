#include <stddef.h>
#include <stdint.h>
#include "fbr34ker/physical_validation.h"

// SPDX-License-Identifier: BSD-2-Clause
_Static_assert(offsetof(fbr34ker_physical_validation_claim_t, size) == 0,
               "size offset drift");
_Static_assert(offsetof(fbr34ker_physical_validation_claim_t, evidence_flags) == 8,
               "evidence flags offset drift");
_Static_assert(offsetof(fbr34ker_physical_validation_claim_t, session_id_hi) == 16,
               "session id offset drift");

int main(void) {
    fbr34ker_physical_validation_claim_t claim = {
        .size = sizeof(fbr34ker_physical_validation_claim_t),
        .schema_version = FBR34KER_PHYSICAL_VALIDATION_SCHEMA_VERSION,
        .evidence_flags = FBR34KER_VALIDATION_EVIDENCE_BUNDLE_INTEGRITY |
                          FBR34KER_VALIDATION_EVIDENCE_CONSOLE_ENTRY,
        .maturity = FBR34KER_VALIDATION_MATURITY_CONSOLE_VERIFIED,
        .session_id_hi = UINT64_C(0x1122334455667788),
        .session_id_lo = UINT64_C(0x99aabbccddeeff00),
    };
    return claim.schema_version == 1U && claim.size == 32U ? 0 : 1;
}
