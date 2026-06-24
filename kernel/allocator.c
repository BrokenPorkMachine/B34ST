#include "fbr34ker/allocator.h"
#include "fbr34ker/string.h"

#define ALLOCATION_MAGIC 0x46414c4c4f433031ULL
#define ALLOCATION_STATE_ACTIVE 0xa110ca7eU
#define ALLOCATION_STATE_FREED  0xfee1deadU
#define GUARD_SIZE 16U
#define GUARD_BYTE 0xa5U
#define FREED_BYTE 0xddU
#define INITIAL_BYTE 0xccU

typedef struct allocation_header {
    u64 magic;
    u64 canary;
    usize requested_size;
    usize total_end_offset;
    u32 state;
    u32 reserved;
    struct allocation_header *next;
} allocation_header_t;

extern u8 __heap_start[];
extern u8 __heap_end[];

static u8 *heap_start;
static u8 *heap_end;
static usize current_offset;
static allocation_header_t *first_allocation;
static allocation_header_t *last_allocation;
static allocator_stats_t statistics;

static u64 allocation_canary(const allocation_header_t *header)
{
    return ALLOCATION_MAGIC ^ (u64)(usize)header ^
           (u64)header->requested_size ^ 0x9e3779b97f4a7c15ULL;
}

static bool address_in_heap(usize address, usize size)
{
    if (heap_start == NULL || heap_end == NULL) {
        return false;
    }
    const usize base = (usize)heap_start;
    const usize limit = (usize)heap_end;
    return address >= base && address <= limit && size <= limit - address;
}

static u8 *payload_for(allocation_header_t *header)
{
    return (u8 *)header + sizeof(*header) + GUARD_SIZE;
}

static allocation_header_t *header_for(void *pointer)
{
    if (pointer == NULL || heap_start == NULL) {
        return NULL;
    }
    const usize payload = (usize)pointer;
    const usize prefix = sizeof(allocation_header_t) + GUARD_SIZE;
    const usize base = (usize)heap_start;
    usize minimum_payload;
    if (!usize_add_checked(base, prefix, &minimum_payload) ||
        payload < minimum_payload || payload >= (usize)heap_end) {
        return NULL;
    }
    return (allocation_header_t *)(payload - prefix);
}

static bool bytes_are(const u8 *bytes, usize size, u8 value)
{
    for (usize index = 0U; index < size; ++index) {
        if (bytes[index] != value) {
            return false;
        }
    }
    return true;
}

static bool header_valid(const allocation_header_t *header)
{
    const usize header_address = (usize)header;
    if (header == NULL ||
        !address_in_heap(header_address, sizeof(*header)) ||
        header->magic != ALLOCATION_MAGIC ||
        header->reserved != 0U ||
        header->requested_size == 0U ||
        header->canary != allocation_canary(header)) {
        return false;
    }

    usize payload_address;
    usize guarded_payload_size;
    usize allocation_end;
    if (!usize_add_checked(header_address,
                           sizeof(*header) + GUARD_SIZE,
                           &payload_address) ||
        !usize_add_checked(payload_address, header->requested_size,
                           &allocation_end) ||
        !usize_add_checked(header->requested_size, GUARD_SIZE,
                           &guarded_payload_size) ||
        !usize_add_checked(allocation_end, GUARD_SIZE, &allocation_end) ||
        !address_in_heap(payload_address, guarded_payload_size)) {
        return false;
    }
    const usize expected_offset = allocation_end - (usize)heap_start;
    if (header->total_end_offset != expected_offset ||
        expected_offset > current_offset ||
        header->total_end_offset > statistics.capacity) {
        return false;
    }

    const u8 *payload = (const u8 *)payload_address;
    return bytes_are((const u8 *)header + sizeof(*header), GUARD_SIZE,
                     GUARD_BYTE) &&
           bytes_are(payload + header->requested_size, GUARD_SIZE,
                     GUARD_BYTE);
}

bool allocator_init_region(void *base, usize size)
{
    fm_memset(&statistics, 0, sizeof(statistics));
    current_offset = 0U;
    first_allocation = NULL;
    last_allocation = NULL;
    heap_start = NULL;
    heap_end = NULL;

    if (base == NULL || size < sizeof(allocation_header_t) +
                                  (2U * GUARD_SIZE) + 1U) {
        return false;
    }
    const usize start = (usize)base;
    usize end;
    if (!usize_add_checked(start, size, &end)) {
        return false;
    }
    heap_start = (u8 *)start;
    heap_end = (u8 *)end;
    statistics.capacity = size;
    statistics.remaining = size;
    fm_memset(heap_start, INITIAL_BYTE, size);
    return true;
}

void allocator_init(void)
{
    (void)allocator_init_region(__heap_start,
                                (usize)(__heap_end - __heap_start));
}

