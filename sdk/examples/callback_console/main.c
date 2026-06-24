#include "fbr34ker_sdk.h"
#include <stdio.h>
static size_t write_cb(const char *p, size_t n, void *ctx) { (void)ctx; return fwrite(p, 1, n, stdout); }
int main(void) {
    fbr34ker_handoff_builder_t b; const fbr34ker_handoff_t *h = NULL;
    fbr34ker_platform_services_t s = {0};
    s.version=1; s.structure_size=sizeof(s); s.capabilities=FBR34KER_SERVICE_CONSOLE_WRITE; s.console_write=write_cb;
    fbr34ker_handoff_builder_init(&b, 0x80000000ULL, 0x100000ULL);
    (void)fbr34ker_handoff_builder_add_region(&b,0x80000000ULL,0x100000ULL,4,7);
    fbr34ker_handoff_builder_set_services(&b,&s);
    if (fbr34ker_handoff_builder_finalize(&b,&h) != FBR34KER_SDK_OK) return 1;
    h->platform_services->console_write("callback-console\n",17,NULL); return 0;
}
