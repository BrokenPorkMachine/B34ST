#include "fbr34ker/module.h"

static const fbr34ker_api_t *module_api;

static int hello_initialize(const fbr34ker_api_t *api)
{
    if (api == NULL || api->abi_version != FBR34KER_MODULE_ABI) {
        return -1;
    }
    module_api = api;
    module_api->log_info("hello module initialized");
    return 0;
}

static void hello_finalize(void)
{
    if (module_api != NULL) {
        module_api->log_info("hello module finalized");
    }
    module_api = NULL;
}

const fbr34ker_module_descriptor_t hello_module_descriptor = {
    .abi_version = FBR34KER_MODULE_ABI,
    .name = "hello",
    .version = "0.4.5b",
    .description = "Built-in example demonstrating the FBR34KER module API.",
    .initialize = hello_initialize,
    .finalize = hello_finalize,
};
