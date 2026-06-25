#include "fbr34ker/handoff.h"

#define HANDOFF_V1_SIZE ((u32)__builtin_offsetof(fbr34ker_handoff_t, flags))
#define HANDOFF_V2_SIZE ((u32)__builtin_offsetof(fbr34ker_handoff_t, runtime_getc))
#define HANDOFF_V3_SIZE ((u32)__builtin_offsetof(fbr34ker_handoff_t, platform_services))
#define BOOT_FMOD_TYPE 1U
#define BOOT_FMOD_MAX_SIZE (64U * 1024U)
#define TYPE_BIT(type) (1U << (type))
#define METADATA_REGION_TYPES \
    (TYPE_BIT(FBR34KER_HANDOFF_REGION_USABLE) | \
     TYPE_BIT(FBR34KER_HANDOFF_REGION_RESERVED) | \
     TYPE_BIT(FBR34KER_HANDOFF_REGION_MONITOR))
#define FRAMEBUFFER_REGION_TYPES \
    (TYPE_BIT(FBR34KER_HANDOFF_REGION_RESERVED) | \
     TYPE_BIT(FBR34KER_HANDOFF_REGION_MMIO) | \
     TYPE_BIT(FBR34KER_HANDOFF_REGION_FRAMEBUFFER))
#define CALLBACK_REGION_TYPES \
    (TYPE_BIT(FBR34KER_HANDOFF_REGION_USABLE) | \
     TYPE_BIT(FBR34KER_HANDOFF_REGION_RESERVED) | \
     TYPE_BIT(FBR34KER_HANDOFF_REGION_MONITOR))
#define CALLBACK_ADDRESS(callback) ((u64)(usize)(callback))

static const fbr34ker_handoff_t *active_handoff;

static bool pointer_aligned(const void *pointer, usize alignment)
{
    return pointer == NULL || (((usize)pointer & (alignment - 1U)) == 0U);
}

static bool range_valid(u64 base, u64 size)
{
    u64 end;
    return size != 0U && u64_add_checked(base, size, &end) && end > base;
}

static bool multiplication_valid(u64 left, u64 right, u64 *result)
{
    if (result == NULL || (right != 0U && left > U64_MAX_VALUE / right)) {
        return false;
    }
    *result = left * right;
    return true;
}

bool fbr34ker_handoff_covers_range(const fbr34ker_handoff_t *handoff,
                                   u64 base, u64 size)
{
    if (handoff == NULL || !range_valid(base, size) ||
        !range_valid(handoff->monitor_base, handoff->monitor_size)) {
        return false;
    }
    const u64 end = base + size;
    const u64 monitor_end = handoff->monitor_base + handoff->monitor_size;
    return base >= handoff->monitor_base && end <= monitor_end;
}

bool fbr34ker_handoff_describes_range(const fbr34ker_handoff_t *handoff,
                                      u64 base, u64 size,
                                      u32 allowed_type_mask,
                                      u32 required_attributes)
{
    if (handoff == NULL || !range_valid(base, size) ||
        handoff->memory_regions == NULL ||
        handoff->memory_region_count > FBR34KER_HANDOFF_MAX_REGIONS) {
        return false;
    }
    const u64 end = base + size;
    for (u32 index = 0U; index < handoff->memory_region_count; ++index) {
        const fbr34ker_handoff_region_t *region = &handoff->memory_regions[index];
        if (!range_valid(region->base, region->size)) {
            continue;
        }
        const u64 region_end = region->base + region->size;
        const bool type_allowed = allowed_type_mask == 0U ||
            (region->type < 32U &&
             (allowed_type_mask & TYPE_BIT(region->type)) != 0U);
        if (type_allowed &&
            (region->attributes & required_attributes) == required_attributes &&
            base >= region->base && end <= region_end) {
            return true;
        }
    }
    return false;
}

