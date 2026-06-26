#pragma once
#include "fbr34ker/types.h"

u32 crc32_begin(void);
u32 crc32_update(u32 crc, const void *data, usize size);
u32 crc32_finish(u32 crc);
u32 crc32_compute(const void *data, usize size);
