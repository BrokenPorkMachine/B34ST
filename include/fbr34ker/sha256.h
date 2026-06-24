#pragma once
#include "fbr34ker/types.h"

typedef struct {
    u32 state[8];
    u64 bit_count;
    u8 buffer[64];
    usize buffer_used;
} sha256_context_t;

void sha256_init(sha256_context_t *context);
void sha256_update(sha256_context_t *context, const void *data, usize size);
void sha256_final(sha256_context_t *context, u8 digest[32]);
void sha256_compute(const void *data, usize size, u8 digest[32]);
bool sha256_digest_equal(const u8 left[32], const u8 right[32]);