static bool regions_basic_valid(const fbr34ker_handoff_t *handoff)
{
    if (handoff->memory_region_count > FBR34KER_HANDOFF_MAX_REGIONS ||
        (handoff->memory_region_count != 0U &&
         (handoff->memory_regions == NULL ||
          !pointer_aligned(handoff->memory_regions, 8U)))) {
        return false;
    }
    for (u32 index = 0U; index < handoff->memory_region_count; ++index) {
        const fbr34ker_handoff_region_t *region = &handoff->memory_regions[index];
        if (!range_valid(region->base, region->size)) {
            return false;
        }
    }
    return true;
}

static bool regions_v4_valid(const fbr34ker_handoff_t *handoff)
{
    if (handoff->memory_region_count == 0U) {
        return false;
    }
    u64 previous_end = 0U;
    for (u32 index = 0U; index < handoff->memory_region_count; ++index) {
        const fbr34ker_handoff_region_t *region = &handoff->memory_regions[index];
        if (region->type < FBR34KER_HANDOFF_REGION_USABLE ||
            region->type > FBR34KER_HANDOFF_REGION_FRAMEBUFFER ||
            (region->attributes & ~FBR34KER_REGION_ATTR_SUPPORTED) != 0U) {
            return false;
        }
        if (index != 0U && region->base < previous_end) {
            return false;
        }
        previous_end = region->base + region->size;
        if (region->type == FBR34KER_HANDOFF_REGION_MMIO &&
            (region->attributes & FBR34KER_REGION_ATTR_DEVICE) == 0U) {
            return false;
        }
        if (region->type == FBR34KER_HANDOFF_REGION_FRAMEBUFFER &&
            (region->attributes & (FBR34KER_REGION_ATTR_READ |
                                   FBR34KER_REGION_ATTR_WRITE)) !=
                (FBR34KER_REGION_ATTR_READ | FBR34KER_REGION_ATTR_WRITE)) {
            return false;
        }
    }
    return fbr34ker_handoff_describes_range(
        handoff, handoff->monitor_base, handoff->monitor_size,
        TYPE_BIT(FBR34KER_HANDOFF_REGION_MONITOR),
        FBR34KER_REGION_ATTR_READ | FBR34KER_REGION_ATTR_WRITE |
            FBR34KER_REGION_ATTR_EXECUTE);
}

static bool boot_modules_valid(const fbr34ker_handoff_t *handoff)
{
    if (handoff->boot_module_count > FBR34KER_HANDOFF_MAX_BOOT_MODULES ||
        (handoff->boot_module_count != 0U &&
         (handoff->boot_modules == NULL ||
          !pointer_aligned(handoff->boot_modules, 8U)))) {
        return false;
    }
    for (u32 index = 0U; index < handoff->boot_module_count; ++index) {
        const fbr34ker_handoff_boot_module_t *module =
            &handoff->boot_modules[index];
        if (module->base == NULL || module->size == 0U ||
            (module->type == BOOT_FMOD_TYPE &&
             module->size > BOOT_FMOD_MAX_SIZE)) {
            return false;
        }
    }
    return true;
}

static bool v2_flags_valid(const fbr34ker_handoff_t *handoff)
{
    if ((handoff->flags & ~FBR34KER_HANDOFF_FLAGS_SUPPORTED) != 0U) {
        return false;
    }

    const bool early_flag =
        (handoff->flags & FBR34KER_HANDOFF_FLAG_EARLY_CONSOLE_VALID) != 0U;
    const bool dt_flag =
        (handoff->flags & FBR34KER_HANDOFF_FLAG_DEVICE_TREE_VALID) != 0U;
    const bool fb_flag =
        (handoff->flags & FBR34KER_HANDOFF_FLAG_FRAMEBUFFER_VALID) != 0U;

    if (early_flag != (handoff->early_putc != NULL)) {
        return false;
    }
    const bool dt_present = handoff->device_tree != NULL ||
                            handoff->device_tree_size != 0U;
    if (dt_flag != dt_present ||
        (dt_flag &&
         (handoff->device_tree == NULL ||
          !pointer_aligned(handoff->device_tree, 4U) ||
          handoff->device_tree_size == 0U ||
          handoff->device_tree_size > FBR34KER_HANDOFF_MAX_DEVICE_TREE_SIZE))) {
        return false;
    }
    const bool fb_present = handoff->framebuffer.base != 0U ||
                            handoff->framebuffer.width != 0U ||
                            handoff->framebuffer.height != 0U ||
                            handoff->framebuffer.pixels_per_row != 0U;
    if (fb_flag != fb_present ||
        (fb_flag &&
         (handoff->framebuffer.base == 0U ||
          handoff->framebuffer.width == 0U ||
          handoff->framebuffer.height == 0U ||
          handoff->framebuffer.pixels_per_row < handoff->framebuffer.width))) {
        return false;
    }
    return true;
}

