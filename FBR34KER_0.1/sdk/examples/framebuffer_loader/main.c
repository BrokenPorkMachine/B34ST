#include "fbr34ker_sdk.h"
#include <stdio.h>
int main(void) {
    fbr34ker_handoff_builder_t b; const fbr34ker_handoff_t *h = NULL;
    fbr34ker_handoff_builder_init(&b,0x80000000ULL,0x100000ULL);
    (void)fbr34ker_handoff_builder_add_region(&b,0x70000000ULL,0x400000ULL,5,3);
    (void)fbr34ker_handoff_builder_add_region(&b,0x80000000ULL,0x100000ULL,4,7);
    b.handoff.framebuffer=(fbr34ker_handoff_framebuffer_t){0x70000000ULL,1024,768,1024,FBR34KER_PIXEL_FORMAT_XRGB8888};
    b.handoff.framebuffer_size=0x400000ULL; b.handoff.framebuffer_bytes_per_pixel=4;
    b.handoff.flags|=FBR34KER_HANDOFF_FLAG_FRAMEBUFFER_VALID;
    if (fbr34ker_handoff_builder_finalize(&b,&h) != FBR34KER_SDK_OK) return 1;
    printf("framebuffer=%ux%u\n",h->framebuffer.width,h->framebuffer.height); return 0;
}
