#pragma once
// SPDX-License-Identifier: BSD-2-Clause
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

/* ------------------------------------------------------------------ */
/* Primitive types for exploit chaining                               */
/* ------------------------------------------------------------------ */
typedef enum {
    CVE_PRIMITIVE_NONE = 0,
    CVE_PRIMITIVE_KERNEL_READ,
    CVE_PRIMITIVE_KERNEL_WRITE,
    CVE_PRIMITIVE_KERNEL_RW,
    CVE_PRIMITIVE_ROOT_PRIVESC,
    CVE_PRIMITIVE_CODESIGN_BYPASS,
    CVE_PRIMITIVE_SANDBOX_ESCAPE,
    CVE_PRIMITIVE_INITIAL_ACCESS,
    CVE_PRIMITIVE_BOOTROM,
    CVE_PRIMITIVE_SEP_BYPASS,
    CVE_PRIMITIVE_KERNEL_LEAK,
    CVE_PRIMITIVE_COUNT,
} cve_primitive_type_t;

static inline const char *cve_primitive_name(cve_primitive_type_t t)
{
    switch (t) {
        case CVE_PRIMITIVE_KERNEL_READ:      return "kernel-read";
        case CVE_PRIMITIVE_KERNEL_WRITE:      return "kernel-write";
        case CVE_PRIMITIVE_KERNEL_RW:         return "kernel-rw";
        case CVE_PRIMITIVE_ROOT_PRIVESC:      return "root-privesc";
        case CVE_PRIMITIVE_CODESIGN_BYPASS:   return "codesign-bypass";
        case CVE_PRIMITIVE_SANDBOX_ESCAPE:    return "sandbox-escape";
        case CVE_PRIMITIVE_INITIAL_ACCESS:    return "initial-access";
        case CVE_PRIMITIVE_BOOTROM:           return "bootrom";
        case CVE_PRIMITIVE_SEP_BYPASS:        return "sep-bypass";
        case CVE_PRIMITIVE_KERNEL_LEAK:       return "kernel-leak";
        default:                              return "none";
    }
}

/* A single primitive instance with metadata */
typedef struct {
    cve_primitive_type_t type;
    u64 address;
    u64 value;
    bool consumed;
} cve_primitive_t;

#define CVE_PRIMITIVE_REGISTRY_MAX 64U

/* Runtime registry for chaining primitives across exploits */
typedef struct {
    cve_primitive_t primitives[CVE_PRIMITIVE_REGISTRY_MAX];
    u32 count;
    bool initialized;
} cve_primitive_registry_t;

extern cve_primitive_registry_t g_cve_primitives;

static inline void cve_primitive_registry_init(cve_primitive_registry_t *reg)
{
    if (!reg) return;
    reg->count = 0;
    reg->initialized = true;
}

static inline bool cve_primitive_register(cve_primitive_registry_t *reg,
                                          cve_primitive_type_t type,
                                          u64 address, u64 value)
{
    if (!reg || !reg->initialized) return false;
    if (reg->count >= CVE_PRIMITIVE_REGISTRY_MAX) return false;
    reg->primitives[reg->count].type = type;
    reg->primitives[reg->count].address = address;
    reg->primitives[reg->count].value = value;
    reg->primitives[reg->count].consumed = false;
    reg->count++;
    log_write(LOG_LEVEL_VERBOSE, "cve: registered %s (addr=0x%llx val=0x%llx)",
              cve_primitive_name(type), address, value);
    return true;
}

static inline bool cve_primitive_has(cve_primitive_registry_t *reg,
                                     cve_primitive_type_t type)
{
    if (!reg || !reg->initialized) return false;
    for (u32 i = 0; i < reg->count; i++) {
        if (reg->primitives[i].type == type && !reg->primitives[i].consumed)
            return true;
    }
    return false;
}

static inline bool cve_primitive_consume(cve_primitive_registry_t *reg,
                                         cve_primitive_type_t type,
                                         u64 *address, u64 *value)
{
    if (!reg || !reg->initialized) return false;
    for (u32 i = 0; i < reg->count; i++) {
        if (reg->primitives[i].type == type && !reg->primitives[i].consumed) {
            if (address) *address = reg->primitives[i].address;
            if (value) *value = reg->primitives[i].value;
            reg->primitives[i].consumed = true;
            log_write(LOG_LEVEL_VERBOSE, "cve: consumed %s (addr=0x%llx)",
                      cve_primitive_name(type), reg->primitives[i].address);
            return true;
        }
    }
    return false;
}

static inline u32 cve_primitive_available_count(cve_primitive_registry_t *reg)
{
    if (!reg || !reg->initialized) return 0;
    u32 count = 0;
    for (u32 i = 0; i < reg->count; i++) {
        if (!reg->primitives[i].consumed) count++;
    }
    return count;
}

/* ------------------------------------------------------------------ */
/* Exploit result descriptor                                          */
/* ------------------------------------------------------------------ */
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

/* Format status line into a buffer (returns chars written) */
static inline int cve_status_line(const char *cve_id, u64 state,
                                   char *buf, usize n)
{
    if (!buf || !n) return -1;
    usize i = 0;
    while (cve_id[i] && i < n - 1) {
        buf[i] = cve_id[i];
        i++;
    }
    const char *tag = "]";
    switch (state) {
        case CVE_STATE_IDLE:    tag = "]IDLE";   break;
        case CVE_STATE_RUNNING: tag = "]RUN";     break;
        case CVE_STATE_DONE:    tag = "]OK";      break;
        case CVE_STATE_FAIL:    tag = "]FAIL";    break;
    }
    buf[i++] = '[';
    int j = 0;
    while (tag[j] && i < n - 1) {
        buf[i] = tag[j];
        i++; j++;
    }
    buf[i] = 0;
    return (int)i;
}

/* Exploit entry descriptor (for registry) */
typedef struct {
    const char *cve_id;
    int (*init)(void);
    int (*exec)(void);
    int (*cleanup)(void);
    int (*status)(char *, usize);
    cve_primitive_type_t provides;
    cve_primitive_type_t requires;
} cve_exploit_entry_t;
