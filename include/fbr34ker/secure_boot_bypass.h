#pragma once
// SPDX-License-Identifier: BSD-2-Clause
#include "fbr34ker/types.h"

#define MAX_SIGNATURE_BYPASSES 8U
#define FAKE_CERTIFICATE_CHAIN_DEPTH 4U
#define IMAGE4_MANIFEST_MAX_SIZE 4096U

typedef enum {
    BYPASS_TYPE_IMAGE4_SIGNATURE = 0,
    BYPASS_TYPE_CERTIFICATE_CHAIN,
    BYPASS_TYPE_AP_TICKET,
    BYPASS_TYPE_SHSH_BLOB,
    BYPASS_TYPE_IBOOT_AUTH,
    BYPASS_TYPE_BOOT_MANIFEST,
    BYPASS_TYPE_COUNT
} secure_boot_bypass_type_t;

typedef enum {
    BYPASS_STATE_INACTIVE = 0,
    BYPASS_STATE_PREPARED,
    BYPASS_STATE_ACTIVE,
    BYPASS_STATE_FAILED
} secure_boot_bypass_state_t;

typedef struct {
    char name[48U];
    secure_boot_bypass_type_t type;
    secure_boot_bypass_state_t state;
    u64 target_base;
    u64 region_size;
    bool applied;
    bool persistent;
} secure_boot_bypass_entry_t;

typedef struct {
    secure_boot_bypass_entry_t bypasses[MAX_SIGNATURE_BYPASSES];
    u32 bypass_count;
    u32 active_count;
    u32 failed_count;
    bool signature_validation_disabled;
    bool certificate_chain_deployed;
    bool ap_ticket_bypassed;
    bool shsh_bypassed;
    bool iboot_auth_disabled;
    bool boot_manifest_compromised;
} secure_boot_bypass_status_t;

void secure_boot_bypass_init(void);
secure_boot_bypass_status_t secure_boot_bypass_status(void);

bool secure_boot_bypass_register(const char *name,
                                  secure_boot_bypass_type_t type,
                                  u64 target_base, u64 region_size);

bool secure_boot_bypass_activate_all(void);
bool secure_boot_bypass_activate_by_type(secure_boot_bypass_type_t type);
bool secure_boot_bypass_deactivate_all(void);

bool secure_boot_bypass_image4_signature(void);
bool secure_boot_bypass_deploy_fake_chain(void);
bool secure_boot_bypass_forge_signature(u8 *output, usize *output_size,
                                         const u8 *manifest, usize manifest_size);
bool secure_boot_bypass_ap_ticket(void);
bool secure_boot_bypass_shsh_blob(void);
bool secure_boot_bypass_iboot_authentication(void);
bool secure_boot_bypass_boot_manifest(void);

bool secure_boot_bypass_available(void);
const char *secure_boot_bypass_type_name(secure_boot_bypass_type_t type);
u32 secure_boot_bypass_active_count(void);
