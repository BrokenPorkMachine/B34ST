#include "fbr34ker/trust_cache.h"
#include "fbr34ker/kernel_patches.h"
#include "fbr34ker/mmio.h"
#include "fbr34ker/log.h"
#include "fbr34ker/string.h"
#include "fbr34ker/event.h"
#include "fbr34ker/apple_platform.h"

// SPDX-License-Identifier: BSD-2-Clause
static trust_cache_status_t state;

static u32 trust_cache_entry_size(u32 version)
{
    switch (version) {
    case TRUST_CACHE_VERSION_0:
        return TRUST_CACHE_CDHASH_SIZE;
    case TRUST_CACHE_VERSION_1:
        return sizeof(trust_cache_entry_v1_t);
    default:
        return TRUST_CACHE_CDHASH_SIZE;
    }
}

static bool is_valid_tc_header(const trust_cache_header_t *hdr, usize max_size)
{
    if (hdr == NULL) return false;
    if (hdr->version != TRUST_CACHE_VERSION_0 &&
        hdr->version != TRUST_CACHE_VERSION_1) {
        return false;
    }
    u32 entry_sz = trust_cache_entry_size(hdr->version);
    u64 allocation = (u64)sizeof(trust_cache_header_t) + ((u64)hdr->num_entries * (u64)entry_sz);
    if (allocation > max_size) return false;
    if (hdr->num_entries == 0U || hdr->num_entries > 4096U) return false;
    return true;
}

typedef struct {
    u64 start;
    u64 end;
} mem_region_t;

static const mem_region_t scan_regions[] = {
    { 0x800000000ULL, 0x800400000ULL },
    { 0xfffffff007000000ULL, 0xfffffff00f000000ULL },
};

static bool scan_kernel_for_tc_anchor(void)
{
    log_write(LOG_LEVEL_INFO, "trust_cache: scanning kernel memory for anchor");
    for (usize r = 0U; r < sizeof(scan_regions) / sizeof(scan_regions[0U]); ++r) {
        u64 base = scan_regions[r].start;
        u64 end = scan_regions[r].end;
        for (u64 addr = base; addr < end; addr += TRUST_CACHE_SCAN_ALIGN) {
            trust_cache_header_t hdr;
            fm_memset(&hdr, 0, sizeof(hdr));
            for (u32 b = 0U; b < sizeof(hdr); ++b) {
                u32 word = 0U;
                if (mmio_read32(addr + b, &word)) {
                    ((u8 *)&hdr)[b] = (u8)(word & 0xFF);
                }
            }
            if (is_valid_tc_header(&hdr, (usize)(end - addr))) {
                log_write(LOG_LEVEL_INFO,
                          "trust_cache: found anchor at 0x%llx (ver=%u, entries=%u)",
                          addr, (unsigned)hdr.version, (unsigned)hdr.num_entries);
                state.anchor_address = addr;
                return true;
            }
        }
    }
    log_write(LOG_LEVEL_WARN, "trust_cache: anchor not found in scan regions");
    return false;
}

static u64 allocate_in_kernel(usize size)
{
    u64 alloc_base = state.anchor_address;
    if (alloc_base == 0U) return 0U;
    u64 scan_start = alloc_base + (0x100000ULL);
    for (usize i = 0U; i < 256U; ++i) {
        u64 addr = scan_start + (i * 0x1000ULL);
        u32 word = 0U;
        if (!mmio_read32(addr, &word)) continue;
        bool in_use = false;
        for (u32 off = 0U; off < size; off += 4U) {
            u32 val = 0U;
            if (mmio_read32(addr + off, &val) && val != 0U) {
                in_use = true;
                break;
            }
        }
        if (!in_use) {
            log_write(LOG_LEVEL_VERBOSE,
                      "trust_cache: allocated 0x%llx bytes at 0x%llx",
                      (u64)size, addr);
            return addr;
        }
    }
    log_write(LOG_LEVEL_WARN, "trust_cache: no free kernel memory found");
    return 0U;
}

static bool write_trust_cache_to_kernel(u64 dest, const trust_cache_header_t *hdr,
                                         u32 num_entries, u32 entry_sz)
{
    u8 *data = (u8 *)hdr;
    usize total = sizeof(trust_cache_header_t) + ((usize)num_entries * entry_sz);
    for (usize off = 0U; off < total; off += 4U) {
        u32 val = 0U;
        for (u32 b = 0U; b < 4U && (off + b) < total; ++b) {
            val |= ((u32)data[off + b]) << (b * 8U);
        }
        if (!mmio_write32(dest + off, val)) {
            log_write(LOG_LEVEL_ERROR,
                      "trust_cache: write failed at 0x%llx", dest + off);
            return false;
        }
    }
    return true;
}

