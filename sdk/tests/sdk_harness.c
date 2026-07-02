#include "fbr34ker_sdk.h"
#include <assert.h>
#include <stdio.h>

// SPDX-License-Identifier: BSD-2-Clause
static uint32_t irq_ack(void *context) { (void)context; return 0U; }
static void irq_complete(uint32_t value, void *context) { (void)value; (void)context; }
static bool irq_enabled(uint32_t value, bool enabled, void *context) {
    (void)value; (void)enabled; (void)context; return true;
}

int main(void) {
    fbr34ker_handoff_builder_t b;
    const fbr34ker_handoff_t *h = NULL;
    fbr34ker_handoff_builder_init(&b, 0x80000000ULL, 0x200000ULL);
    assert(fbr34ker_handoff_builder_add_region(&b, 0x80000000ULL, 0x200000ULL,
        FBR34KER_HANDOFF_REGION_MONITOR,
        FBR34KER_REGION_ATTR_READ | FBR34KER_REGION_ATTR_WRITE |
        FBR34KER_REGION_ATTR_EXECUTE) == FBR34KER_SDK_OK);
    assert(fbr34ker_handoff_builder_add_region(&b, 0x80200000ULL, 0x200000ULL,
        FBR34KER_HANDOFF_REGION_USABLE,
        FBR34KER_REGION_ATTR_READ | FBR34KER_REGION_ATTR_WRITE) == FBR34KER_SDK_OK);
    assert(fbr34ker_handoff_builder_finalize(&b, &h) == FBR34KER_SDK_OK);
    assert(fbr34ker_handoff_validate_sdk(h) == FBR34KER_SDK_OK);
    assert(sizeof(*h) == 284U);

    b.handoff.flags |= FBR34KER_HANDOFF_FLAG_TIMER_VALID;
    assert(fbr34ker_handoff_validate_sdk(&b.handoff) == FBR34KER_SDK_ERR_CALLBACK);
    b.handoff.flags &= ~FBR34KER_HANDOFF_FLAG_TIMER_VALID;

    fbr34ker_platform_services_t services = {0};
    services.version = FBR34KER_PLATFORM_SERVICES_VERSION_1;
    services.structure_size = (uint32_t)sizeof(services);
    services.capabilities = FBR34KER_SERVICE_INTERRUPT_CONTROLLER;
    services.interrupt_ack = irq_ack;
    fbr34ker_handoff_builder_set_services(&b, &services);
    assert(fbr34ker_handoff_validate_sdk(&b.handoff) == FBR34KER_SDK_ERR_CALLBACK);
    services.interrupt_complete = irq_complete;
    services.interrupt_set_enabled = irq_enabled;
    fbr34ker_handoff_builder_set_services(&b, &services);
    assert(fbr34ker_handoff_validate_sdk(&b.handoff) == FBR34KER_SDK_OK);

    b.handoff.module_slot_limit = 1U;
    b.handoff.module_instruction_budget_limit = 100U;
    assert(fbr34ker_handoff_validate_sdk(&b.handoff) == FBR34KER_SDK_ERR_POLICY);
    b.handoff.flags |= FBR34KER_HANDOFF_FLAG_MODULE_POLICY_VALID;
    assert(fbr34ker_handoff_validate_sdk(&b.handoff) == FBR34KER_SDK_OK);

    puts("sdk harness passed");
    return 0;
}
