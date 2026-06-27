#pragma once
#include "fbr34ker/types.h"
#include "fbr34ker/log.h"
#include "fbr34ker/mmio.h"
#include "fbr34ker/event.h"
#include "fbr34ker/kernel_patches.h"

/* CVE exploit state machine */
#define CVE_STATE_IDLE   0
#define CVE_STATE_RUNNING 1
#define CVE_STATE_DONE   2
#define CVE_STATE_FAIL   3

/* Maximum CVE exploit name length */
#define CVE_NAME_MAX 48U

/* Exploit result descriptor */
typedef struct {
    char cve_id[CVE_NAME_MAX];
    u64 state;
    u64 kernel_task;
    u64 kernel_base;
    bool pwned;
    bool privilege_escalated;
    bool sandbox_escaped;
    bool codesign_bypassed;
} cve_result_t;

/* Built-in helper: find kernel base address */
static inline bool cve_find_kernel_base(u64 *kbase)
{
    if (!kbase) return false;
    u64 val = 0;
    /* Scan typical kernel base regions */
    for (u64 addr = 0xFFFFFFF007004000ULL; addr < 0xFFFFFFF007008000ULL; addr += 0x1000) {
        if (mmio_probe_read32(addr, (u32*)&val)) {
            *kbase = addr & 0xFFFFFFF000000000ULL;
            return true;
        }
    }
    return false;
}

/* Initialize a CVE result descriptor */
static inline void cve_result_init(cve_result_t *r, const char *id)
{
    if (!r) return;
    for (usize i = 0; i < CVE_NAME_MAX - 1 && id[i]; i++)
        r->cve_id[i] = id[i];
    r->cve_id[CVE_NAME_MAX - 1] = 0;
    r->state = CVE_STATE_IDLE;
    r->kernel_task = 0;
    r->kernel_base = 0;
    r->pwned = false;
    r->privilege_escalated = false;
    r->sandbox_escaped = false;
    r->codesign_bypassed = false;
}