static bool link_trust_cache_chain(u64 new_cache_addr)
{
    u64 anchor = state.anchor_address;
    if (anchor == 0U || new_cache_addr == 0U) return false;
    u64 next_ptr_addr = anchor;
    u64 max_depth = 32U;
    for (u64 d = 0U; d < max_depth; ++d) {
        u32 low = 0U, high = 0U;
        if (!mmio_read32(next_ptr_addr, &low) ||
            !mmio_read32(next_ptr_addr + 4U, &high)) {
            break;
        }
        u64 next = ((u64)high << 32U) | (u64)low;
        if (next == 0U) {
            u32 low_new = (u32)(new_cache_addr & 0xFFFFFFFFULL);
            u32 high_new = (u32)((new_cache_addr >> 32U) & 0xFFFFFFFFULL);
            if (!mmio_write32(next_ptr_addr, low_new)) return false;
            if (!mmio_write32(next_ptr_addr + 4U, high_new)) return false;
            log_write(LOG_LEVEL_INFO,
                      "trust_cache: linked new cache at 0x%llx", new_cache_addr);
            return true;
        }
        if (next == new_cache_addr) {
            log_write(LOG_LEVEL_VERBOSE,
                      "trust_cache: already linked at depth %llu", d);
            return true;
        }
        u32 tc_version = 0U, tc_num_entries = 0U;
        mmio_read32(next, &tc_version);
        mmio_read32(next + 4U, &tc_num_entries);
        u32 entry_sz = trust_cache_entry_size(tc_version);
        u64 alloc = (u64)sizeof(trust_cache_header_t) + ((u64)tc_num_entries * (u64)entry_sz);
        next_ptr_addr = next + (u64)alloc;
    }
    log_write(LOG_LEVEL_WARN,
              "trust_cache: chain too deep or circular at anchor 0x%llx", anchor);
    return false;
}

void trust_cache_init(void)
{
    fm_memset(&state, 0, sizeof(state));
    state.state = TRUST_CACHE_STATE_INACTIVE;
    log_write(LOG_LEVEL_INFO, "trust_cache: initialized (%u max slots)",
              TRUST_CACHE_MAX_ENTRIES);
    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE,
                            "trust-cache", 0U, 0U);
}

trust_cache_status_t trust_cache_get_status(void)
{
    return state;
}

bool trust_cache_register_entry(const char *name,
                                 const u8 cdhash[TRUST_CACHE_CDHASH_SIZE],
                                 trust_cache_hash_type_t hash_type)
{
    if (state.slot_count >= TRUST_CACHE_MAX_ENTRIES || cdhash == NULL) {
        return false;
    }
    trust_cache_slot_t *slot = &state.slots[state.slot_count];
    if (name != NULL) {
        fm_strlcpy(slot->name, name, sizeof(slot->name));
    } else {
        fm_strlcpy(slot->name, "tc-entry", sizeof(slot->name));
    }
    fm_memcpy(slot->entry.cdhash, cdhash, TRUST_CACHE_CDHASH_SIZE);
    slot->entry.hash_type = (u8)hash_type;
    slot->entry.flags = 0U;
    slot->state = TRUST_CACHE_STATE_INACTIVE;
    slot->injected = false;
    ++state.slot_count;
    log_write(LOG_LEVEL_INFO,
              "trust_cache: registered '%s' hash_type=%u",
              slot->name, (unsigned)slot->entry.hash_type);
    return true;
}

bool trust_cache_find_anchor(void)
{
    if (state.anchor_address != 0U) return true;
    return scan_kernel_for_tc_anchor();
}

bool trust_cache_inject_all(void)
{
    if (state.slot_count == 0U) {
        log_write(LOG_LEVEL_WARN, "trust_cache: no entries to inject");
        return false;
    }
    if (!trust_cache_find_anchor()) {
        log_write(LOG_LEVEL_ERROR, "trust_cache: cannot inject without anchor");
        state.state = TRUST_CACHE_STATE_FAILED;
        return false;
    }
    u32 entry_sz = sizeof(trust_cache_entry_v1_t);
    u32 num_entries = state.slot_count;
    usize cache_size = sizeof(trust_cache_header_t) + ((usize)num_entries * entry_sz);
    u64 cache_addr = allocate_in_kernel(cache_size);
    if (cache_addr == 0U) {
        log_write(LOG_LEVEL_ERROR, "trust_cache: allocation failed (%llu bytes)",
                  (u64)cache_size);
        state.state = TRUST_CACHE_STATE_FAILED;
        return false;
    }
    trust_cache_header_t hdr;
    fm_memset(&hdr, 0, sizeof(hdr));
    hdr.version = TRUST_CACHE_VERSION_1;
    hdr.num_entries = num_entries;
    trust_cache_entry_v1_t entries[TRUST_CACHE_MAX_ENTRIES];
    fm_memset(entries, 0, sizeof(entries));
    for (u32 i = 0U; i < num_entries; ++i) {
        fm_memcpy(entries[i].cdhash, state.slots[i].entry.cdhash,
                  TRUST_CACHE_CDHASH_SIZE);
        entries[i].hash_type = state.slots[i].entry.hash_type;
        entries[i].flags = 0U;
    }
    if (!write_trust_cache_to_kernel(cache_addr, &hdr,
                                      num_entries, entry_sz)) {
        log_write(LOG_LEVEL_ERROR, "trust_cache: kernel write failed");
        state.state = TRUST_CACHE_STATE_FAILED;
        return false;
    }
    if (!link_trust_cache_chain(cache_addr)) {
        log_write(LOG_LEVEL_WARN, "trust_cache: chain link failed");
    }
    for (u32 i = 0U; i < num_entries; ++i) {
        state.slots[i].state = TRUST_CACHE_STATE_ACTIVE;
        state.slots[i].injected = true;
    }
    state.injected_count = num_entries;
    state.state = TRUST_CACHE_STATE_ACTIVE;
    log_write(LOG_LEVEL_INFO,
              "trust_cache: injected %u entries at 0x%llx",
              (unsigned)num_entries, cache_addr);
    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE,
                            "trust-cache-inject", num_entries, 0U);
    return true;
}

u64 trust_cache_get_anchor(void)
{
    return state.anchor_address;
}

bool trust_cache_available(void)
{
    return state.slot_count > 0U;
}

u32 trust_cache_entry_count(void)
{
    return state.slot_count;
}