static bool v3_callbacks_valid(const fbr34ker_handoff_t *handoff)
{
    const bool runtime_flag =
        (handoff->flags & FBR34KER_HANDOFF_FLAG_RUNTIME_IO_VALID) != 0U;
    const bool timer_flag =
        (handoff->flags & FBR34KER_HANDOFF_FLAG_TIMER_VALID) != 0U;
    const bool power_flag =
        (handoff->flags & FBR34KER_HANDOFF_FLAG_POWER_VALID) != 0U;

    /* Runtime input is independent from the selected output transport. */
    if (runtime_flag != (handoff->runtime_getc != NULL)) {
        return false;
    }
    const bool timer_present = handoff->timer_read != NULL ||
                               handoff->timer_frequency != NULL;
    if (timer_flag != timer_present ||
        (timer_flag &&
         (handoff->timer_read == NULL || handoff->timer_frequency == NULL))) {
        return false;
    }
    const bool power_present = handoff->reboot != NULL || handoff->halt != NULL;
    if (power_flag != power_present ||
        (power_flag && (handoff->reboot == NULL || handoff->halt == NULL))) {
        return false;
    }
    return true;
}

static bool service_table_valid(const fbr34ker_platform_services_t *services,
                                u32 supplied_size)
{
    if (services == NULL || !pointer_aligned(services, 8U) ||
        supplied_size < sizeof(*services) ||
        services->version != FBR34KER_PLATFORM_SERVICES_VERSION_1 ||
        services->structure_size < sizeof(*services) ||
        services->structure_size > supplied_size || services->reserved != 0U ||
        (services->capabilities & ~FBR34KER_SERVICE_FLAGS_SUPPORTED) != 0U) {
        return false;
    }
#define CALLBACK_MATCHES(flag, callback) \
    ((((services->capabilities & (flag)) != 0U) == ((callback) != NULL)))
    if (!CALLBACK_MATCHES(FBR34KER_SERVICE_CONSOLE_WRITE,
                          services->console_write) ||
        !CALLBACK_MATCHES(FBR34KER_SERVICE_CONSOLE_READ,
                          services->console_read) ||
        !CALLBACK_MATCHES(FBR34KER_SERVICE_CONSOLE_FLUSH,
                          services->console_flush) ||
        !CALLBACK_MATCHES(FBR34KER_SERVICE_FRAMEBUFFER_FLUSH,
                          services->framebuffer_flush) ||
        !CALLBACK_MATCHES(FBR34KER_SERVICE_WATCHDOG_CONFIGURE,
                          services->watchdog_configure) ||
        !CALLBACK_MATCHES(FBR34KER_SERVICE_WATCHDOG_KICK,
                          services->watchdog_kick)) {
        return false;
    }
#undef CALLBACK_MATCHES
    const bool interrupt_capability =
        (services->capabilities & FBR34KER_SERVICE_INTERRUPT_CONTROLLER) != 0U;
    const bool interrupt_callbacks = services->interrupt_ack != NULL ||
        services->interrupt_complete != NULL ||
        services->interrupt_set_enabled != NULL;
    if (interrupt_capability != interrupt_callbacks ||
        (interrupt_capability &&
         (services->interrupt_ack == NULL ||
          services->interrupt_complete == NULL ||
          services->interrupt_set_enabled == NULL))) {
        return false;
    }
    return true;
}

