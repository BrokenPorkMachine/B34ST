#include "fbr34ker/sha256.h"
#include "fbr34ker/string.h"

// SPDX-License-Identifier: BSD-2-Clause
static const u32 round_constants[64] = {
    0x428a2f98U, 0x71374491U, 0xb5c0fbcfU, 0xe9b5dba5U,
    0x3956c25bU, 0x59f111f1U, 0x923f82a4U, 0xab1c5ed5U,
    0xd807aa98U, 0x12835b01U, 0x243185beU, 0x550c7dc3U,
    0x72be5d74U, 0x80deb1feU, 0x9bdc06a7U, 0xc19bf174U,
    0xe49b69c1U, 0xefbe4786U, 0x0fc19dc6U, 0x240ca1ccU,
    0x2de92c6fU, 0x4a7484aaU, 0x5cb0a9dcU, 0x76f988daU,
    0x983e5152U, 0xa831c66dU, 0xb00327c8U, 0xbf597fc7U,
    0xc6e00bf3U, 0xd5a79147U, 0x06ca6351U, 0x14292967U,
    0x27b70a85U, 0x2e1b2138U, 0x4d2c6dfcU, 0x53380d13U,
    0x650a7354U, 0x766a0abbU, 0x81c2c92eU, 0x92722c85U,
    0xa2bfe8a1U, 0xa81a664bU, 0xc24b8b70U, 0xc76c51a3U,
    0xd192e819U, 0xd6990624U, 0xf40e3585U, 0x106aa070U,
    0x19a4c116U, 0x1e376c08U, 0x2748774cU, 0x34b0bcb5U,
    0x391c0cb3U, 0x4ed8aa4aU, 0x5b9cca4fU, 0x682e6ff3U,
    0x748f82eeU, 0x78a5636fU, 0x84c87814U, 0x8cc70208U,
    0x90befffaU, 0xa4506cebU, 0xbef9a3f7U, 0xc67178f2U,
};

static u32 rotate_right(u32 value, u32 amount)
{
    return (value >> amount) | (value << (32U - amount));
}

static u32 load_be32(const u8 *bytes)
{
    return ((u32)bytes[0] << 24U) | ((u32)bytes[1] << 16U) |
           ((u32)bytes[2] << 8U) | (u32)bytes[3];
}

static void store_be32(u8 *bytes, u32 value)
{
    bytes[0] = (u8)(value >> 24U);
    bytes[1] = (u8)(value >> 16U);
    bytes[2] = (u8)(value >> 8U);
    bytes[3] = (u8)value;
}

static void transform(sha256_context_t *context, const u8 block[64])
{
    u32 schedule[64];
    for (usize index = 0U; index < 16U; ++index) {
        schedule[index] = load_be32(&block[index * 4U]);
    }
    for (usize index = 16U; index < 64U; ++index) {
        const u32 a = schedule[index - 15U];
        const u32 b = schedule[index - 2U];
        const u32 s0 = rotate_right(a, 7U) ^ rotate_right(a, 18U) ^ (a >> 3U);
        const u32 s1 = rotate_right(b, 17U) ^ rotate_right(b, 19U) ^ (b >> 10U);
        schedule[index] = schedule[index - 16U] + s0 +
                          schedule[index - 7U] + s1;
    }

    u32 a = context->state[0];
    u32 b = context->state[1];
    u32 c = context->state[2];
    u32 d = context->state[3];
    u32 e = context->state[4];
    u32 f = context->state[5];
    u32 g = context->state[6];
    u32 h = context->state[7];

    for (usize index = 0U; index < 64U; ++index) {
        const u32 sum1 = rotate_right(e, 6U) ^ rotate_right(e, 11U) ^
                         rotate_right(e, 25U);
        const u32 choose = (e & f) ^ ((~e) & g);
        const u32 temporary1 = h + sum1 + choose +
                               round_constants[index] + schedule[index];
        const u32 sum0 = rotate_right(a, 2U) ^ rotate_right(a, 13U) ^
                         rotate_right(a, 22U);
        const u32 majority = (a & b) ^ (a & c) ^ (b & c);
        const u32 temporary2 = sum0 + majority;
        h = g;
        g = f;
        f = e;
        e = d + temporary1;
        d = c;
        c = b;
        b = a;
        a = temporary1 + temporary2;
    }

    context->state[0] += a;
    context->state[1] += b;
    context->state[2] += c;
    context->state[3] += d;
    context->state[4] += e;
    context->state[5] += f;
    context->state[6] += g;
    context->state[7] += h;
}

void sha256_init(sha256_context_t *context)
{
    context->state[0] = 0x6a09e667U;
    context->state[1] = 0xbb67ae85U;
    context->state[2] = 0x3c6ef372U;
    context->state[3] = 0xa54ff53aU;
    context->state[4] = 0x510e527fU;
    context->state[5] = 0x9b05688cU;
    context->state[6] = 0x1f83d9abU;
    context->state[7] = 0x5be0cd19U;
    context->bit_count = 0U;
    context->buffer_used = 0U;
}

void sha256_update(sha256_context_t *context, const void *data, usize size)
{
    const u8 *bytes = (const u8 *)data;
    if (size == 0U) {
        return;
    }
    context->bit_count += (u64)size * 8ULL;
    while (size != 0U) {
        usize available = 64U - context->buffer_used;
        usize take = size < available ? size : available;
        fm_memcpy(&context->buffer[context->buffer_used], bytes, take);
        context->buffer_used += take;
        bytes += take;
        size -= take;
        if (context->buffer_used == 64U) {
            transform(context, context->buffer);
            context->buffer_used = 0U;
        }
    }
}

void sha256_final(sha256_context_t *context, u8 digest[32])
{
    context->buffer[context->buffer_used++] = 0x80U;
    if (context->buffer_used > 56U) {
        while (context->buffer_used < 64U) {
            context->buffer[context->buffer_used++] = 0U;
        }
        transform(context, context->buffer);
        context->buffer_used = 0U;
    }
    while (context->buffer_used < 56U) {
        context->buffer[context->buffer_used++] = 0U;
    }
    const u64 bits = context->bit_count;
    for (usize index = 0U; index < 8U; ++index) {
        context->buffer[63U - index] = (u8)(bits >> (index * 8U));
    }
    transform(context, context->buffer);
    for (usize index = 0U; index < 8U; ++index) {
        store_be32(&digest[index * 4U], context->state[index]);
    }
    fm_memset(context, 0, sizeof(*context));
}

void sha256_compute(const void *data, usize size, u8 digest[32])
{
    sha256_context_t context;
    sha256_init(&context);
    sha256_update(&context, data, size);
    sha256_final(&context, digest);
}

bool sha256_digest_equal(const u8 left[32], const u8 right[32])
{
    u8 difference = 0U;
    for (usize index = 0U; index < 32U; ++index) {
        difference |= left[index] ^ right[index];
    }
    return difference == 0U;
}
