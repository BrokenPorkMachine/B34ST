#include "fbr34ker_sdk.h"

// SPDX-License-Identifier: BSD-2-Clause
static bool valid_range(uint64_t base, uint64_t size) {
    return size != 0U && base <= UINT64_MAX - size;
}
static void zero_bytes(void *pointer, size_t size) {
    unsigned char *bytes = (unsigned char *)pointer;
    for (size_t index = 0; index < size; ++index) bytes[index] = 0U;
}

void fbr34ker_handoff_builder_init(fbr34ker_handoff_builder_t *builder,
                                   uint64_t monitor_base, uint64_t monitor_size) {
    if (builder == NULL) return;
    zero_bytes(builder, sizeof(*builder));
    builder->handoff.magic = FBR34KER_HANDOFF_MAGIC;
    builder->handoff.version = FBR34KER_HANDOFF_VERSION_CURRENT;
    builder->handoff.structure_size = (uint32_t)sizeof(builder->handoff);
    builder->handoff.monitor_base = monitor_base;
    builder->handoff.monitor_size = monitor_size;
    builder->handoff.entry_exception_level = 1U;
    builder->handoff.page_granule = FBR34KER_PAGE_GRANULE_4K;
}

fbr34ker_sdk_result_t fbr34ker_handoff_builder_add_region(
    fbr34ker_handoff_builder_t *builder, uint64_t base, uint64_t size,
    uint32_t type, uint32_t attributes) {
    if (builder == NULL || !valid_range(base, size)) return FBR34KER_SDK_ERR_ARGUMENT;
    if (builder->region_count >= FBR34KER_SDK_MAX_REGIONS) return FBR34KER_SDK_ERR_CAPACITY;
    if (type < FBR34KER_HANDOFF_REGION_USABLE || type > FBR34KER_HANDOFF_REGION_FRAMEBUFFER ||
        (attributes & ~FBR34KER_REGION_ATTR_SUPPORTED) != 0U) return FBR34KER_SDK_ERR_PERMISSIONS;
    uint64_t end = base + size;
    for (uint32_t i = 0U; i < builder->region_count; ++i) {
        uint64_t region_end = builder->regions[i].base + builder->regions[i].size;
        if (base < region_end && end > builder->regions[i].base) return FBR34KER_SDK_ERR_OVERLAP;
    }
    builder->regions[builder->region_count++] = (fbr34ker_handoff_region_t){base, size, type, attributes};
    return FBR34KER_SDK_OK;
}

fbr34ker_sdk_result_t fbr34ker_handoff_builder_add_module(
    fbr34ker_handoff_builder_t *builder, const void *base, uint64_t size,
    uint32_t type, uint32_t flags) {
    if (builder == NULL || base == NULL || size == 0U) return FBR34KER_SDK_ERR_ARGUMENT;
    if (builder->module_count >= FBR34KER_SDK_MAX_MODULES) return FBR34KER_SDK_ERR_CAPACITY;
    if (type == FBR34KER_BOOT_MODULE_TYPE_FMOD && size > FBR34KER_BOOT_MODULE_MAX_FMOD_SIZE)
        return FBR34KER_SDK_ERR_RANGE;
    builder->modules[builder->module_count++] = (fbr34ker_handoff_boot_module_t){base, size, type, flags};
    return FBR34KER_SDK_OK;
}

void fbr34ker_handoff_builder_set_services(fbr34ker_handoff_builder_t *builder,
                                           const fbr34ker_platform_services_t *services) {
    if (builder == NULL) return;
    zero_bytes(&builder->services, sizeof(builder->services));
    builder->handoff.platform_services = NULL;
    builder->handoff.platform_services_size = 0U;
    builder->handoff.flags &= ~FBR34KER_HANDOFF_FLAG_PLATFORM_SERVICES_VALID;
    if (services != NULL) {
        builder->services = *services;
        builder->handoff.platform_services = &builder->services;
        builder->handoff.platform_services_size = (uint32_t)sizeof(builder->services);
        builder->handoff.flags |= FBR34KER_HANDOFF_FLAG_PLATFORM_SERVICES_VALID;
    }
}

fbr34ker_sdk_result_t fbr34ker_handoff_builder_finalize(
    fbr34ker_handoff_builder_t *builder, const fbr34ker_handoff_t **handoff_out) {
    if (builder == NULL || handoff_out == NULL) return FBR34KER_SDK_ERR_ARGUMENT;
    builder->handoff.memory_regions = builder->regions;
    builder->handoff.memory_region_count = builder->region_count;
    builder->handoff.boot_modules = builder->module_count != 0U ? builder->modules : NULL;
    builder->handoff.boot_module_count = builder->module_count;
    fbr34ker_sdk_result_t result = fbr34ker_handoff_validate_sdk(&builder->handoff);
    if (result == FBR34KER_SDK_OK) *handoff_out = &builder->handoff;
    return result;
}
