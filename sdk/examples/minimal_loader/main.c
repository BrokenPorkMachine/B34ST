#include "fbr34ker_sdk.h"
#include <stdio.h>
// SPDX-License-Identifier: BSD-2-Clause
int main(void) {
    fbr34ker_handoff_builder_t b; const fbr34ker_handoff_t *h = NULL;
    fbr34ker_handoff_builder_init(&b, 0x80000000ULL, 0x00800000ULL);
    if (fbr34ker_handoff_builder_add_region(&b, 0x80000000ULL, 0x00800000ULL,
        FBR34KER_HANDOFF_REGION_MONITOR, FBR34KER_REGION_ATTR_READ|FBR34KER_REGION_ATTR_WRITE|FBR34KER_REGION_ATTR_EXECUTE) != FBR34KER_SDK_OK) return 1;
    if (fbr34ker_handoff_builder_finalize(&b, &h) != FBR34KER_SDK_OK) return 2;
    printf("handoff-v%u size=%u\n", h->version, h->structure_size); return 0;
}