static bool callback_address_valid(const fbr34ker_handoff_t *handoff,
                                   u64 address)
{
    return address != 0U && (address & 3U) == 0U &&
        fbr34ker_handoff_describes_range(
            handoff, address, 4U, CALLBACK_REGION_TYPES,
            FBR34KER_REGION_ATTR_READ | FBR34KER_REGION_ATTR_EXECUTE);
}

static bool context_pointer_valid(const fbr34ker_handoff_t *handoff,
                                  u64 address)
{
    return address == 0U ||
        fbr34ker_handoff_describes_range(
            handoff, address, 1U,
            TYPE_BIT(FBR34KER_HANDOFF_REGION_USABLE) |
            TYPE_BIT(FBR34KER_HANDOFF_REGION_RESERVED) |
            TYPE_BIT(FBR34KER_HANDOFF_REGION_MONITOR),
            FBR34KER_REGION_ATTR_READ);
}

static bool callback_set_v4_valid(const fbr34ker_handoff_t *handoff)
{
#define VALID_OPTIONAL(callback) \
    ((callback) == NULL || callback_address_valid(handoff, CALLBACK_ADDRESS(callback)))
    if (!VALID_OPTIONAL(handoff->early_putc) ||
        !VALID_OPTIONAL(handoff->runtime_getc) ||
        !VALID_OPTIONAL(handoff->timer_read) ||
        !VALID_OPTIONAL(handoff->timer_frequency) ||
        !VALID_OPTIONAL(handoff->reboot) || !VALID_OPTIONAL(handoff->halt)) {
        return false;
    }
    const fbr34ker_platform_services_t *services = handoff->platform_services;
    if (services != NULL &&
        (!VALID_OPTIONAL(services->console_write) ||
         !VALID_OPTIONAL(services->console_read) ||
         !VALID_OPTIONAL(services->console_flush) ||
         !VALID_OPTIONAL(services->framebuffer_flush) ||
         !VALID_OPTIONAL(services->interrupt_ack) ||
         !VALID_OPTIONAL(services->interrupt_complete) ||
         !VALID_OPTIONAL(services->interrupt_set_enabled) ||
         !VALID_OPTIONAL(services->watchdog_configure) ||
         !VALID_OPTIONAL(services->watchdog_kick))) {
        return false;
    }
#undef VALID_OPTIONAL
    return true;
}

static bool framebuffer_v4_valid(const fbr34ker_handoff_t *handoff)
{
    const bool present =
        (handoff->flags & FBR34KER_HANDOFF_FLAG_FRAMEBUFFER_VALID) != 0U;
    if (!present) {
        return handoff->framebuffer_size == 0U &&
               handoff->framebuffer_bytes_per_pixel == 0U &&
               handoff->framebuffer_rotation == 0U;
    }
    const u32 bpp = handoff->framebuffer_bytes_per_pixel;
    const bool format_matches =
        ((handoff->framebuffer.pixel_format == FBR34KER_PIXEL_FORMAT_RGB565) &&
         bpp == 2U) ||
        ((handoff->framebuffer.pixel_format == FBR34KER_PIXEL_FORMAT_XRGB8888 ||
          handoff->framebuffer.pixel_format == FBR34KER_PIXEL_FORMAT_ARGB8888 ||
          handoff->framebuffer.pixel_format == FBR34KER_PIXEL_FORMAT_BGRA8888) &&
         bpp == 4U);
    if (!format_matches || handoff->framebuffer_size == 0U ||
        (handoff->framebuffer_rotation != 0U &&
         handoff->framebuffer_rotation != 90U &&
         handoff->framebuffer_rotation != 180U &&
         handoff->framebuffer_rotation != 270U)) {
        return false;
    }
    u64 row_bytes;
    u64 needed;
    if (!multiplication_valid(handoff->framebuffer.pixels_per_row, bpp,
                              &row_bytes) ||
        !multiplication_valid(row_bytes, handoff->framebuffer.height,
                              &needed) ||
        needed > handoff->framebuffer_size) {
        return false;
    }
    return fbr34ker_handoff_describes_range(
        handoff, handoff->framebuffer.base, handoff->framebuffer_size,
        FRAMEBUFFER_REGION_TYPES,
        FBR34KER_REGION_ATTR_READ | FBR34KER_REGION_ATTR_WRITE);
}

