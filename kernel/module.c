#include "fbr34ker/module.h"
#include "fbr34ker/allocator.h"
#include "fbr34ker/command.h"
#include "fbr34ker/console.h"
#include "fbr34ker/device_tree.h"
#include "fbr34ker/event.h"
#include "fbr34ker/format.h"
#include "fbr34ker/handoff.h"
#include "fbr34ker/hardware_probe.h"
#include "fbr34ker/log.h"
#include "fbr34ker/protocol.h"
#include "fbr34ker/sha256.h"
#include "fbr34ker/string.h"
#include "fbr34ker/timer.h"

#define BYTECODE_STACK_CAPACITY 16U
#define BYTECODE_MAX_TEXT 1024U
#define BYTECODE_MAX_KEY 23U

// SPDX-License-Identifier: BSD-2-Clause
extern const fbr34ker_module_descriptor_t hello_module_descriptor;

static const fbr34ker_module_descriptor_t *const built_in_modules[] = {
    &hello_module_descriptor,
};

typedef struct {
    bool used;
    char key[BYTECODE_MAX_KEY + 1U];
    u64 value;
} module_state_entry_t;

typedef struct {
    bool loaded;
    fbr34ker_dynamic_module_info_t information;
    module_state_entry_t state[FBR34KER_MODULE_MAX_STATE_SLOTS];
    ALIGNED(16) u8 container[FBR34KER_MODULE_MAX_CONTAINER_SIZE];
} dynamic_module_slot_t;

typedef struct {
    const u8 *code;
    u32 code_size;
    u32 capabilities;
    u16 state_slots;
    char command[32];
    u32 instruction_budget;
} bytecode_view_t;

static dynamic_module_slot_t dynamic_modules[FBR34KER_MODULE_MAX_DYNAMIC];
static fbr34ker_module_policy_t active_policy = {
    .allowed_capabilities = FBR34KER_MODULE_CAP_SUPPORTED,
    .dynamic_slot_limit = FBR34KER_MODULE_MAX_DYNAMIC,
    .reserved = 0U,
    .instruction_budget_limit = FBR34KER_MODULE_MAX_INSTRUCTION_BUDGET,
    .loader_defined = false,
};

STATIC_ASSERT(sizeof(fbr34ker_module_container_header_t) == 96U,
              "FMOD header must remain 96 bytes");
STATIC_ASSERT(sizeof(fbr34ker_module_bytecode_header_v1_t) == 20U,
              "FMBC v1 header must remain 20 bytes");
STATIC_ASSERT(sizeof(fbr34ker_module_bytecode_header_t) == 56U,
              "FMBC v2 header must remain 56 bytes");

static void module_log_info(const char *text)
{
    log_write(LOG_LEVEL_INFO, "module: %s", text);
}

static const fbr34ker_api_t fbr34ker_api = {
    .abi_version = FBR34KER_MODULE_ABI,
    .print = fm_printf,
    .log_info = module_log_info,
    .allocate = allocator_alloc,
    .uptime_ms = timer_uptime_ms,
};

static u16 read_le16(const u8 *bytes)
{
    return (u16)bytes[0] | (u16)((u16)bytes[1] << 8U);
}

static u64 read_le64(const u8 *bytes)
{
    u64 result = 0U;
    for (usize index = 0U; index < 8U; ++index) {
        result |= (u64)bytes[index] << (index * 8U);
    }
    return result;
}

static bool identifier_valid(const char *text, usize capacity, bool allow_empty)
{
    bool terminated = false;
    if (text == NULL || capacity == 0U) {
        return false;
    }
    if (text[0] == '\0') {
        return allow_empty;
    }
    for (usize index = 0U; index < capacity; ++index) {
        const char value = text[index];
        if (value == '\0') {
            terminated = true;
            break;
        }
        const bool alpha_numeric =
            (value >= 'a' && value <= 'z') ||
            (value >= 'A' && value <= 'Z') ||
            (value >= '0' && value <= '9');
        if (!alpha_numeric && value != '.' && value != '_' &&
            value != '-' && value != '+') {
            return false;
        }
    }
    return terminated;
}

static bool text_valid(const u8 *text, usize length)
{
    if (length == 0U || length > BYTECODE_MAX_TEXT) {
        return false;
    }
    for (usize index = 0U; index < length; ++index) {
        const u8 value = text[index];
        if (value == 0U || (value < 0x20U && value != '\n' &&
                            value != '\r' && value != '\t')) {
            return false;
        }
    }
    return true;
}

