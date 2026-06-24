#include "fbr34ker/allocator.h"
#include "fbr34ker/types.h"

u8 __heap_start[1];
u8 __heap_end[1];

static ALIGNED(4096) u8 test_heap[64U * 1024U];

static int require(bool condition, int code)
{
    return condition ? 0 : code;
}

int main(void)
{
    if (require(!allocator_init_region(NULL, sizeof(test_heap)), 1) != 0 ||
        require(allocator_init_region(test_heap, sizeof(test_heap)), 2) != 0 ||
        require(allocator_check(), 3) != 0) {
        return 1;
    }

    void *first = allocator_alloc(37U, 16U);
    void *second = allocator_alloc(128U, 64U);
    if (first == NULL || second == NULL ||
        ((usize)first & 15U) != 0U || ((usize)second & 63U) != 0U ||
        !allocator_check()) {
        return 2;
    }

    if (!allocator_free(first) || allocator_free(first)) {
        return 3;
    }
    allocator_stats_t stats = allocator_stats();
    if (stats.double_frees != 1U || stats.active_allocations != 1U ||
        !allocator_check()) {
        return 4;
    }

    u8 outside = 0U;
    if (allocator_free(&outside)) {
        return 5;
    }

    if (!allocator_init_region(test_heap, sizeof(test_heap))) {
        return 6;
    }
    u8 *guarded = (u8 *)allocator_alloc(8U, 8U);
    if (guarded == NULL) {
        return 7;
    }
    guarded[8] ^= 1U;
    if (allocator_check()) {
        return 8;
    }

    if (!allocator_init_region(test_heap, sizeof(test_heap)) ||
        allocator_alloc(1U, 3U) != NULL ||
        allocator_alloc(0U, 1U) != NULL) {
        return 9;
    }
    return 0;
}
