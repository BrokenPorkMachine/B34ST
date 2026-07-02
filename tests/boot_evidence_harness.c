#include "fbr34ker/boot_evidence.h"

// SPDX-License-Identifier: BSD-2-Clause
int main(void)
{
    boot_evidence_init();
    boot_evidence_stage(FBR34KER_BOOT_STAGE_CONTEXT);
    boot_evidence_stage(FBR34KER_BOOT_STAGE_ARCHITECTURE);
    const fbr34ker_boot_evidence_t *record=boot_evidence_record();
    if(record==0 || record->boot_count!=1U || record->current_stage!=FBR34KER_BOOT_STAGE_ARCHITECTURE) return 1;
    boot_evidence_init();
    record=boot_evidence_record();
    if(record==0 || record->boot_count!=2U || record->previous_stage!=FBR34KER_BOOT_STAGE_ARCHITECTURE || record->previous_clean!=0U) return 2;
    boot_evidence_error(7U,0x1234U);
    record=boot_evidence_record();
    if(record==0 || record->current_stage!=FBR34KER_BOOT_STAGE_FAULT || record->last_error!=7U) return 3;
    char json[512];
    if(boot_evidence_export_json(json,sizeof(json))==0U || json[0]!='{') return 4;
    boot_evidence_clean_shutdown();
    return boot_evidence_record()->clean_shutdown==1U?0:5;
}
