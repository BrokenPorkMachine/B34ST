#ifndef FBR34KER_SDK_H
#define FBR34KER_SDK_H
#include "fbr34ker_bridge_protocol.h"
#include "fbr34ker_handoff.h"

#define FBR34KER_SDK_MAX_REGIONS 32U
#define FBR34KER_SDK_MAX_MODULES 8U

typedef enum {
    FBR34KER_SDK_OK = 0,
    FBR34KER_SDK_ERR_ARGUMENT,
    FBR34KER_SDK_ERR_ABI,
    FBR34KER_SDK_ERR_RANGE,
    FBR34KER_SDK_ERR_OVERLAP,
    FBR34KER_SDK_ERR_PERMISSIONS,
    FBR34KER_SDK_ERR_CALLBACK,
    FBR34KER_SDK_ERR_POLICY,
    FBR34KER_SDK_ERR_CAPACITY
} fbr34ker_sdk_result_t;

typedef struct {
    fbr34ker_handoff_t handoff;
    fbr34ker_platform_services_t services FBR34KER_SDK_ALIGNED(8);
    fbr34ker_handoff_region_t regions[FBR34KER_SDK_MAX_REGIONS] FBR34KER_SDK_ALIGNED(8);
    fbr34ker_handoff_boot_module_t modules[FBR34KER_SDK_MAX_MODULES] FBR34KER_SDK_ALIGNED(8);
    uint32_t region_count;
    uint32_t module_count;
} fbr34ker_handoff_builder_t;

typedef struct {
    uint64_t required_services;
    uint32_t required_module_capabilities;
    uint32_t expected_exception_level;
    uint32_t expected_page_granule;
    bool require_device_tree;
    bool require_framebuffer;
} fbr34ker_sdk_profile_t;

void fbr34ker_handoff_builder_init(fbr34ker_handoff_builder_t *builder,
                                   uint64_t monitor_base, uint64_t monitor_size);
fbr34ker_sdk_result_t fbr34ker_handoff_builder_add_region(
    fbr34ker_handoff_builder_t *builder, uint64_t base, uint64_t size,
    uint32_t type, uint32_t attributes);
fbr34ker_sdk_result_t fbr34ker_handoff_builder_add_module(
    fbr34ker_handoff_builder_t *builder, const void *base, uint64_t size,
    uint32_t type, uint32_t flags);
void fbr34ker_handoff_builder_set_services(fbr34ker_handoff_builder_t *builder,
                                           const fbr34ker_platform_services_t *services);
fbr34ker_sdk_result_t fbr34ker_handoff_builder_finalize(
    fbr34ker_handoff_builder_t *builder, const fbr34ker_handoff_t **handoff_out);
fbr34ker_sdk_result_t fbr34ker_handoff_validate_sdk(const fbr34ker_handoff_t *handoff);
fbr34ker_sdk_result_t fbr34ker_profile_match_sdk(
    const fbr34ker_handoff_t *handoff, const fbr34ker_sdk_profile_t *profile);
const char *fbr34ker_sdk_result_string(fbr34ker_sdk_result_t result);

#endif
