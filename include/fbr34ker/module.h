#pragma once
// SPDX-License-Identifier: BSD-2-Clause
#include "fbr34ker/types.h"

#define FBR34KER_MODULE_ABI 3U
#define FBR34KER_MODULE_CONTAINER_MAGIC 0x444F4D46U
#define FBR34KER_MODULE_BYTECODE_MAGIC  0x30434246U
#define FBR34KER_MODULE_FORMAT_VERSION 1U
#define FBR34KER_MODULE_FLAGS_SUPPORTED 0U
#define FBR34KER_MODULE_BYTECODE_VERSION_1 1U
#define FBR34KER_MODULE_BYTECODE_VERSION_2 2U
#define FBR34KER_MODULE_BYTECODE_VERSION_CURRENT FBR34KER_MODULE_BYTECODE_VERSION_2
#define FBR34KER_MODULE_MAX_CONTAINER_SIZE (64U * 1024U)
#define FBR34KER_MODULE_MAX_DYNAMIC 4U
#define FBR34KER_MODULE_MAX_STATE_SLOTS 8U
#define FBR34KER_MODULE_MAX_INSTRUCTION_BUDGET 4096U

#define FBR34KER_MODULE_CAP_CONSOLE (1U << 0)
#define FBR34KER_MODULE_CAP_LOG     (1U << 1)
#define FBR34KER_MODULE_CAP_TIME    (1U << 2)
#define FBR34KER_MODULE_CAP_DT      (1U << 3)
#define FBR34KER_MODULE_CAP_STATE   (1U << 4)
#define FBR34KER_MODULE_CAP_HOST    (1U << 5)
#define FBR34KER_MODULE_CAP_SUPPORTED \
    (FBR34KER_MODULE_CAP_CONSOLE | FBR34KER_MODULE_CAP_LOG | \
     FBR34KER_MODULE_CAP_TIME | FBR34KER_MODULE_CAP_DT | \
     FBR34KER_MODULE_CAP_STATE | FBR34KER_MODULE_CAP_HOST)

typedef struct fbr34ker_api fbr34ker_api_t;
typedef int (*fbr34ker_module_init_fn)(const fbr34ker_api_t *api);
typedef void (*fbr34ker_module_fini_fn)(void);

typedef struct {
    u32 abi_version;
    const char *name;
    const char *version;
    const char *description;
    fbr34ker_module_init_fn initialize;
    fbr34ker_module_fini_fn finalize;
} fbr34ker_module_descriptor_t;

struct fbr34ker_api {
    u32 abi_version;
    int (*print)(const char *format, ...);
    void (*log_info)(const char *text);
    void *(*allocate)(usize size, usize alignment);
    u64 (*uptime_ms)(void);
};

typedef struct {
    u32 magic;
    u16 format_version;
    u16 header_size;
    u32 image_size;
    u32 flags;
    char name[32];
    char version[16];
    u8 sha256[32];
} fbr34ker_module_container_header_t;

typedef struct PACKED {
    u32 magic;
    u16 bytecode_version;
    u16 header_size;
    u32 code_size;
    u32 required_capabilities;
    u32 reserved;
} fbr34ker_module_bytecode_header_v1_t;

typedef struct PACKED {
    u32 magic;
    u16 bytecode_version;
    u16 header_size;
    u32 code_size;
    u32 required_capabilities;
    u16 state_slots;
    u16 reserved;
    char command[32];
    u32 instruction_budget;
} fbr34ker_module_bytecode_header_t;

typedef enum {
    FBR34KER_BC_HALT = 0x00,
    FBR34KER_BC_PUSH_U64 = 0x01,
    FBR34KER_BC_PRINT_TEXT = 0x02,
    FBR34KER_BC_LOG_TEXT = 0x03,
    FBR34KER_BC_UPTIME_MS = 0x04,
    FBR34KER_BC_ADD = 0x05,
    FBR34KER_BC_SUB = 0x06,
    FBR34KER_BC_PRINT_U64 = 0x07,
    FBR34KER_BC_DUP = 0x08,
    FBR34KER_BC_MUL = 0x09,
    FBR34KER_BC_AND = 0x0a,
    FBR34KER_BC_OR = 0x0b,
    FBR34KER_BC_XOR = 0x0c,
    FBR34KER_BC_EQ = 0x0d,
    FBR34KER_BC_DROP = 0x0e,
    FBR34KER_BC_SWAP = 0x0f,
    FBR34KER_BC_STATE_SET = 0x10,
    FBR34KER_BC_STATE_GET = 0x11,
    FBR34KER_BC_DT_HAS_NODE = 0x12,
    FBR34KER_BC_DT_GET_U32 = 0x13,
    FBR34KER_BC_LOG_KV = 0x14,
    FBR34KER_BC_HOST_EVENT = 0x15,
} fbr34ker_bytecode_opcode_t;

typedef struct {
    bool loaded;
    char name[32];
    char version[16];
    char command[32];
    u32 flags;
    u32 required_capabilities;
    u32 container_size;
    u32 code_size;
    u16 state_slots;
    u16 reserved;
    u32 instruction_budget;
    u64 run_count;
} fbr34ker_dynamic_module_info_t;


typedef struct {
    u32 allowed_capabilities;
    u16 dynamic_slot_limit;
    u16 reserved;
    u32 instruction_budget_limit;
    bool loader_defined;
} fbr34ker_module_policy_t;

typedef enum {
    MODULE_OK = 0,
    MODULE_ERROR_ARGUMENT = -1,
    MODULE_ERROR_SIZE = -2,
    MODULE_ERROR_HEADER = -3,
    MODULE_ERROR_HASH = -4,
    MODULE_ERROR_FORMAT = -5,
    MODULE_ERROR_CAPABILITY = -6,
    MODULE_ERROR_PROGRAM = -7,
    MODULE_ERROR_DUPLICATE = -8,
    MODULE_ERROR_CAPACITY = -9,
    MODULE_ERROR_NOT_FOUND = -10,
    MODULE_ERROR_RUNTIME = -11,
    MODULE_ERROR_QUOTA = -12,
} fbr34ker_module_result_t;

void module_system_init(void);
u64 module_builtin_count(void);
const fbr34ker_module_descriptor_t *module_builtin_at(u64 index);
const fbr34ker_module_descriptor_t *module_builtin_find(const char *name);
u64 module_dynamic_count(void);
bool module_dynamic_info(u64 index, fbr34ker_dynamic_module_info_t *information);
fbr34ker_module_result_t module_load_container(const void *container, usize size,
                                            const char **loaded_name);
fbr34ker_module_result_t module_run_dynamic(const char *name);
fbr34ker_module_result_t module_unload_dynamic(const char *name);
bool module_run_registered_command(const char *command,
                                   fbr34ker_module_result_t *result);
bool module_check_integrity(void);
fbr34ker_module_policy_t module_policy(void);
const char *module_result_string(fbr34ker_module_result_t result);
bool module_container_header_valid(const fbr34ker_module_container_header_t *header,
                                   usize available_size);
