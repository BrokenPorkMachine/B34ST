#include "fbr34ker/build_info.h"
#include "fbr34ker/handoff.h"
#include "fbr34ker/module.h"
#include "fbr34ker/protocol.h"
#include "fbr34ker/version.h"

STATIC_ASSERT(sizeof(FBR34KER_MONITOR_NAME) <= 16U,
              "monitor name exceeds build metadata field");
STATIC_ASSERT(sizeof(FBR34KER_MONITOR_VERSION) <= 24U,
              "monitor version exceeds build metadata field");
STATIC_ASSERT(sizeof(FBR34KER_MONITOR_BUILD) <= 24U,
              "build channel exceeds build metadata field");
STATIC_ASSERT(sizeof(FBR34KER_BUILD_TARGET) <= 24U,
              "build target exceeds build metadata field");
STATIC_ASSERT(sizeof(FBR34KER_SOURCE_ID) <= 32U,
              "source identifier exceeds build metadata field");

static const fbr34ker_build_info_t embedded_build_info
    __attribute__((used, section(".fbr34ker.build"), aligned(16))) = {
        .magic = FBR34KER_BUILD_INFO_MAGIC,
        .format_version = FBR34KER_BUILD_INFO_VERSION,
        .structure_size = sizeof(fbr34ker_build_info_t),
        .monitor_name = FBR34KER_MONITOR_NAME,
        .monitor_version = FBR34KER_MONITOR_VERSION,
        .build_channel = FBR34KER_MONITOR_BUILD,
        .build_target = FBR34KER_BUILD_TARGET,
        .source_id = FBR34KER_SOURCE_ID,
        .protocol_version = FBR34KER_PROTOCOL_VERSION,
        .handoff_version = FBR34KER_HANDOFF_VERSION_CURRENT,
        .module_abi = FBR34KER_MODULE_ABI,
        .module_format_version = FBR34KER_MODULE_FORMAT_VERSION,
        .bytecode_version = FBR34KER_MODULE_BYTECODE_VERSION_CURRENT,
    };

const fbr34ker_build_info_t *fbr34ker_build_info(void)
{
    return &embedded_build_info;
}
