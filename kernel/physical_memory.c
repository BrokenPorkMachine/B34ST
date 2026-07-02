#include "fbr34ker/physical_memory.h"
#include "fbr34ker/device_tree.h"
#include "fbr34ker/platform.h"
#include "fbr34ker/string.h"

// SPDX-License-Identifier: BSD-2-Clause
typedef struct {
    fbr34ker_pmm_range_t range;
    bool active;
} allocation_slot_t;

static fbr34ker_pmm_range_t usable[FBR34KER_PMM_MAX_USABLE_RANGES];
static fbr34ker_pmm_range_t reserved[FBR34KER_PMM_MAX_RESERVED_RANGES];
static allocation_slot_t allocations[FBR34KER_PMM_MAX_ALLOCATIONS];
static fbr34ker_pmm_stats_t statistics;

static void copy_text(char *destination, usize capacity, const char *source)
{
    usize index = 0U;
    if (destination == NULL || capacity == 0U) return;
    if (source != NULL) {
        while (index + 1U < capacity && source[index] != '\0') {
            destination[index] = source[index];
            ++index;
        }
    }
    destination[index] = '\0';
}

static bool range_end(u64 base, u64 size, u64 *end)
{
    return size != 0U && u64_add_checked(base, size, end);
}

static bool overlaps(u64 first_base, u64 first_size,
                     u64 second_base, u64 second_size)
{
    u64 first_end;
    u64 second_end;
    return range_end(first_base, first_size, &first_end) &&
           range_end(second_base, second_size, &second_end) &&
           first_base < second_end && second_base < first_end;
}

static bool contains_range(const fbr34ker_pmm_range_t *outer,
                           u64 base, u64 size)
{
    u64 end;
    u64 outer_end;
    return outer != NULL && range_end(base, size, &end) &&
           range_end(outer->base, outer->size, &outer_end) &&
           base >= outer->base && end <= outer_end;
}

static u64 align_down(u64 value, u64 alignment)
{
    return value & ~(alignment - 1U);
}

static bool align_up(u64 value, u64 alignment, u64 *result)
{
    const u64 mask = alignment - 1U;
    u64 adjusted;
    if (result == NULL || (alignment & mask) != 0U ||
        !u64_add_checked(value, mask, &adjusted)) return false;
    *result = adjusted & ~mask;
    return true;
}

static const char *platform_region_tag(memory_region_type_t type)
{
    switch (type) {
    case MEMORY_REGION_USABLE: return "platform-usable";
    case MEMORY_REGION_RESERVED: return "platform-reserved";
    case MEMORY_REGION_MMIO: return "platform-mmio";
    case MEMORY_REGION_MONITOR: return "monitor-image";
    case MEMORY_REGION_FRAMEBUFFER: return "framebuffer";
    default: return "platform-region";
    }
}

void physical_memory_init(void)
{
    fm_memset(usable, 0, sizeof(usable));
    fm_memset(reserved, 0, sizeof(reserved));
    fm_memset(allocations, 0, sizeof(allocations));
    fm_memset(&statistics, 0, sizeof(statistics));
    statistics.initialized = true;

    const memory_region_t *regions = NULL;
    const u64 count = platform_memory_regions(&regions);
    for (u64 index = 0U; index < count; ++index) {
        if (regions[index].type == MEMORY_REGION_USABLE) {
            if (!physical_memory_add_usable(regions[index].base,
                                            regions[index].size,
                                            regions[index].name != NULL
                                                ? regions[index].name
                                                : "platform-usable")) {
                statistics.initialized = false;
                return;
            }
        }
    }
    for (u64 index = 0U; index < count; ++index) {
        if (regions[index].type != MEMORY_REGION_USABLE &&
            !physical_memory_reserve(regions[index].base, regions[index].size,
                                     regions[index].name != NULL
                                         ? regions[index].name
                                         : platform_region_tag(regions[index].type))) {
            statistics.initialized = false;
            return;
        }
    }
    if (device_tree_valid()) {
        const u32 reservation_count = device_tree_reservation_count();
        for (u32 index = 0U; index < reservation_count; ++index) {
            u64 base;
            u64 size;
            if (device_tree_reservation_at(index, &base, &size) && size != 0U) {
                (void)physical_memory_reserve(base, size, "dtb-reserved");
            }
        }
    }
}

void physical_memory_shutdown(void)
{
    fm_memset(usable, 0, sizeof(usable));
    fm_memset(reserved, 0, sizeof(reserved));
    fm_memset(allocations, 0, sizeof(allocations));
    fm_memset(&statistics, 0, sizeof(statistics));
}