static bool key_valid(const u8 *key, usize length)
{
    if (length == 0U || length > BYTECODE_MAX_KEY) {
        return false;
    }
    for (usize index = 0U; index < length; ++index) {
        const u8 value = key[index];
        const bool alpha_numeric =
            (value >= 'a' && value <= 'z') ||
            (value >= 'A' && value <= 'Z') ||
            (value >= '0' && value <= '9');
        if (!alpha_numeric && value != '_' && value != '-' && value != '.') {
            return false;
        }
    }
    return true;
}

static bool read_inline(const u8 *code, usize code_size, usize *program_counter,
                        const u8 **text, usize *length, bool key)
{
    if (code_size - *program_counter < 2U) {
        return false;
    }
    const usize amount = read_le16(code + *program_counter);
    *program_counter += 2U;
    if (amount > code_size - *program_counter ||
        !(key ? key_valid(code + *program_counter, amount)
              : text_valid(code + *program_counter, amount))) {
        return false;
    }
    *text = code + *program_counter;
    *length = amount;
    *program_counter += amount;
    return true;
}

static fbr34ker_module_result_t parse_bytecode(const u8 *payload, usize size,
                                            bytecode_view_t *view)
{
    if (payload == NULL || view == NULL ||
        size < sizeof(fbr34ker_module_bytecode_header_v1_t)) {
        return MODULE_ERROR_FORMAT;
    }
    fbr34ker_module_bytecode_header_v1_t base;
    fm_memcpy(&base, payload, sizeof(base));
    if (base.magic != FBR34KER_MODULE_BYTECODE_MAGIC) {
        return MODULE_ERROR_FORMAT;
    }
    fm_memset(view, 0, sizeof(*view));
    if (base.bytecode_version == FBR34KER_MODULE_BYTECODE_VERSION_1) {
        if (base.header_size != sizeof(base) || base.reserved != 0U ||
            base.code_size != size - sizeof(base)) {
            return MODULE_ERROR_FORMAT;
        }
        view->code = payload + sizeof(base);
        view->code_size = base.code_size;
        view->capabilities = base.required_capabilities;
        view->instruction_budget = FBR34KER_MODULE_MAX_INSTRUCTION_BUDGET;
    } else if (base.bytecode_version == FBR34KER_MODULE_BYTECODE_VERSION_2) {
        if (size < sizeof(fbr34ker_module_bytecode_header_t)) {
            return MODULE_ERROR_FORMAT;
        }
        fbr34ker_module_bytecode_header_t header;
        fm_memcpy(&header, payload, sizeof(header));
        if (header.header_size != sizeof(header) || header.reserved != 0U ||
            header.code_size != size - sizeof(header) ||
            header.state_slots > FBR34KER_MODULE_MAX_STATE_SLOTS ||
            header.instruction_budget == 0U ||
            header.instruction_budget > FBR34KER_MODULE_MAX_INSTRUCTION_BUDGET ||
            !identifier_valid(header.command, sizeof(header.command), true)) {
            return MODULE_ERROR_FORMAT;
        }
        view->code = payload + sizeof(header);
        view->code_size = header.code_size;
        view->capabilities = header.required_capabilities;
        view->state_slots = header.state_slots;
        view->instruction_budget = header.instruction_budget;
        fm_strlcpy(view->command, header.command, sizeof(view->command));
    } else {
        return MODULE_ERROR_FORMAT;
    }
    if ((view->capabilities & ~FBR34KER_MODULE_CAP_SUPPORTED) != 0U ||
        ((view->capabilities & FBR34KER_MODULE_CAP_STATE) != 0U &&
         view->state_slots == 0U)) {
        return MODULE_ERROR_CAPABILITY;
    }
    return MODULE_OK;
}