static bool v4_metadata_ranges_valid(const fbr34ker_handoff_t *handoff)
{
    u64 regions_size;
    if (!multiplication_valid(handoff->memory_region_count,
                              sizeof(fbr34ker_handoff_region_t),
                              &regions_size) ||
        !fbr34ker_handoff_describes_range(
            handoff, (u64)(usize)handoff->memory_regions, regions_size,
            METADATA_REGION_TYPES, FBR34KER_REGION_ATTR_READ)) {
        return false;
    }
    if ((handoff->flags & FBR34KER_HANDOFF_FLAG_DEVICE_TREE_VALID) != 0U &&
        !fbr34ker_handoff_describes_range(
            handoff, (u64)(usize)handoff->device_tree,
            handoff->device_tree_size, METADATA_REGION_TYPES,
            FBR34KER_REGION_ATTR_READ)) {
        return false;
    }
    if (handoff->boot_module_count != 0U) {
        u64 table_size;
        if (!multiplication_valid(handoff->boot_module_count,
                                  sizeof(fbr34ker_handoff_boot_module_t),
                                  &table_size) ||
            !fbr34ker_handoff_describes_range(
                handoff, (u64)(usize)handoff->boot_modules, table_size,
                METADATA_REGION_TYPES, FBR34KER_REGION_ATTR_READ)) {
            return false;
        }
        for (u32 index = 0U; index < handoff->boot_module_count; ++index) {
            const fbr34ker_handoff_boot_module_t *module =
                &handoff->boot_modules[index];
            if (!fbr34ker_handoff_describes_range(
                    handoff, (u64)(usize)module->base, module->size,
                    METADATA_REGION_TYPES, FBR34KER_REGION_ATTR_READ)) {
                return false;
            }
        }
    }
    if ((handoff->flags & FBR34KER_HANDOFF_FLAG_PLATFORM_SERVICES_VALID) != 0U &&
        !fbr34ker_handoff_describes_range(
            handoff, (u64)(usize)handoff->platform_services,
            handoff->platform_services_size, METADATA_REGION_TYPES,
            FBR34KER_REGION_ATTR_READ)) {
        return false;
    }
    return true;
}

