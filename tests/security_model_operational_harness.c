#include "fbr34ker/event.h"
#include "fbr34ker/fault.h"
#include "fbr34ker/kernel_patches.h"
#include "fbr34ker/log.h"
#include "fbr34ker/mmio.h"

#include <stdarg.h>

#define TEST_BASE 0x00100000ULL
#define TEST_SIZE 0x02000000ULL

static bool fail_writes;
static u64 last_write_address;
static u64 last_write_value;

bool event_bus_publish(fbr34ker_event_type_t type, const char *source,
                       u64 value0, u64 value1)
{
    UNUSED(type);
    UNUSED(source);
    UNUSED(value0);
    UNUSED(value1);
    return true;
}

bool fault_injection_should_fail(fbr34ker_fault_point_t point,
                                 const char *source)
{
    UNUSED(point);
    UNUSED(source);
    return false;
}

void log_write(log_level_t level, const char *format, ...)
{
    UNUSED(level);
    UNUSED(format);
}

static bool test_read(u64 address, u32 width, u64 *value, void *context)
{
    static const char marker[] = "Darwin Kernel Version 23.0.0";
    UNUSED(context);
    if (value == NULL || width != 4U || address < TEST_BASE) {
        return false;
    }
    *value = 0U;
    const u64 offset = address - TEST_BASE;
    for (u32 index = 0U; index < 4U; ++index) {
        const u64 position = offset + index;
        if (position < sizeof(marker)) {
            *value |= (u64)(u8)marker[position] << (index * 8U);
        }
    }
    return true;
}

static bool test_write(u64 address, u32 width, u64 value, void *context)
{
    UNUSED(context);
    if (fail_writes || width != 4U) {
        return false;
    }
    last_write_address = address;
    last_write_value = value;
    return true;
}

int main(void)
{
    mmio_init(false);
    if (!mmio_register_window(
            "test-memory", TEST_BASE, TEST_SIZE,
            FBR34KER_MMIO_READ | FBR34KER_MMIO_WRITE |
                FBR34KER_MMIO_PROBE_SAFE,
            1U << 2)) {
        return 1;
    }
    mmio_set_backend(test_read, test_write, NULL);
    if (!kernel_patches_set_soc(0x8020U, TEST_BASE)) return 2;
    kernel_patches_init();

    kernel_patches_status_t status = kernel_patches_status();
    if (status.patch_count == 0U) return 3;
    if (status.patches[0].target_address != TEST_BASE + 0x00B00000ULL) {
        return 4;
    }

    const u32 success_index = status.patch_count;
    if (!kernel_patches_register(
            "write-success", KERNEL_PATCH_TYPE_MEMORY, TEST_BASE + 0x1000U,
            4U, 0x11223344U, 0xAABBCCDDU, false)) {
        return 5;
    }
    if (!kernel_patches_apply_single(success_index)) return 6;
    if (last_write_address != TEST_BASE + 0x1000U ||
        last_write_value != 0xAABBCCDDU) {
        return 7;
    }
    if (!kernel_patches_revert_single(success_index)) return 8;
    if (last_write_value != 0x11223344U) return 9;

    status = kernel_patches_status();
    const u32 failure_index = status.patch_count;
    if (!kernel_patches_register(
            "write-failure", KERNEL_PATCH_TYPE_MEMORY, TEST_BASE + 0x1004U,
            4U, 0U, 1U, false)) {
        return 10;
    }
    fail_writes = true;
    if (kernel_patches_apply_single(failure_index)) return 11;
    status = kernel_patches_status();
    if (status.patches[failure_index].applied ||
        status.patches[failure_index].state != KERNEL_PATCH_STATE_FAILED ||
        status.failed_count == 0U) {
        return 12;
    }
    return 0;
}