static fbr34ker_module_result_t validate_program(const bytecode_view_t *view)
{
    const u8 *code = view->code;
    const usize code_size = view->code_size;
    usize program_counter = 0U;
    usize stack_depth = 0U;
    usize instruction_count = 0U;
    bool halted = false;

    while (program_counter < code_size) {
        if (++instruction_count > view->instruction_budget) {
            return MODULE_ERROR_PROGRAM;
        }
        const u8 opcode = code[program_counter++];
        switch (opcode) {
        case FBR34KER_BC_HALT:
            halted = true;
            if (program_counter != code_size) return MODULE_ERROR_PROGRAM;
            break;
        case FBR34KER_BC_PUSH_U64:
            if (code_size - program_counter < 8U ||
                stack_depth >= BYTECODE_STACK_CAPACITY) return MODULE_ERROR_PROGRAM;
            program_counter += 8U;
            ++stack_depth;
            break;
        case FBR34KER_BC_PRINT_TEXT:
        case FBR34KER_BC_LOG_TEXT:
        case FBR34KER_BC_HOST_EVENT: {
            const u8 *text;
            usize length;
            if (!read_inline(code, code_size, &program_counter, &text,
                             &length, false)) return MODULE_ERROR_PROGRAM;
            UNUSED(text); UNUSED(length);
            const u32 needed = opcode == FBR34KER_BC_PRINT_TEXT
                ? FBR34KER_MODULE_CAP_CONSOLE
                : opcode == FBR34KER_BC_LOG_TEXT
                    ? FBR34KER_MODULE_CAP_LOG : FBR34KER_MODULE_CAP_HOST;
            if ((view->capabilities & needed) == 0U) return MODULE_ERROR_CAPABILITY;
            break;
        }
        case FBR34KER_BC_UPTIME_MS:
            if ((view->capabilities & FBR34KER_MODULE_CAP_TIME) == 0U)
                return MODULE_ERROR_CAPABILITY;
            if (stack_depth >= BYTECODE_STACK_CAPACITY) return MODULE_ERROR_PROGRAM;
            ++stack_depth;
            break;
        case FBR34KER_BC_ADD: case FBR34KER_BC_SUB: case FBR34KER_BC_MUL:
        case FBR34KER_BC_AND: case FBR34KER_BC_OR: case FBR34KER_BC_XOR:
        case FBR34KER_BC_EQ:
            if (stack_depth < 2U) return MODULE_ERROR_PROGRAM;
            --stack_depth;
            break;
        case FBR34KER_BC_PRINT_U64:
            if ((view->capabilities & FBR34KER_MODULE_CAP_CONSOLE) == 0U)
                return MODULE_ERROR_CAPABILITY;
            if (stack_depth == 0U) return MODULE_ERROR_PROGRAM;
            --stack_depth;
            break;
        case FBR34KER_BC_DUP:
            if (stack_depth == 0U || stack_depth >= BYTECODE_STACK_CAPACITY)
                return MODULE_ERROR_PROGRAM;
            ++stack_depth;
            break;
        case FBR34KER_BC_DROP:
            if (stack_depth == 0U) return MODULE_ERROR_PROGRAM;
            --stack_depth;
            break;
        case FBR34KER_BC_SWAP:
            if (stack_depth < 2U) return MODULE_ERROR_PROGRAM;
            break;
        case FBR34KER_BC_STATE_SET:
        case FBR34KER_BC_STATE_GET:
        case FBR34KER_BC_LOG_KV: {
            const u8 *key;
            usize length;
            if (!read_inline(code, code_size, &program_counter, &key,
                             &length, true)) return MODULE_ERROR_PROGRAM;
            UNUSED(key); UNUSED(length);
            const u32 needed = opcode == FBR34KER_BC_LOG_KV
                ? FBR34KER_MODULE_CAP_LOG : FBR34KER_MODULE_CAP_STATE;
            if ((view->capabilities & needed) == 0U) return MODULE_ERROR_CAPABILITY;
            if (opcode == FBR34KER_BC_STATE_GET) {
                if (stack_depth >= BYTECODE_STACK_CAPACITY) return MODULE_ERROR_PROGRAM;
                ++stack_depth;
            } else {
                if (stack_depth == 0U) return MODULE_ERROR_PROGRAM;
                --stack_depth;
            }
            break;
        }
        case FBR34KER_BC_DT_HAS_NODE: {
            const u8 *path; usize length;
            if (!read_inline(code, code_size, &program_counter, &path,
                             &length, false)) return MODULE_ERROR_PROGRAM;
            UNUSED(path); UNUSED(length);
            if ((view->capabilities & FBR34KER_MODULE_CAP_DT) == 0U)
                return MODULE_ERROR_CAPABILITY;
            if (stack_depth >= BYTECODE_STACK_CAPACITY) return MODULE_ERROR_PROGRAM;
            ++stack_depth;
            break;
        }
        case FBR34KER_BC_DT_GET_U32: {
            const u8 *path; const u8 *property; usize path_length; usize property_length;
            if (!read_inline(code, code_size, &program_counter, &path,
                             &path_length, false) ||
                !read_inline(code, code_size, &program_counter, &property,
                             &property_length, true)) return MODULE_ERROR_PROGRAM;
            UNUSED(path); UNUSED(property); UNUSED(path_length); UNUSED(property_length);
            if ((view->capabilities & FBR34KER_MODULE_CAP_DT) == 0U)
                return MODULE_ERROR_CAPABILITY;
            if (stack_depth >= BYTECODE_STACK_CAPACITY) return MODULE_ERROR_PROGRAM;
            ++stack_depth;
            break;
        }
        default:
            return MODULE_ERROR_PROGRAM;
        }
        if (halted) break;
    }
    return halted ? MODULE_OK : MODULE_ERROR_PROGRAM;
}

