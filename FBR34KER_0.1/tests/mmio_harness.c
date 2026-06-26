#include "fbr34ker/mmio.h"
#include "fbr34ker/types.h"

static u8 storage[256];

static bool backend_read(u64 address, u32 width, u64 *value, void *context)
{
    UNUSED(context);
    if (address < 0x1000U || address + width > 0x1100U || value == NULL) return false;
    const u32 offset = (u32)(address - 0x1000U);
    u64 result = 0U;
    for (u32 index = 0U; index < width; ++index) result |= (u64)storage[offset + index] << (index * 8U);
    *value = result;
    return true;
}

static bool backend_write(u64 address, u32 width, u64 value, void *context)
{
    UNUSED(context);
    if (address < 0x1000U || address + width > 0x1100U) return false;
    const u32 offset = (u32)(address - 0x1000U);
    for (u32 index = 0U; index < width; ++index) storage[offset + index] = (u8)(value >> (index * 8U));
    return true;
}

int main(void)
{
    mmio_init(false);
    mmio_set_backend(backend_read, backend_write, NULL);
    if (!mmio_register_window("test", 0x1000U, 0x100U,
                              FBR34KER_MMIO_READ | FBR34KER_MMIO_WRITE |
                              FBR34KER_MMIO_PROBE_SAFE, 0x0fU)) return 1;
    if (mmio_register_window("overlap", 0x1080U, 0x20U,
                             FBR34KER_MMIO_READ, 0x04U)) return 2;
    if (!mmio_write32(0x1010U, 0x11223344U)) return 3;
    u32 value = 0U;
    if (!mmio_read32(0x1010U, &value) || value != 0x11223344U) return 4;
    if (!mmio_update32(0x1010U, 0x00ff0000U, 0x00550000U, &value) ||
        value != 0x11553344U) return 5;
    if (mmio_read32(0x10ffU, &value)) return 6;
    if (!mmio_address_allowed(0x1000U, 4U, false, true)) return 7;
    fbr34ker_mmio_stats_t stats = mmio_stats();
    if (stats.reads != 2U || stats.writes != 2U || stats.rejected == 0U) return 8;
    mmio_init(true);
    mmio_set_backend(backend_read, backend_write, NULL);
    if (!mmio_register_window("locked", 0x1000U, 0x100U,
                              FBR34KER_MMIO_READ | FBR34KER_MMIO_WRITE, 0x0fU)) return 9;
    if (mmio_write32(0x1000U, 1U)) return 10;
    if (!mmio_read32(0x1000U, &value)) return 11;
    return mmio_healthy() ? 0 : 12;
}