bool physical_memory_ready(void) { return statistics.initialized; }

bool physical_memory_add_usable(u64 base, u64 size, const char *tag)
{
    if (!statistics.initialized || size == 0U ||
        statistics.usable_ranges >= FBR34KER_PMM_MAX_USABLE_RANGES) return false;
    u64 end;
    u64 aligned_base;
    if (!range_end(base, size, &end) ||
        !align_up(base, FBR34KER_PMM_PAGE_SIZE, &aligned_base)) return false;
    const u64 aligned_end = align_down(end, FBR34KER_PMM_PAGE_SIZE);
    if (aligned_end <= aligned_base) return false;
    const u64 aligned_size = aligned_end - aligned_base;
    for (u32 index = 0U; index < statistics.usable_ranges; ++index) {
        if (overlaps(aligned_base, aligned_size,
                     usable[index].base, usable[index].size)) return false;
    }
    fbr34ker_pmm_range_t *range = &usable[statistics.usable_ranges++];
    range->base = aligned_base;
    range->size = aligned_size;
    copy_text(range->tag, sizeof(range->tag), tag);
    statistics.usable_bytes += aligned_size;
    statistics.free_bytes += aligned_size;
    return true;
}

bool physical_memory_reserve(u64 base, u64 size, const char *tag)
{
    if (!statistics.initialized || size == 0U) return false;
    u64 end;
    if (!range_end(base, size, &end)) return false;
    const u64 aligned_base = align_down(base, FBR34KER_PMM_PAGE_SIZE);
    u64 aligned_end;
    if (!align_up(end, FBR34KER_PMM_PAGE_SIZE, &aligned_end) ||
        aligned_end <= aligned_base) return false;
    const u64 aligned_size = aligned_end - aligned_base;
    for (u32 index = 0U; index < statistics.reserved_ranges; ++index) {
        if (contains_range(&reserved[index], aligned_base, aligned_size)) return true;
        if (overlaps(aligned_base, aligned_size,
                     reserved[index].base, reserved[index].size)) return false;
    }
    if (statistics.reserved_ranges >= FBR34KER_PMM_MAX_RESERVED_RANGES) return false;
    fbr34ker_pmm_range_t *range = &reserved[statistics.reserved_ranges++];
    range->base = aligned_base;
    range->size = aligned_size;
    copy_text(range->tag, sizeof(range->tag), tag);
    statistics.reserved_bytes += aligned_size;
    u64 overlap_bytes = 0U;
    for (u32 index = 0U; index < statistics.usable_ranges; ++index) {
        const u64 start = aligned_base > usable[index].base ? aligned_base : usable[index].base;
        const u64 reservation_end = aligned_base + aligned_size;
        const u64 usable_end = usable[index].base + usable[index].size;
        const u64 stop = reservation_end < usable_end ? reservation_end : usable_end;
        if (stop > start) overlap_bytes += stop - start;
    }
    statistics.free_bytes = overlap_bytes <= statistics.free_bytes
        ? statistics.free_bytes - overlap_bytes : 0U;
    return true;
}

static bool candidate_free(u64 base, u64 size)
{
    for (u32 index = 0U; index < statistics.reserved_ranges; ++index) {
        if (overlaps(base, size, reserved[index].base, reserved[index].size)) return false;
    }
    for (u32 index = 0U; index < FBR34KER_PMM_MAX_ALLOCATIONS; ++index) {
        if (allocations[index].active &&
            overlaps(base, size, allocations[index].range.base,
                     allocations[index].range.size)) return false;
    }
    return true;
}

bool physical_memory_allocate_pages(u32 page_count, u32 alignment_pages,
                                    const char *tag, u64 *base)
{
    ++statistics.allocation_attempts;
    if (!statistics.initialized || base == NULL || page_count == 0U) {
        ++statistics.allocation_failures;
        return false;
    }
    if (alignment_pages == 0U) alignment_pages = 1U;
    if ((alignment_pages & (alignment_pages - 1U)) != 0U) {
        ++statistics.allocation_failures;
        return false;
    }
    const u64 bytes = (u64)page_count * FBR34KER_PMM_PAGE_SIZE;
    const u64 alignment = (u64)alignment_pages * FBR34KER_PMM_PAGE_SIZE;
    u32 slot = FBR34KER_PMM_MAX_ALLOCATIONS;
    for (u32 index = 0U; index < FBR34KER_PMM_MAX_ALLOCATIONS; ++index) {
        if (!allocations[index].active) { slot = index; break; }
    }
    if (slot == FBR34KER_PMM_MAX_ALLOCATIONS) {
        ++statistics.allocation_failures;
        return false;
    }
    for (u32 range_index = 0U; range_index < statistics.usable_ranges; ++range_index) {
        const fbr34ker_pmm_range_t *range = &usable[range_index];
        u64 candidate;
        if (!align_up(range->base, alignment, &candidate)) continue;
        const u64 limit = range->base + range->size;
        while (candidate <= limit && bytes <= limit - candidate) {
            if (candidate_free(candidate, bytes)) {
                allocations[slot].active = true;
                allocations[slot].range.base = candidate;
                allocations[slot].range.size = bytes;
                copy_text(allocations[slot].range.tag,
                          sizeof(allocations[slot].range.tag), tag);
                ++statistics.active_allocations;
                statistics.allocated_bytes += bytes;
                statistics.free_bytes = bytes <= statistics.free_bytes
                    ? statistics.free_bytes - bytes : 0U;
                *base = candidate;
                return true;
            }
            if (candidate > U64_MAX_VALUE - alignment) break;
            candidate += alignment;
        }
    }
    ++statistics.allocation_failures;
    return false;
}