static dynamic_module_slot_t *find_dynamic_slot(const char *name)
{
    for (usize index = 0U; index < ARRAY_COUNT(dynamic_modules); ++index) {
        if (dynamic_modules[index].loaded &&
            fm_strcmp(dynamic_modules[index].information.name, name) == 0) {
            return &dynamic_modules[index];
        }
    }
    return NULL;
}

static dynamic_module_slot_t *find_command_slot(const char *command)
{
    for (usize index = 0U; index < ARRAY_COUNT(dynamic_modules); ++index) {
        if (dynamic_modules[index].loaded &&
            dynamic_modules[index].information.command[0] != '\0' &&
            fm_strcmp(dynamic_modules[index].information.command, command) == 0) {
            return &dynamic_modules[index];
        }
    }
    return NULL;
}

static dynamic_module_slot_t *find_free_slot(void)
{
    const usize limit = active_policy.dynamic_slot_limit < ARRAY_COUNT(dynamic_modules)
        ? active_policy.dynamic_slot_limit : ARRAY_COUNT(dynamic_modules);
    for (usize index = 0U; index < limit; ++index) {
        if (!dynamic_modules[index].loaded) return &dynamic_modules[index];
    }
    return NULL;
}

void module_system_init(void)
{
    fm_memset(dynamic_modules, 0, sizeof(dynamic_modules));
    active_policy = (fbr34ker_module_policy_t){
        .allowed_capabilities = FBR34KER_MODULE_CAP_SUPPORTED,
        .dynamic_slot_limit = FBR34KER_MODULE_MAX_DYNAMIC,
        .reserved = 0U,
        .instruction_budget_limit = FBR34KER_MODULE_MAX_INSTRUCTION_BUDGET,
        .loader_defined = false,
    };
    const fbr34ker_handoff_t *handoff = fbr34ker_handoff_active();
    if (handoff != NULL && handoff->version >= FBR34KER_HANDOFF_VERSION_4 &&
        (handoff->flags & FBR34KER_HANDOFF_FLAG_MODULE_POLICY_VALID) != 0U) {
        active_policy.allowed_capabilities = handoff->module_capability_allow_mask;
        active_policy.dynamic_slot_limit = handoff->module_slot_limit;
        active_policy.instruction_budget_limit =
            handoff->module_instruction_budget_limit;
        active_policy.loader_defined = true;
    }
    if (hardware_probe_immutable()) {
        active_policy.allowed_capabilities = 0U;
        active_policy.dynamic_slot_limit = 0U;
        active_policy.instruction_budget_limit = 0U;
        return;
    }
    for (usize index = 0U; index < ARRAY_COUNT(built_in_modules); ++index) {
        const fbr34ker_module_descriptor_t *module = built_in_modules[index];
        if (module->abi_version != FBR34KER_MODULE_ABI || module->initialize == NULL) {
            log_write(LOG_LEVEL_WARN, "module %s has incompatible ABI", module->name);
            continue;
        }
        const int result = module->initialize(&fbr34ker_api);
        if (result != 0) {
            log_write(LOG_LEVEL_ERROR, "module %s init failed: %d", module->name, result);
        }
    }
}

u64 module_builtin_count(void) { return ARRAY_COUNT(built_in_modules); }
const fbr34ker_module_descriptor_t *module_builtin_at(u64 index)
{
    return index < ARRAY_COUNT(built_in_modules) ? built_in_modules[index] : NULL;
}
const fbr34ker_module_descriptor_t *module_builtin_find(const char *name)
{
    for (usize index = 0U; index < ARRAY_COUNT(built_in_modules); ++index) {
        if (fm_strcmp(built_in_modules[index]->name, name) == 0)
            return built_in_modules[index];
    }
    return NULL;
}

u64 module_dynamic_count(void)
{
    u64 count = 0U;
    for (usize index = 0U; index < ARRAY_COUNT(dynamic_modules); ++index)
        if (dynamic_modules[index].loaded) ++count;
    return count;
}

