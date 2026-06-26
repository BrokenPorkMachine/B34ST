#include "fbr34ker/boot_image.h"

int main(void)
{
    fbr34ker_boot_image_header_t header = {0};
    header.magic = FBR34KER_BOOT_IMAGE_MAGIC;
    header.format_version = FBR34KER_BOOT_IMAGE_FORMAT_VERSION;
    header.header_size = FBR34KER_BOOT_IMAGE_HEADER_SIZE;
    header.family = FBR34KER_BOOT_FAMILY_A13;
    header.component_count = 3U;
    header.manifest_capacity = FBR34KER_BOOT_IMAGE_MANIFEST_CAPACITY;
    header.manifest_offset = FBR34KER_BOOT_IMAGE_HEADER_SIZE;
    header.payload_offset = 5U * FBR34KER_BOOT_IMAGE_ALIGNMENT;
    return header.magic == 0x49524246U &&
           header.payload_offset == 20480U &&
           sizeof(header) == 128U ? 0 : 1;
}
