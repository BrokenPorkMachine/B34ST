#include "fbr34ker/lifecycle.h"
#include "fbr34ker/fault.h"
#include "fbr34ker/string.h"
#include "fbr34ker/trace.h"

typedef struct {
    const fbr34ker_component_descriptor_t *descriptor;
    fbr34ker_component_state_t state;
    u64 missing;
    u64 activation_sequence;
} lifecycle_entry_t;

static lifecycle_entry_t entries[FBR34KER_LIFECYCLE_MAX_COMPONENTS];
static usize entry_count;
static u64 provided_capabilities;
static u64 next_activation_sequence;
static bool started;
static fbr34ker_lifecycle_stats_t statistics;

static void set_state(lifecycle_entry_t *entry, fbr34ker_component_state_t state)
{
    entry->state = state;
    (void)trace_emit(FBR34KER_TRACE_LIFECYCLE, (u32)state,
                     state == FBR34KER_COMPONENT_FAILED ? -1 : 0,
                     entry->descriptor->name, entry->missing,
                     entry->activation_sequence);
}

void lifecycle_init(void)
{
    fm_memset(entries, 0, sizeof(entries));
    fm_memset(&statistics, 0, sizeof(statistics));
    entry_count = 0U;
    provided_capabilities = 0U;
    next_activation_sequence = 1U;
    started = false;
}

static bool name_valid(const char *name)
{
    if (name == NULL || *name == '\0') {
        return false;
    }
    const usize length = fm_strlen(name);
    return length > 0U && length < FBR34KER_LIFECYCLE_NAME_CAPACITY;
}

bool lifecycle_register(const fbr34ker_component_descriptor_t *descriptor)
{
    if (started || descriptor == NULL || !name_valid(descriptor->name) ||
        descriptor->phase >= FBR34KER_PHASE_COUNT || descriptor->provides == 0U ||
        entry_count >= ARRAY_COUNT(entries)) {
        return false;
    }
    for (usize index = 0U; index < entry_count; ++index) {
        if (fm_strcmp(entries[index].descriptor->name, descriptor->name) == 0 ||
            (entries[index].descriptor->provides & descriptor->provides) != 0U) {
            return false;
        }
    }
    entries[entry_count++] = (lifecycle_entry_t){
        .descriptor = descriptor,
        .state = FBR34KER_COMPONENT_REGISTERED,
        .missing = descriptor->requires,
        .activation_sequence = 0U,
    };
    return true;
}

static lifecycle_entry_t *latest_active(void)
{
    lifecycle_entry_t *latest = NULL;
    for (usize index = 0U; index < entry_count; ++index) {
        lifecycle_entry_t *entry = &entries[index];
        if (entry->state != FBR34KER_COMPONENT_ACTIVE) {
            continue;
        }
        if (latest == NULL || entry->activation_sequence > latest->activation_sequence) {
            latest = entry;
        }
    }
    return latest;
}

static void rollback_active(void)
{
    bool rolled_back = false;
    for (;;) {
        lifecycle_entry_t *entry = latest_active();
        if (entry == NULL) {
            break;
        }
        set_state(entry, FBR34KER_COMPONENT_STOPPING);
        if (entry->descriptor->stop != NULL) {
            entry->descriptor->stop();
        }
        provided_capabilities &= ~entry->descriptor->provides;
        set_state(entry, FBR34KER_COMPONENT_ROLLED_BACK);
        rolled_back = true;
    }
    if (rolled_back) {
        ++statistics.rollbacks;
    }
    statistics.provided_capabilities = provided_capabilities;
}

static void record_failure(lifecycle_entry_t *entry)
{
    ++statistics.failures;
    fm_strlcpy(statistics.last_failure, entry->descriptor->name,
               sizeof(statistics.last_failure));
}

static bool start_phase(fbr34ker_lifecycle_phase_t phase)
{
    for (;;) {
        lifecycle_entry_t *candidate = NULL;
        bool pending = false;
        for (usize index = 0U; index < entry_count; ++index) {
            lifecycle_entry_t *entry = &entries[index];
            if (entry->descriptor->phase != phase ||
                entry->state != FBR34KER_COMPONENT_REGISTERED) {
                continue;
            }
            pending = true;
            entry->missing = entry->descriptor->requires & ~provided_capabilities;
            if (entry->missing == 0U) {
                candidate = entry;
                break;
            }
        }
        if (candidate == NULL) {
            if (!pending) {
                return true;
            }
            for (usize index = 0U; index < entry_count; ++index) {
                lifecycle_entry_t *entry = &entries[index];
                if (entry->descriptor->phase == phase &&
                    entry->state == FBR34KER_COMPONENT_REGISTERED) {
                    entry->missing = entry->descriptor->requires & ~provided_capabilities;
                    set_state(entry, FBR34KER_COMPONENT_BLOCKED);
                    record_failure(entry);
                }
            }
            return false;
        }

        set_state(candidate, FBR34KER_COMPONENT_STARTING);
        const bool injected = fault_injection_should_fail(
            FBR34KER_FAULT_COMPONENT_START, candidate->descriptor->name);
        if (injected || (candidate->descriptor->start != NULL &&
                         !candidate->descriptor->start())) {
            set_state(candidate, FBR34KER_COMPONENT_FAILED);
            record_failure(candidate);
            return false;
        }
        candidate->activation_sequence = next_activation_sequence++;
        provided_capabilities |= candidate->descriptor->provides;
        statistics.provided_capabilities = provided_capabilities;
        ++statistics.successful_starts;
        set_state(candidate, FBR34KER_COMPONENT_ACTIVE);
    }
}