bool module_dynamic_info(u64 requested_index, fbr34ker_dynamic_module_info_t *information)
{
    u64 visible = 0U;
    if (information == NULL) return false;
    for (usize index = 0U; index < ARRAY_COUNT(dynamic_modules); ++index) {
        if (!dynamic_modules[index].loaded) continue;
        if (visible++ == requested_index) {
            *information = dynamic_modules[index].information;
            return true;
        }
    }
    return false;
}

bool module_container_header_valid(const fbr34ker_module_container_header_t *header,
                                   usize available_size)
{
    if (header == NULL || available_size < sizeof(*header)) return false;
    return header->magic == FBR34KER_MODULE_CONTAINER_MAGIC &&
           header->format_version == FBR34KER_MODULE_FORMAT_VERSION &&
           (header->flags & ~FBR34KER_MODULE_FLAGS_SUPPORTED) == 0U &&
           header->header_size == sizeof(*header) &&
           (usize)header->image_size == available_size - sizeof(*header) &&
           identifier_valid(header->name, sizeof(header->name), false) &&
           identifier_valid(header->version, sizeof(header->version), false);
}

fbr34ker_module_result_t module_load_container(const void *container, usize size,
                                            const char **loaded_name)
{
    if (loaded_name != NULL) *loaded_name = NULL;
    if (!hardware_probe_modules_allowed()) return MODULE_ERROR_CAPABILITY;
    if (container == NULL) return MODULE_ERROR_ARGUMENT;
    if (size < sizeof(fbr34ker_module_container_header_t) ||
        size > FBR34KER_MODULE_MAX_CONTAINER_SIZE) return MODULE_ERROR_SIZE;

    fbr34ker_module_container_header_t header;
    fm_memcpy(&header, container, sizeof(header));
    if (!module_container_header_valid(&header, size)) return MODULE_ERROR_HEADER;
    if (module_builtin_find(header.name) != NULL ||
        find_dynamic_slot(header.name) != NULL) return MODULE_ERROR_DUPLICATE;

    const u8 *payload = (const u8 *)container + sizeof(header);
    u8 digest[32];
    sha256_compute(payload, header.image_size, digest);
    if (!sha256_digest_equal(digest, header.sha256)) return MODULE_ERROR_HASH;

    bytecode_view_t view;
    fbr34ker_module_result_t result = parse_bytecode(payload, header.image_size, &view);
    if (result != MODULE_OK) return result;
    if (view.command[0] != '\0' &&
        (find_command_slot(view.command) != NULL ||
         shell_command_name_reserved(view.command))) {
        return MODULE_ERROR_DUPLICATE;
    }
    result = validate_program(&view);
    if (result != MODULE_OK) return result;
    if ((view.capabilities & ~active_policy.allowed_capabilities) != 0U) {
        return MODULE_ERROR_CAPABILITY;
    }
    if (view.instruction_budget > active_policy.instruction_budget_limit) {
        return MODULE_ERROR_QUOTA;
    }
    if (module_dynamic_count() >= active_policy.dynamic_slot_limit) {
        return MODULE_ERROR_CAPACITY;
    }

    dynamic_module_slot_t *slot = find_free_slot();
    if (slot == NULL) return MODULE_ERROR_CAPACITY;
    fm_memset(slot, 0, sizeof(*slot));
    fm_memcpy(slot->container, container, size);
    slot->loaded = true;
    slot->information.loaded = true;
    fm_strlcpy(slot->information.name, header.name, sizeof(slot->information.name));
    fm_strlcpy(slot->information.version, header.version, sizeof(slot->information.version));
    fm_strlcpy(slot->information.command, view.command, sizeof(slot->information.command));
    slot->information.flags = header.flags;
    slot->information.required_capabilities = view.capabilities;
    slot->information.container_size = (u32)size;
    slot->information.code_size = view.code_size;
    slot->information.state_slots = view.state_slots;
    slot->information.instruction_budget = view.instruction_budget;
    if (loaded_name != NULL) *loaded_name = slot->information.name;
    log_write(LOG_LEVEL_INFO, "loaded dynamic module %s %s (%u bytes)",
              slot->information.name, slot->information.version, (u32)size);
    (void)event_bus_publish(FBR34KER_EVENT_MODULE_LOADED, slot->information.name, (u64)size, slot->information.required_capabilities);
    return MODULE_OK;
}


