#include "fbr34ker/fault.h"
#include "fbr34ker/trace.h"

int main(void)
{
    trace_init();
    fault_injection_init();
    if (!fault_injection_available()) return 1;
    if (!fault_injection_arm(FBR34KER_FAULT_DRIVER_START, "target", 1U, 2U)) return 2;
    if (fault_injection_should_fail(FBR34KER_FAULT_DRIVER_START, "other")) return 3;
    if (fault_injection_should_fail(FBR34KER_FAULT_DRIVER_START, "target")) return 4;
    if (!fault_injection_should_fail(FBR34KER_FAULT_DRIVER_START, "target")) return 5;
    if (!fault_injection_should_fail(FBR34KER_FAULT_DRIVER_START, "target")) return 6;
    if (fault_injection_should_fail(FBR34KER_FAULT_DRIVER_START, "target")) return 7;
    const fbr34ker_fault_status_t status = fault_injection_status();
    if (status.enabled || status.injections != 2U || status.checks != 3U) return 8;
    return trace_count() >= 3U ? 0 : 9;
}