static bool align_up_checked(usize value, usize alignment, usize *result)
{
    const usize mask = alignment - 1U;
    usize adjusted;
    if (!usize_add_checked(value, mask, &adjusted)) {
        return false;
    }
    *result = adjusted & ~mask;
    return true;
}

void *allocator_alloc(usize size, usize alignment)
{
    if (heap_start == NULL || size == 0U) {
        ++statistics.failed_allocations;
        return NULL;
    }
    if (alignment == 0U) {
        alignment = 1U;
    }
    if ((alignment & (alignment - 1U)) != 0U || alignment > 4096U) {
        ++statistics.failed_allocations;
        return NULL;
    }

    const usize base = (usize)heap_start;
    const usize limit = (usize)heap_end;
    usize start;
    usize pre_payload;
    usize payload;
    usize end;
    if (!usize_add_checked(base, current_offset, &start) ||
        !usize_add_checked(start, sizeof(allocation_header_t) + GUARD_SIZE,
                           &pre_payload) ||
        !align_up_checked(pre_payload, alignment, &payload) ||
        payload < pre_payload || payload > limit ||
        size > limit - payload ||
        !usize_add_checked(payload, size, &end) ||
        GUARD_SIZE > limit - end ||
        !usize_add_checked(end, GUARD_SIZE, &end)) {
        ++statistics.failed_allocations;
        return NULL;
    }

    const usize header_address = payload - GUARD_SIZE -
                                 sizeof(allocation_header_t);
    if (header_address < start || end < payload) {
        ++statistics.failed_allocations;
        return NULL;
    }

    allocation_header_t *header = (allocation_header_t *)header_address;
    fm_memset(header, 0, sizeof(*header));
    header->magic = ALLOCATION_MAGIC;
    header->requested_size = size;
    header->total_end_offset = end - base;
    header->state = ALLOCATION_STATE_ACTIVE;
    header->canary = allocation_canary(header);
    fm_memset((u8 *)header + sizeof(*header), GUARD_BYTE, GUARD_SIZE);
    fm_memset((void *)payload, 0, size);
    fm_memset((void *)(payload + size), GUARD_BYTE, GUARD_SIZE);

    if (last_allocation != NULL) {
        last_allocation->next = header;
    } else {
        first_allocation = header;
    }
    last_allocation = header;
    current_offset = end - base;
    ++statistics.allocations;
    ++statistics.active_allocations;
    statistics.used = current_offset;
    statistics.remaining = statistics.capacity - current_offset;
    return (void *)payload;
}

bool allocator_free(void *pointer)
{
    allocation_header_t *header = header_for(pointer);
    if (!header_valid(header)) {
        ++statistics.corruptions;
        return false;
    }
    if (header->state == ALLOCATION_STATE_FREED) {
        ++statistics.double_frees;
        return false;
    }
    if (header->state != ALLOCATION_STATE_ACTIVE) {
        ++statistics.corruptions;
        return false;
    }
    fm_memset(pointer, FREED_BYTE, header->requested_size);
    header->state = ALLOCATION_STATE_FREED;
    --statistics.active_allocations;
    ++statistics.frees;
    return true;
}

bool allocator_check(void)
{
    if (heap_start == NULL || current_offset > statistics.capacity ||
        statistics.used != current_offset ||
        statistics.remaining != statistics.capacity - current_offset) {
        ++statistics.corruptions;
        return false;
    }

    usize visited = 0U;
    usize active = 0U;
    allocation_header_t *previous = NULL;
    for (allocation_header_t *header = first_allocation;
         header != NULL; header = header->next) {
        if (++visited > statistics.allocations || !header_valid(header) ||
            (previous != NULL && (usize)header <= (usize)previous) ||
            (header->state != ALLOCATION_STATE_ACTIVE &&
             header->state != ALLOCATION_STATE_FREED)) {
            ++statistics.corruptions;
            return false;
        }
        if (header->state == ALLOCATION_STATE_ACTIVE) {
            ++active;
        } else if (!bytes_are(payload_for(header), header->requested_size,
                              FREED_BYTE)) {
            ++statistics.corruptions;
            return false;
        }
        if (header->next != NULL &&
            !address_in_heap((usize)header->next, sizeof(*header->next))) {
            ++statistics.corruptions;
            return false;
        }
        previous = header;
    }

    if (visited != statistics.allocations ||
        active != statistics.active_allocations ||
        (visited == 0U && last_allocation != NULL) ||
        (visited != 0U && previous != last_allocation)) {
        ++statistics.corruptions;
        return false;
    }
    return true;
}

allocator_stats_t allocator_stats(void)
{
    return statistics;
}

u64 allocator_base(void)
{
    return (u64)(usize)heap_start;
}

u64 allocator_limit(void)
{
    return (u64)(usize)heap_end;
}
