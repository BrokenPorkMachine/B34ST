#include "fbr34ker/secure_boot_bypass.h"
#include "fbr34ker/event.h"
#include "fbr34ker/log.h"
#include "fbr34ker/string.h"
#include "fbr34ker/fault.h"
#include "fbr34ker/mmio.h"
#include "fbr34ker/kernel_patches.h"
#include "fbr34ker/apple_platform.h"

static secure_boot_bypass_status_t state;

static void register_default_bypasses(void)
{
    secure_boot_bypass_register("image4-sig", BYPASS_TYPE_IMAGE4_SIGNATURE, 0U, 0U);
    secure_boot_bypass_register("cert-chain", BYPASS_TYPE_CERTIFICATE_CHAIN, 0U, 0U);
    secure_boot_bypass_register("ap-ticket", BYPASS_TYPE_AP_TICKET, 0U, 0U);
    secure_boot_bypass_register("shsh-blob", BYPASS_TYPE_SHSH_BLOB, 0U, 0U);
    secure_boot_bypass_register("iboot-auth", BYPASS_TYPE_IBOOT_AUTH, 0U, 0U);
    secure_boot_bypass_register("boot-manifest", BYPASS_TYPE_BOOT_MANIFEST, 0U, 0U);
    log_write(LOG_LEVEL_INFO, "registered %u default secure boot bypasses",
              state.bypass_count);
}

void secure_boot_bypass_init(void)
{
    fm_memset(&state, 0, sizeof(state));
    state.signature_validation_disabled = false;
    state.certificate_chain_deployed = false;
    state.ap_ticket_bypassed = false;
    state.shsh_bypassed = false;
    state.iboot_auth_disabled = false;
    state.boot_manifest_compromised = false;
    register_default_bypasses();
    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE,
                            "secure-boot-bypass", 1U, 0U);
    log_write(LOG_LEVEL_INFO, "secure boot bypass subsystem initialized (%u entries)",
              state.bypass_count);
}

secure_boot_bypass_status_t secure_boot_bypass_status(void)
{
    return state;
}

bool secure_boot_bypass_register(const char *name,
                                  secure_boot_bypass_type_t type,
                                  u64 target_base, u64 region_size)
{
    if (name == NULL ||
        state.bypass_count >= MAX_SIGNATURE_BYPASSES ||
        type >= BYPASS_TYPE_COUNT) {
        return false;
    }
    secure_boot_bypass_entry_t *entry = &state.bypasses[state.bypass_count];
    fm_strlcpy(entry->name, name, sizeof(entry->name));
    entry->type = type;
    entry->state = BYPASS_STATE_INACTIVE;
    entry->target_base = target_base;
    entry->region_size = region_size;
    entry->applied = false;
    entry->persistent = false;
    ++state.bypass_count;
    log_write(LOG_LEVEL_INFO, "registered secure boot bypass '%s' type=%s",
              name, secure_boot_bypass_type_name(type));
    return true;
}

static bool activate_bypass_entry(secure_boot_bypass_entry_t *entry)
{
    if (entry == NULL || entry->applied) {
        return false;
    }
    if (fault_injection_should_fail(FBR34KER_FAULT_EVENT_PUBLISH,
                                    "secure_boot_bypass_activate")) {
        entry->state = BYPASS_STATE_FAILED;
        ++state.failed_count;
        return false;
    }
    entry->state = BYPASS_STATE_ACTIVE;
    entry->applied = true;
    ++state.active_count;
    log_write(LOG_LEVEL_INFO, "activated secure boot bypass '%s'",
              entry->name);
    return true;
}

bool secure_boot_bypass_activate_all(void)
{
    bool all_success = true;
    for (u32 i = 0U; i < state.bypass_count; ++i) {
        if (!activate_bypass_entry(&state.bypasses[i])) {
            all_success = false;
        }
    }
    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE,
                            "bypass-activate-all", state.active_count,
                            state.failed_count);
    return all_success;
}

bool secure_boot_bypass_activate_by_type(secure_boot_bypass_type_t type)
{
    if (type >= BYPASS_TYPE_COUNT) {
        return false;
    }
    bool all_success = true;
    for (u32 i = 0U; i < state.bypass_count; ++i) {
        if (state.bypasses[i].type == type &&
            !activate_bypass_entry(&state.bypasses[i])) {
            all_success = false;
        }
    }
    return all_success;
}

bool secure_boot_bypass_deactivate_all(void)
{
    for (u32 i = 0U; i < state.bypass_count; ++i) {
        secure_boot_bypass_entry_t *entry = &state.bypasses[i];
        if (entry->applied) {
            entry->state = BYPASS_STATE_INACTIVE;
            entry->applied = false;
            if (state.active_count > 0U) {
                --state.active_count;
            }
        }
    }
    state.signature_validation_disabled = false;
    state.certificate_chain_deployed = false;
    state.ap_ticket_bypassed = false;
    state.shsh_bypassed = false;
    state.iboot_auth_disabled = false;
    state.boot_manifest_compromised = false;
    return true;
}

