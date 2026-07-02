#include "fbr34ker/deployment_protocol.h"

// SPDX-License-Identifier: BSD-2-Clause
int main(void)
{
    if (sizeof(fbr34ker_deploy_header_t) != 20U) {
        return 1;
    }
    if (FBR34KER_DEPLOY_VERSION != 1U || FBR34KER_DEPLOY_MAX_CHUNK != 4096U) {
        return 2;
    }
    if (FBR34KER_DEPLOY_START != 0x14 || FBR34KER_DEPLOY_EVIDENCE_GET != 0x20) {
        return 3;
    }
    return 0;
}
