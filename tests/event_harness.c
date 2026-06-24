#include "fbr34ker/event.h"
#include "fbr34ker/fault.h"

static u64 callbacks;
static void callback(const fbr34ker_event_t *event, void *context)
{
    if (event != NULL && context != NULL) ++*(u64 *)context;
}

int main(void)
{
    fault_injection_init();
    event_bus_init();
    if (!event_bus_subscribe(1ULL << FBR34KER_EVENT_BOOT,
                             callback, &callbacks)) return 1;
    if (!event_bus_publish(FBR34KER_EVENT_BOOT, "test", 1U, 2U) ||
        callbacks != 1U) return 2;
    fbr34ker_event_t event;
    if (!event_bus_at(0U, &event) || event.value1 != 2U) return 3;
    for (u32 index = 0U; index < 40U; ++index) {
        (void)event_bus_publish(FBR34KER_EVENT_SERVICE_STATE,
                                "service", index, 0U);
    }
    const fbr34ker_event_stats_t stats = event_bus_stats();
    if (stats.journal_count != FBR34KER_EVENT_JOURNAL_CAPACITY ||
        stats.overwritten == 0U) return 4;
    event_bus_shutdown();
    return event_bus_ready() ? 5 : 0;
}