bool lifecycle_start(void)
{
    if (started) {
        return lifecycle_healthy();
    }
    started = true;
    ++statistics.starts;
    for (u32 phase = 0U; phase < (u32)FBR34KER_PHASE_COUNT; ++phase) {
        if (!start_phase((fbr34ker_lifecycle_phase_t)phase)) {
            rollback_active();
            return false;
        }
    }
    return lifecycle_healthy();
}

void lifecycle_stop(void)
{
    if (!started) {
        return;
    }
    for (;;) {
        lifecycle_entry_t *entry = latest_active();
        if (entry == NULL) {
            break;
        }
        set_state(entry, FBR34KER_COMPONENT_STOPPING);
        if (entry->descriptor->stop != NULL) {
            entry->descriptor->stop();
        }
        provided_capabilities &= ~entry->descriptor->provides;
        set_state(entry, FBR34KER_COMPONENT_STOPPED);
        ++statistics.stops;
    }
    statistics.provided_capabilities = provided_capabilities;
    started = false;
}

u64 lifecycle_component_count(void)
{
    return (u64)entry_count;
}

bool lifecycle_component_info(u64 requested, fbr34ker_component_info_t *information)
{
    if (information == NULL || requested >= entry_count) {
        return false;
    }
    lifecycle_entry_t *entry = &entries[(usize)requested];
    bool healthy = entry->state == FBR34KER_COMPONENT_ACTIVE;
    if (healthy && entry->descriptor->health != NULL) {
        healthy = entry->descriptor->health();
    }
    *information = (fbr34ker_component_info_t){
        .name = entry->descriptor->name,
        .phase = entry->descriptor->phase,
        .state = entry->state,
        .requires = entry->descriptor->requires,
        .provides = entry->descriptor->provides,
        .missing = entry->missing,
        .activation_sequence = entry->activation_sequence,
        .healthy = healthy,
    };
    return true;
}

u64 lifecycle_provided_capabilities(void)
{
    return provided_capabilities;
}

bool lifecycle_healthy(void)
{
    if (!started || entry_count == 0U) {
        return false;
    }
    for (usize index = 0U; index < entry_count; ++index) {
        lifecycle_entry_t *entry = &entries[index];
        if (entry->state != FBR34KER_COMPONENT_ACTIVE) {
            return false;
        }
        if (entry->descriptor->health != NULL && !entry->descriptor->health()) {
            return false;
        }
    }
    return true;
}

fbr34ker_lifecycle_stats_t lifecycle_stats(void)
{
    statistics.provided_capabilities = provided_capabilities;
    return statistics;
}

const char *lifecycle_phase_name(fbr34ker_lifecycle_phase_t phase)
{
    switch (phase) {
    case FBR34KER_PHASE_EARLY: return "early";
    case FBR34KER_PHASE_CORE: return "core";
    case FBR34KER_PHASE_PLATFORM: return "platform";
    case FBR34KER_PHASE_SERVICES: return "services";
    case FBR34KER_PHASE_EXTENSIONS: return "extensions";
    case FBR34KER_PHASE_INTERACTIVE: return "interactive";
    default: return "unknown";
    }
}

const char *lifecycle_state_name(fbr34ker_component_state_t state)
{
    switch (state) {
    case FBR34KER_COMPONENT_REGISTERED: return "registered";
    case FBR34KER_COMPONENT_STARTING: return "starting";
    case FBR34KER_COMPONENT_ACTIVE: return "active";
    case FBR34KER_COMPONENT_BLOCKED: return "blocked";
    case FBR34KER_COMPONENT_FAILED: return "failed";
    case FBR34KER_COMPONENT_STOPPING: return "stopping";
    case FBR34KER_COMPONENT_STOPPED: return "stopped";
    case FBR34KER_COMPONENT_ROLLED_BACK: return "rolled-back";
    default: return "unknown";
    }
}