bool physical_memory_free_pages(u64 base, u32 page_count)
{
    if (!statistics.initialized || page_count == 0U) return false;
    const u64 bytes = (u64)page_count * FBR34KER_PMM_PAGE_SIZE;
    for (u32 index = 0U; index < FBR34KER_PMM_MAX_ALLOCATIONS; ++index) {
        if (allocations[index].active && allocations[index].range.base == base &&
            allocations[index].range.size == bytes) {
            allocations[index].active = false;
            --statistics.active_allocations;
            statistics.allocated_bytes -= bytes;
            statistics.free_bytes += bytes;
            return true;
        }
    }
    return false;
}

bool physical_memory_healthy(void)
{
    if (!statistics.initialized ||
        statistics.usable_ranges > FBR34KER_PMM_MAX_USABLE_RANGES ||
        statistics.reserved_ranges > FBR34KER_PMM_MAX_RESERVED_RANGES ||
        statistics.active_allocations > FBR34KER_PMM_MAX_ALLOCATIONS) return false;
    u32 active = 0U;
    u64 allocated = 0U;
    for (u32 index = 0U; index < FBR34KER_PMM_MAX_ALLOCATIONS; ++index) {
        if (!allocations[index].active) continue;
        ++active;
        allocated += allocations[index].range.size;
        bool within_usable = false;
        for (u32 range_index = 0U; range_index < statistics.usable_ranges; ++range_index) {
            if (contains_range(&usable[range_index], allocations[index].range.base,
                               allocations[index].range.size)) {
                within_usable = true;
                break;
            }
        }
        if (!within_usable || !candidate_free(allocations[index].range.base,
                                              allocations[index].range.size)) {
            /* candidate_free sees this allocation itself; validate manually below. */
            for (u32 reserved_index = 0U; reserved_index < statistics.reserved_ranges;
                 ++reserved_index) {
                if (overlaps(allocations[index].range.base,
                             allocations[index].range.size,
                             reserved[reserved_index].base,
                             reserved[reserved_index].size)) return false;
            }
        }
        for (u32 other = index + 1U; other < FBR34KER_PMM_MAX_ALLOCATIONS; ++other) {
            if (allocations[other].active &&
                overlaps(allocations[index].range.base, allocations[index].range.size,
                         allocations[other].range.base, allocations[other].range.size)) return false;
        }
    }
    return active == statistics.active_allocations &&
           allocated == statistics.allocated_bytes;
}

u32 physical_memory_usable_count(void) { return statistics.usable_ranges; }
u32 physical_memory_reserved_count(void) { return statistics.reserved_ranges; }
u32 physical_memory_allocation_count(void) { return statistics.active_allocations; }

bool physical_memory_usable_at(u32 index, fbr34ker_pmm_range_t *range)
{
    if (range == NULL || index >= statistics.usable_ranges) return false;
    *range = usable[index]; return true;
}

bool physical_memory_reserved_at(u32 index, fbr34ker_pmm_range_t *range)
{
    if (range == NULL || index >= statistics.reserved_ranges) return false;
    *range = reserved[index]; return true;
}

bool physical_memory_allocation_at(u32 index, fbr34ker_pmm_range_t *range)
{
    if (range == NULL) return false;
    u32 occurrence = 0U;
    for (u32 slot = 0U; slot < FBR34KER_PMM_MAX_ALLOCATIONS; ++slot) {
        if (!allocations[slot].active) continue;
        if (occurrence++ == index) { *range = allocations[slot].range; return true; }
    }
    return false;
}

fbr34ker_pmm_stats_t physical_memory_stats(void) { return statistics; }