static fbr34ker_module_result_t verify_slot_container(
    const dynamic_module_slot_t *slot, bytecode_view_t *view)
{
    if (slot == NULL || !slot->loaded || view == NULL ||
        slot->information.container_size <
            sizeof(fbr34ker_module_container_header_t) ||
        slot->information.container_size > FBR34KER_MODULE_MAX_CONTAINER_SIZE) {
        return MODULE_ERROR_HEADER;
    }

    fbr34ker_module_container_header_t header;
    fm_memcpy(&header, slot->container, sizeof(header));
    const usize container_size = slot->information.container_size;
    if (!module_container_header_valid(&header, container_size) ||
        fm_strcmp(header.name, slot->information.name) != 0 ||
        fm_strcmp(header.version, slot->information.version) != 0 ||
        header.flags != slot->information.flags) {
        return MODULE_ERROR_HEADER;
    }

    const u8 *payload = slot->container + sizeof(header);
    u8 digest[32];
    sha256_compute(payload, header.image_size, digest);
    if (!sha256_digest_equal(digest, header.sha256)) {
        return MODULE_ERROR_HASH;
    }

    fbr34ker_module_result_t result = parse_bytecode(
        payload, header.image_size, view);
    if (result != MODULE_OK) {
        return result;
    }
    result = validate_program(view);
    if (result != MODULE_OK) {
        return result;
    }
    if ((view->capabilities & ~active_policy.allowed_capabilities) != 0U ||
        view->instruction_budget > active_policy.instruction_budget_limit) {
        return MODULE_ERROR_CAPABILITY;
    }
    if (view->code_size != slot->information.code_size ||
        view->capabilities != slot->information.required_capabilities ||
        view->state_slots != slot->information.state_slots ||
        view->instruction_budget != slot->information.instruction_budget ||
        fm_strcmp(view->command, slot->information.command) != 0) {
        return MODULE_ERROR_HEADER;
    }
    return MODULE_OK;
}

fbr34ker_module_policy_t module_policy(void)
{
    return active_policy;
}

bool module_check_integrity(void)
{
    if (module_dynamic_count() > active_policy.dynamic_slot_limit) {
        return false;
    }
    for (usize index = 0U; index < ARRAY_COUNT(dynamic_modules); ++index) {
        if (!dynamic_modules[index].loaded) {
            continue;
        }
        bytecode_view_t view;
        if (verify_slot_container(&dynamic_modules[index], &view) != MODULE_OK) {
            return false;
        }
    }
    return true;
}

static bool inline_to_string(const u8 *bytes, usize length, char *text, usize capacity)
{
    if (length + 1U > capacity) return false;
    fm_memcpy(text, bytes, length);
    text[length] = '\0';
    return true;
}

static module_state_entry_t *state_find(dynamic_module_slot_t *slot,
                                        const char *key, bool create)
{
    const usize limit = slot->information.state_slots;
    module_state_entry_t *free_entry = NULL;
    for (usize index = 0U; index < limit; ++index) {
        if (slot->state[index].used && fm_strcmp(slot->state[index].key, key) == 0)
            return &slot->state[index];
        if (!slot->state[index].used && free_entry == NULL)
            free_entry = &slot->state[index];
    }
    if (create && free_entry != NULL) {
        free_entry->used = true;
        fm_strlcpy(free_entry->key, key, sizeof(free_entry->key));
        return free_entry;
    }
    return NULL;
}

