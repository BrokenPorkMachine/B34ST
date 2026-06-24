#include "fbr34ker/trace.h"
#include "fbr34ker/string.h"

static bool contains(const char *text, const char *needle)
{
    const usize needle_length = fm_strlen(needle);
    for (usize index = 0U; text[index] != '\0'; ++index) {
        if (fm_strncmp(text + index, needle, needle_length) == 0) return true;
    }
    return false;
}

int main(void)
{
    trace_init();
    for (u32 index = 0U; index < 80U; ++index) {
        if (!trace_emit(FBR34KER_TRACE_VALIDATION, index, 0,
                        "native", index, index + 1U)) return 1;
    }
    const fbr34ker_trace_stats_t stats = trace_stats();
    if (stats.retained != FBR34KER_TRACE_CAPACITY ||
        stats.overwritten != 16U) return 2;
    fbr34ker_trace_record_t record;
    if (!trace_at(0U, &record) || record.sequence != 17U) return 3;
    char json[16384];
    const usize length = trace_export_json(json, sizeof(json));
    if (length == 0U || !contains(json, "\"schema\":1") ||
        !contains(json, "validation")) return 4;
    trace_shutdown();
    return trace_ready() ? 5 : 0;
}
