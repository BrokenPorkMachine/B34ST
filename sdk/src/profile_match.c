#include "fbr34ker_sdk.h"

// SPDX-License-Identifier: BSD-2-Clause
fbr34ker_sdk_result_t fbr34ker_profile_match_sdk(
    const fbr34ker_handoff_t *handoff, const fbr34ker_sdk_profile_t *profile) {
    fbr34ker_sdk_result_t base = fbr34ker_handoff_validate_sdk(handoff);
    if (base != FBR34KER_SDK_OK || profile == NULL) return base != FBR34KER_SDK_OK ? base : FBR34KER_SDK_ERR_ARGUMENT;
    if (profile->expected_exception_level != 0U && handoff->entry_exception_level != profile->expected_exception_level)
        return FBR34KER_SDK_ERR_ABI;
    if (profile->expected_page_granule != 0U && handoff->page_granule != profile->expected_page_granule)
        return FBR34KER_SDK_ERR_ABI;
    if (profile->require_device_tree && (handoff->flags & FBR34KER_HANDOFF_FLAG_DEVICE_TREE_VALID) == 0U)
        return FBR34KER_SDK_ERR_RANGE;
    if (profile->require_framebuffer && (handoff->flags & FBR34KER_HANDOFF_FLAG_FRAMEBUFFER_VALID) == 0U)
        return FBR34KER_SDK_ERR_RANGE;
    if (profile->required_services != 0U) {
        if (handoff->platform_services == NULL ||
            (handoff->platform_services->capabilities & profile->required_services) != profile->required_services)
            return FBR34KER_SDK_ERR_CALLBACK;
    }
    if ((handoff->module_capability_allow_mask & profile->required_module_capabilities) != profile->required_module_capabilities)
        return FBR34KER_SDK_ERR_POLICY;
    return FBR34KER_SDK_OK;
}