static fbr34ker_module_result_t execute_slot(dynamic_module_slot_t *slot)
{
    bytecode_view_t view;
    const fbr34ker_module_result_t verified =
        verify_slot_container(slot, &view);
    if (verified != MODULE_OK) {
        return verified == MODULE_ERROR_HASH || verified == MODULE_ERROR_HEADER
            ? verified : MODULE_ERROR_RUNTIME;
    }
    const u8 *code = view.code;
    const usize code_size = view.code_size;
    u64 stack[BYTECODE_STACK_CAPACITY] = {0U};
    usize depth = 0U;
    usize pc = 0U;
    usize instructions = 0U;

    while (pc < code_size && instructions++ < view.instruction_budget) {
        const u8 opcode = code[pc++];
        const u8 *inline_data;
        usize inline_length;
        char first[BYTECODE_MAX_TEXT + 1U];
        char second[BYTECODE_MAX_KEY + 1U];
        switch (opcode) {
        case FBR34KER_BC_HALT:
            ++slot->information.run_count;
            return MODULE_OK;
        case FBR34KER_BC_PUSH_U64:
            if (code_size - pc < 8U || depth >= BYTECODE_STACK_CAPACITY) return MODULE_ERROR_RUNTIME;
            stack[depth++] = read_le64(code + pc); pc += 8U; break;
        case FBR34KER_BC_PRINT_TEXT:
        case FBR34KER_BC_LOG_TEXT:
        case FBR34KER_BC_HOST_EVENT:
            if (!read_inline(code, code_size, &pc, &inline_data, &inline_length, false) ||
                !inline_to_string(inline_data, inline_length, first, sizeof(first)))
                return MODULE_ERROR_RUNTIME;
            if (opcode == FBR34KER_BC_PRINT_TEXT) console_write_n(first, inline_length);
            else if (opcode == FBR34KER_BC_LOG_TEXT)
                log_write(LOG_LEVEL_INFO, "dynamic/%s: %s", slot->information.name, first);
            else protocol_emit_event(slot->information.name, first);
            break;
        case FBR34KER_BC_UPTIME_MS:
            if (depth >= BYTECODE_STACK_CAPACITY) return MODULE_ERROR_RUNTIME;
            stack[depth++] = timer_uptime_ms(); break;
        case FBR34KER_BC_ADD: case FBR34KER_BC_SUB: case FBR34KER_BC_MUL:
        case FBR34KER_BC_AND: case FBR34KER_BC_OR: case FBR34KER_BC_XOR:
        case FBR34KER_BC_EQ: {
            if (depth < 2U) return MODULE_ERROR_RUNTIME;
            const u64 right = stack[--depth];
            u64 *left = &stack[depth - 1U];
            if (opcode == FBR34KER_BC_ADD) {
                if (*left > U64_MAX_VALUE - right) {
                    log_write(LOG_LEVEL_ERROR, "bytecode ADD overflow: %llu + %llu",
                              *left, right);
                    return MODULE_ERROR_RUNTIME;
                }
                *left += right;
            } else if (opcode == FBR34KER_BC_SUB) {
                if (*left < right) {
                    log_write(LOG_LEVEL_ERROR, "bytecode SUB underflow: %llu - %llu",
                              *left, right);
                    return MODULE_ERROR_RUNTIME;
                }
                *left -= right;
            } else if (opcode == FBR34KER_BC_MUL) {
                if (right != 0U && *left > U64_MAX_VALUE / right) {
                    log_write(LOG_LEVEL_ERROR, "bytecode MUL overflow: %llu * %llu",
                              *left, right);
                    return MODULE_ERROR_RUNTIME;
                }
                *left *= right;
            } else if (opcode == FBR34KER_BC_AND) *left &= right;
            else if (opcode == FBR34KER_BC_OR) *left |= right;
            else if (opcode == FBR34KER_BC_XOR) *left ^= right;
            else *left = *left == right ? 1U : 0U;
            break;
        }
        case FBR34KER_BC_PRINT_U64:
            if (depth == 0U) return MODULE_ERROR_RUNTIME;
            fm_printf("%llu", stack[--depth]); break;
        case FBR34KER_BC_DUP:
            if (depth == 0U || depth >= BYTECODE_STACK_CAPACITY) return MODULE_ERROR_RUNTIME;
            stack[depth] = stack[depth - 1U]; ++depth; break;
        case FBR34KER_BC_DROP:
            if (depth == 0U) return MODULE_ERROR_RUNTIME;
            --depth; break;
        case FBR34KER_BC_SWAP:
            if (depth < 2U) return MODULE_ERROR_RUNTIME;
            { const u64 temp = stack[depth - 1U]; stack[depth - 1U] = stack[depth - 2U]; stack[depth - 2U] = temp; }
            break;
        case FBR34KER_BC_STATE_SET:
        case FBR34KER_BC_STATE_GET:
        case FBR34KER_BC_LOG_KV:
            if (!read_inline(code, code_size, &pc, &inline_data, &inline_length, true) ||
                !inline_to_string(inline_data, inline_length, second, sizeof(second)))
                return MODULE_ERROR_RUNTIME;
            if (opcode == FBR34KER_BC_STATE_GET) {
                if (depth >= BYTECODE_STACK_CAPACITY) return MODULE_ERROR_RUNTIME;
                module_state_entry_t *entry = state_find(slot, second, false);
                stack[depth++] = entry != NULL ? entry->value : 0U;
            } else {
                if (depth == 0U) return MODULE_ERROR_RUNTIME;
                const u64 value = stack[--depth];
                if (opcode == FBR34KER_BC_LOG_KV) {
                    log_write(LOG_LEVEL_INFO, "dynamic/%s %s=%llu",
                              slot->information.name, second, value);
                } else {
                    module_state_entry_t *entry = state_find(slot, second, true);
                    if (entry == NULL) return MODULE_ERROR_QUOTA;
                    entry->value = value;
                }
            }
            break;
        case FBR34KER_BC_DT_HAS_NODE:
            if (!read_inline(code, code_size, &pc, &inline_data, &inline_length, false) ||
                !inline_to_string(inline_data, inline_length, first, sizeof(first)) ||
                depth >= BYTECODE_STACK_CAPACITY) return MODULE_ERROR_RUNTIME;
            stack[depth++] = device_tree_has_node(first) ? 1U : 0U;
            break;
        case FBR34KER_BC_DT_GET_U32: {
            const u8 *property; usize property_length;
            if (!read_inline(code, code_size, &pc, &inline_data, &inline_length, false) ||
                !inline_to_string(inline_data, inline_length, first, sizeof(first)) ||
                !read_inline(code, code_size, &pc, &property, &property_length, true) ||
                !inline_to_string(property, property_length, second, sizeof(second)) ||
                depth >= BYTECODE_STACK_CAPACITY) return MODULE_ERROR_RUNTIME;
            u32 value = 0U;
            if (!device_tree_get_u32(first, second, &value)) {
                log_write(LOG_LEVEL_ERROR, "bytecode dt-get-u32 failed: %s/%s",
                          first, second);
                return MODULE_ERROR_RUNTIME;
            }
            stack[depth++] = value;
            break;
        }
        default:
            return MODULE_ERROR_RUNTIME;
        }
    }
    return MODULE_ERROR_RUNTIME;
}

