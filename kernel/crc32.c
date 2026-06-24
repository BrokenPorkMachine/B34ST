#include "fbr34ker/crc32.h"

u32 crc32_begin(void)
{
    return 0xffffffffU;
}

u32 crc32_update(u32 crc, const void *data, usize size)
{
    const u8 *bytes = (const u8 *)data;
    for (usize index = 0U; index < size; ++index) {
        crc ^= bytes[index];
        for (u32 bit = 0U; bit < 8U; ++bit) {
            const u32 mask = (u32)-(i32)(crc & 1U);
            crc = (crc >> 1U) ^ (0xedb88320U & mask);
        }
    }
    return crc;
}

u32 crc32_finish(u32 crc)
{
    return crc ^ 0xffffffffU;
}

u32 crc32_compute(const void *data, usize size)
{
    return crc32_finish(crc32_update(crc32_begin(), data, size));
}