static bool v4_valid(const fbr34ker_handoff_t *handoff)
{
    const bool service_flag =
        (handoff->flags & FBR34KER_HANDOFF_FLAG_PLATFORM_SERVICES_VALID) != 0U;
    const bool policy_flag =
        (handoff->flags & FBR34KER_HANDOFF_FLAG_MODULE_POLICY_VALID) != 0U;
    const fbr34ker_platform_services_t *platform_services =
        handoff->platform_services;
    const bool service_present = platform_services != NULL ||
        handoff->platform_services_size != 0U;
    if (service_flag != service_present) {
        return false;
    }
    if (service_flag) {
        if (platform_services == NULL ||
            !service_table_valid(platform_services,
                                 handoff->platform_services_size)) {
            return false;
        }
        if (!context_pointer_valid(handoff,
                                   (u64)(usize)platform_services->console_context) ||
            !context_pointer_valid(handoff,
                                   (u64)(usize)platform_services->framebuffer_context) ||
            !context_pointer_valid(handoff,
                                   (u64)(usize)platform_services->interrupt_context) ||
            !context_pointer_valid(handoff,
                                   (u64)(usize)platform_services->watchdog_context)) {
            return false;
        }
        if ((platform_services->capabilities &
             FBR34KER_SERVICE_FRAMEBUFFER_FLUSH) != 0U &&
            (handoff->flags & FBR34KER_HANDOFF_FLAG_FRAMEBUFFER_VALID) == 0U) {
            return false;
        }
    }
    if (handoff->entry_exception_level < 1U ||
        handoff->entry_exception_level > 3U ||
        (handoff->page_granule != FBR34KER_PAGE_GRANULE_4K &&
         handoff->page_granule != FBR34KER_PAGE_GRANULE_16K &&
         handoff->page_granule != FBR34KER_PAGE_GRANULE_64K) ||
        handoff->reserved_v4_small != 0U ||
        handoff->reserved_v4[0] != 0U || handoff->reserved_v4[1] != 0U) {
        return false;
    }
    const bool policy_present = handoff->module_capability_allow_mask != 0U ||
        handoff->module_slot_limit != 0U ||
        handoff->module_instruction_budget_limit != 0U;
    if (policy_flag != policy_present) {
        return false;
    }
    if (policy_flag &&
        ((handoff->module_capability_allow_mask &
          ~FBR34KER_HANDOFF_MODULE_CAP_MASK_SUPPORTED) != 0U ||
         handoff->module_slot_limit > FBR34KER_HANDOFF_MAX_MODULE_SLOTS ||
         (handoff->module_slot_limit != 0U &&
          (handoff->module_instruction_budget_limit == 0U ||
           handoff->module_instruction_budget_limit >
               FBR34KER_HANDOFF_MAX_INSTRUCTION_BUDGET)))) {
        return false;
    }
    return regions_v4_valid(handoff) && framebuffer_v4_valid(handoff) &&
           v4_metadata_ranges_valid(handoff) && callback_set_v4_valid(handoff);
}

bool fbr34ker_handoff_valid(const fbr34ker_handoff_t *handoff)
{
    if (handoff == NULL || !pointer_aligned(handoff, 8U) ||
        handoff->magic != FBR34KER_HANDOFF_MAGIC ||
        handoff->version < FBR34KER_HANDOFF_VERSION_1 ||
        handoff->version > FBR34KER_HANDOFF_VERSION_CURRENT) {
        return false;
    }

    u32 required_size = HANDOFF_V1_SIZE;
    if (handoff->version == FBR34KER_HANDOFF_VERSION_2) {
        required_size = HANDOFF_V2_SIZE;
    } else if (handoff->version == FBR34KER_HANDOFF_VERSION_3) {
        required_size = HANDOFF_V3_SIZE;
    } else if (handoff->version == FBR34KER_HANDOFF_VERSION_4) {
        required_size = (u32)sizeof(*handoff);
    }
    if (handoff->structure_size < required_size || handoff->reserved != 0U ||
        !range_valid(handoff->monitor_base, handoff->monitor_size) ||
        !regions_basic_valid(handoff)) {
        return false;
    }

    if (handoff->version == FBR34KER_HANDOFF_VERSION_1) {
        const bool dt_present = handoff->device_tree != NULL ||
                                handoff->device_tree_size != 0U;
        return (!dt_present ||
                (handoff->device_tree != NULL &&
                 pointer_aligned(handoff->device_tree, 4U) &&
                 handoff->device_tree_size != 0U &&
                 handoff->device_tree_size <=
                    FBR34KER_HANDOFF_MAX_DEVICE_TREE_SIZE));
    }

    if (handoff->reserved_v2 != 0U || !boot_modules_valid(handoff) ||
        !v2_flags_valid(handoff)) {
        return false;
    }
    if (handoff->version >= FBR34KER_HANDOFF_VERSION_3 &&
        !v3_callbacks_valid(handoff)) {
        return false;
    }
    return handoff->version < FBR34KER_HANDOFF_VERSION_4 || v4_valid(handoff);
}

void fbr34ker_handoff_set_active(const fbr34ker_handoff_t *handoff)
{
    active_handoff = fbr34ker_handoff_valid(handoff) ? handoff : NULL;
}

const fbr34ker_handoff_t *fbr34ker_handoff_active(void)
{
    return active_handoff;
}