fbr34ker_module_result_t module_run_dynamic(const char *name)
{
    if (!hardware_probe_modules_allowed()) return MODULE_ERROR_CAPABILITY;
    if (name == NULL) return MODULE_ERROR_ARGUMENT;
    dynamic_module_slot_t *slot = find_dynamic_slot(name);
    if (slot == NULL) return MODULE_ERROR_NOT_FOUND;
    log_write(LOG_LEVEL_INFO, "running dynamic module %s", name);
    const fbr34ker_module_result_t result = execute_slot(slot);
    if (result != MODULE_OK)
        log_write(LOG_LEVEL_ERROR, "dynamic module %s failed: %s", name,
                  module_result_string(result));
    (void)event_bus_publish(FBR34KER_EVENT_MODULE_EXECUTED, name, (u64)(i64)result, slot->information.run_count);
    return result;
}

bool module_run_registered_command(const char *command,
                                   fbr34ker_module_result_t *result)
{
    if (!hardware_probe_modules_allowed()) return false;
    dynamic_module_slot_t *slot = find_command_slot(command);
    if (slot == NULL) return false;
    log_write(LOG_LEVEL_INFO, "running dynamic module command %s", command);
    const fbr34ker_module_result_t execution = execute_slot(slot);
    if (result != NULL) *result = execution;
    (void)event_bus_publish(FBR34KER_EVENT_MODULE_EXECUTED, slot->information.name, (u64)(i64)execution, slot->information.run_count);
    return true;
}

fbr34ker_module_result_t module_unload_dynamic(const char *name)
{
    if (!hardware_probe_modules_allowed()) return MODULE_ERROR_CAPABILITY;
    if (name == NULL) return MODULE_ERROR_ARGUMENT;
    dynamic_module_slot_t *slot = find_dynamic_slot(name);
    if (slot == NULL) return MODULE_ERROR_NOT_FOUND;
    log_write(LOG_LEVEL_INFO, "unloaded dynamic module %s", name);
    (void)event_bus_publish(FBR34KER_EVENT_MODULE_UNLOADED, name, slot->information.run_count, 0U);
    fm_memset(slot, 0, sizeof(*slot));
    return MODULE_OK;
}

const char *module_result_string(fbr34ker_module_result_t result)
{
    switch (result) {
    case MODULE_OK: return "ok";
    case MODULE_ERROR_ARGUMENT: return "invalid argument";
    case MODULE_ERROR_SIZE: return "invalid size";
    case MODULE_ERROR_HEADER: return "invalid FMOD header";
    case MODULE_ERROR_HASH: return "SHA-256 mismatch";
    case MODULE_ERROR_FORMAT: return "unsupported payload format";
    case MODULE_ERROR_CAPABILITY: return "capability violation";
    case MODULE_ERROR_PROGRAM: return "invalid bytecode program";
    case MODULE_ERROR_DUPLICATE: return "duplicate module or command name";
    case MODULE_ERROR_CAPACITY: return "module slots full";
    case MODULE_ERROR_NOT_FOUND: return "module not found";
    case MODULE_ERROR_RUNTIME: return "bytecode runtime failure";
    case MODULE_ERROR_QUOTA: return "module state quota exceeded";
    default: return "unknown error";
    }
}