static bool bypass_register_and_apply(const char *name, u64 kernel_offset,
                                       u32 patch_value)
{
    u64 addr = APPLE_IOS_KERNEL_BASE + kernel_offset;
    if (!kernel_patches_register(name, KERNEL_PATCH_TYPE_AUTHENTICATION,
                                 addr, 4U, 0U, patch_value, true)) {
        return false;
    }
    return kernel_patches_apply_by_type(KERNEL_PATCH_TYPE_AUTHENTICATION);
}

bool secure_boot_bypass_image4_signature(void)
{
    state.signature_validation_disabled = true;
    bool ok = bypass_register_and_apply("img4-sig", 0x00B00000U, 0xD503201FU);
    log_write(LOG_LEVEL_INFO, "Image4 signature validation disabled (patch %s)",
              ok ? "applied" : "pending");
    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE,
                            "image4-bypass", ok ? 1U : 0U, 0U);
    return ok;
}

bool secure_boot_bypass_deploy_fake_chain(void)
{
    state.certificate_chain_deployed = true;
    bool ok = bypass_register_and_apply("cert-chain", 0x00B00100U, 0x52800020U);
    log_write(LOG_LEVEL_INFO, "fake certificate chain deployed (patch %s)",
              ok ? "applied" : "pending");
    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE,
                            "cert-chain-deploy", ok ? 1U : 0U, 0U);
    return ok;
}

bool secure_boot_bypass_forge_signature(u8 *output, usize *output_size,
                                         const u8 *manifest, usize manifest_size)
{
    if (output == NULL || output_size == NULL ||
        manifest == NULL ||
        manifest_size == 0U || *output_size < 256U) {
        return false;
    }
    if (fault_injection_should_fail(FBR34KER_FAULT_EVENT_PUBLISH,
                                    "secure_boot_bypass_forge")) {
        return false;
    }
    fm_memcpy(output, manifest,
              manifest_size < 256U ? manifest_size : 256U);
    if (manifest_size < 256U) {
        fm_memset(output + manifest_size, 0, 256U - manifest_size);
    }
    *output_size = 256U;
    log_write(LOG_LEVEL_INFO, "forged signature block (%u bytes)",
              (unsigned)*output_size);
    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE,
                            "signature-forge", (u64)*output_size, 1U);
    return true;
}

bool secure_boot_bypass_ap_ticket(void)
{
    state.ap_ticket_bypassed = true;
    bool ok = bypass_register_and_apply("ap-ticket", 0x00B00200U, 0xD503201FU);
    log_write(LOG_LEVEL_INFO, "APTicket validation bypassed (patch %s)",
              ok ? "applied" : "pending");
    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE,
                            "ap-ticket-bypass", ok ? 1U : 0U, 0U);
    return ok;
}

bool secure_boot_bypass_shsh_blob(void)
{
    state.shsh_bypassed = true;
    bool ok = bypass_register_and_apply("shsh-blob", 0x00B00300U, 0xD503201FU);
    log_write(LOG_LEVEL_INFO, "SHSH blob acceptance enabled (patch %s)",
              ok ? "applied" : "pending");
    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE,
                            "shsh-bypass", ok ? 1U : 0U, 0U);
    return ok;
}

bool secure_boot_bypass_iboot_authentication(void)
{
    state.iboot_auth_disabled = true;
    bool ok = bypass_register_and_apply("iboot-auth", 0x00B00400U, 0xD503201FU);
    log_write(LOG_LEVEL_INFO, "iBoot image authentication disabled (patch %s)",
              ok ? "applied" : "pending");
    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE,
                            "iboot-auth-bypass", ok ? 1U : 0U, 0U);
    return ok;
}

bool secure_boot_bypass_boot_manifest(void)
{
    state.boot_manifest_compromised = true;
    bool ok = bypass_register_and_apply("boot-manifest", 0x00B00500U, 0xD503201FU);
    log_write(LOG_LEVEL_INFO, "boot manifest trust evaluation overridden (patch %s)",
              ok ? "applied" : "pending");
    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE,
                            "manifest-bypass", ok ? 1U : 0U, 0U);
    return ok;
}

bool secure_boot_bypass_available(void)
{
    return state.bypass_count > 0U;
}

const char *secure_boot_bypass_type_name(secure_boot_bypass_type_t type)
{
    switch (type) {
    case BYPASS_TYPE_IMAGE4_SIGNATURE: return "image4-signature";
    case BYPASS_TYPE_CERTIFICATE_CHAIN: return "certificate-chain";
    case BYPASS_TYPE_AP_TICKET: return "ap-ticket";
    case BYPASS_TYPE_SHSH_BLOB: return "shsh-blob";
    case BYPASS_TYPE_IBOOT_AUTH: return "iboot-auth";
    case BYPASS_TYPE_BOOT_MANIFEST: return "boot-manifest";
    case BYPASS_TYPE_COUNT: return "count";
    default: return "unknown";
    }
}

u32 secure_boot_bypass_active_count(void)
{
    return state.active_count;
}
