#pragma once
#include "fbr34ker/types.h"

#define TRUST_CACHE_CDHASH_SIZE 20U
#define TRUST_CACHE_MAX_ENTRIES 64U
#define TRUST_CACHE_ENTRY_NAME_LEN 48U
#define TRUST_CACHE_SCAN_SIZE (512U * 1024U)
#define TRUST_CACHE_SCAN_ALIGN 16U
#define TRUST_CACHE_VERSION_0 0U
#define TRUST_CACHE_VERSION_1 1U

typedef enum {
    TRUST_CACHE_HASH_SHA1 = 1,
    TRUST_CACHE_HASH_SHA2 = 2,
} trust_cache_hash_type_t;

typedef enum {
    TRUST_CACHE_STATE_INACTIVE = 0,
    TRUST_CACHE_STATE_ACTIVE,
    TRUST_CACHE_STATE_FAILED,
} trust_cache_state_t;

typedef struct PACKED {
    u8 cdhash[TRUST_CACHE_CDHASH_SIZE];
    u8 hash_type;
    u8 flags;
} trust_cache_entry_v1_t;

typedef struct PACKED {
    u32 version;
    u32 num_entries;
    u8 entries[];
} trust_cache_header_t;

typedef struct {
    char name[TRUST_CACHE_ENTRY_NAME_LEN];
    trust_cache_entry_v1_t entry;
    trust_cache_state_t state;
    bool injected;
} trust_cache_slot_t;

typedef struct {
    trust_cache_slot_t slots[TRUST_CACHE_MAX_ENTRIES];
    u32 slot_count;
    u32 injected_count;
    u64 anchor_address;
    trust_cache_state_t state;
} trust_cache_status_t;

void trust_cache_init(void);
trust_cache_status_t trust_cache_get_status(void);

bool trust_cache_register_entry(const char *name,
                                 const u8 cdhash[TRUST_CACHE_CDHASH_SIZE],
                                 trust_cache_hash_type_t hash_type);
bool trust_cache_inject_all(void);
bool trust_cache_find_anchor(void);
u64 trust_cache_get_anchor(void);
bool trust_cache_available(void);
u32 trust_cache_entry_count(void);
