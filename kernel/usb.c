#include "fbr34ker/usb.h"
#include "fbr34ker/mmio.h"
#include "fbr34ker/log.h"
#include "fbr34ker/string.h"
#include "fbr34ker/event.h"
#include "fbr34ker/platform.h"
#include "fbr34ker/timer.h"
#include "fbr34ker/usbliter8_exploit.h"

#define USB_SERIAL_BUF_SIZE 4096U
#define USB_SERIAL_RX_BUF 2048U
#define USB_DWC3_RESET_TIMEOUT_MS 100U
#define USB_MAX_DEVICE_ADDRESS 127U
#define DWC3_EVT_RING_ENTRIES 64U
#define DWC3_EVT_RING_SIZE (DWC3_EVT_RING_ENTRIES * 16U)

#define DWC3_EVT_TYPE_SETUP 4U
#define DWC3_EVT_TYPE_XFER_COMPLETE 6U
#define DWC3_EVT_TYPE_CMD_CMPLT 2U
#define DWC3_EVT_TYPE_RESET 3U
#define DWC3_EVT_TYPE_CONNECT 1U
#define DWC3_EVT_TYPE_DISCONNECT 2U

#define DWC3_EP0_PHYS 0U
#define DWC3_EP0_MAX_PACKET 64U

STATIC_ASSERT(sizeof(usb_device_descriptor_t) == 18, "bad device desc size");
STATIC_ASSERT(sizeof(usb_config_descriptor_t) == 9, "bad config desc size");
STATIC_ASSERT(sizeof(usb_interface_descriptor_t) == 9, "bad iface desc size");
STATIC_ASSERT(sizeof(usb_endpoint_descriptor_t) == 7, "bad ep desc size");

struct usb_context {
    u64 mmio_base;
    bool initialized;
    bool connected;
    usb_device_state_t state;
    usb_speed_t speed;
    u8 device_address;
    u8 configuration;
    bool configured;
    volatile bool remote_wakeup;
    volatile bool self_powered;
    usb_callback_t setup_callback;
    usb_callback_t bulk_out_callback;
    usb_callback_t bulk_in_callback;
    const char *manufacturer;
    const char *product;
    const char *serial;
    u32 vendor_id;
    u32 product_id;
    u8 rx_buf[USB_SERIAL_RX_BUF];
    volatile usize rx_head;
    volatile usize rx_tail;
    u8 tx_buf[USB_SERIAL_BUF_SIZE];
    volatile usize tx_head;
    volatile usize tx_tail;
    u64 bytes_sent;
    u64 bytes_received;
    u64 irq_count;
    u64 last_connect_ms;
    u64 reset_count;
    u64 error_count;

    ALIGNED(64) u8 evt_ring[DWC3_EVT_RING_SIZE];
    u32 evt_ring_dma;           
    u16 evt_cons_idx;
    bool dfu_mode;

    dfu_state_t dfu_state;
    dfu_status_t dfu_status;
    u32 dfu_transfer_size;
    u32 dfu_received;
    u8 dfu_img_buf[USB_IMG_BUF_SIZE];
    usize dfu_img_size;
    bool dfu_manifest;
    u8 vendor_buf[8];
    u64 vendor_target_addr;
    int vendor_req_pending;
};

static struct usb_context ctx;

static void ctx_zero(void)
{
    fm_memset(&ctx, 0, sizeof(ctx));
    ctx.vendor_req_pending = -1;
}

static u32 dwc3_read32(u64 offset)
{
    if (!ctx.initialized && offset != 0U) {
        return 0U;
    }
    u64 address = ctx.mmio_base + offset;
    u32 value = 0U;
    mmio_read32(address, &value);
    return value;
}

static void dwc3_write32(u64 offset, u32 value)
{
    if (!ctx.initialized) return;
    u64 address = ctx.mmio_base + offset;
    mmio_write32(address, value);
}

static bool dwc3_check_id(void)
{
    u32 id = dwc3_read32(0U);
    bool valid = (id == USB_DWC3_GSNPSID);
    log_trace("dwc3_check_id: GSNPSID=0x%08x %s", id,
              valid ? "match" : "mismatch");
    return valid;
}

static bool dwc3_core_soft_reset(void)
{
    dwc3_write32(USB_DWC3_DCTL, DWC3_DCTL_CSFTRST);
    u64 deadline = timer_uptime_ms() + USB_DWC3_RESET_TIMEOUT_MS;
    do {
        if ((dwc3_read32(USB_DWC3_DCTL) & DWC3_DCTL_CSFTRST) == 0U) {
            log_trace("dwc3 soft reset ok");
            return true;
        }
        __asm__ volatile("yield");
    } while (timer_uptime_ms() < deadline);
    log_error("dwc3 soft reset TIMEOUT after %u ms",
              USB_DWC3_RESET_TIMEOUT_MS);
    ++ctx.error_count;
    return false;
}

static bool dwc3_core_init(void)
{
    dwc3_write32(USB_DWC3_GCTL, 0U);
    dwc3_write32(USB_DWC3_GUSB3PIPECTL, 0U);
    dwc3_write32(USB_DWC3_GUSB2PHYCFG, 0U);
    if (!dwc3_core_soft_reset()) {
        return false;
    }
    dwc3_write32(USB_DWC3_DCFG, DWC3_DCFG_DEVSPEED(4U));
    dwc3_write32(USB_DWC3_DALEPENA, 0U);
    log_trace("dwc3 core init complete");
    return true;
}

static bool dwc3_event_ring_init(void)
{
    u32 evt_size = DWC3_EVT_RING_SIZE;
    u32 dma_low = (u32)((u64)(usize)ctx.evt_ring & 0xFFFFFFFFU);
    u32 dma_high = (u32)(((u64)(usize)ctx.evt_ring >> 32) & 0xFFFFFFFFU);
    ctx.evt_ring_dma = dma_low;
    fm_memset(ctx.evt_ring, 0, DWC3_EVT_RING_SIZE);
    dwc3_write32(USB_DWC3_GEVNTADRLO, dma_low);
    dwc3_write32(USB_DWC3_GEVNTADRHI, dma_high);
    dwc3_write32(USB_DWC3_GEVNTSIZ, evt_size & 0xFFFCU);
    dwc3_write32(USB_DWC3_GEVNTCOUNT, 0U);
    log_trace("dwc3 event ring at phys 0x%08x, size %u", dma_low, evt_size);
    return true;
}

static void dwc3_enable_events(void)
{
    dwc3_write32(USB_DWC3_DEVTEN,
                 DWC3_DEVTEN_ULSTCNGEN |
                 DWC3_DEVTEN_CONNECTDETEN |
                 DWC3_DEVTEN_USBRSTEN |
                 DWC3_DEVTEN_EVNTOVERFLOWEN);
}

static void dwc3_ep0_configure(void)
{
    u32 cfg = DWC3_DEPCFG_EP_NUMBER(0) |
              DWC3_DEPCFG_EP_TYPE(0) |
              DWC3_DEPCFG_MAX_PACKET_SIZE(DWC3_EP0_MAX_PACKET) |
              (DWC3_DEPCFG_ACTION_INIT << 30);
    dwc3_write32(USB_DWC3_DEPCFG, cfg);
    dwc3_write32(USB_DWC3_DEPCMD, DWC3_DEPCMD_DEPSTARTCFG | DWC3_DEPCMD_CMDIOC | DWC3_DEPCMD_CMDACT);
}

static void dwc3_ep_bulk_configure(u32 phys_ep_num, u8 logical_ep, u16 max_pkt)
{
    u32 cfg_base = (u32)(USB_DWC3_DEPCMDPAR0 + phys_ep_num * 0x100U);
    u32 cmd_base = cfg_base + 0xCU;
    u32 depcfg_addr = cfg_base + 0x10U;
    u32 ep_type = EP_TYPE_BULK;
    u32 cfg = DWC3_DEPCFG_EP_NUMBER(logical_ep & 0xFU) |
              DWC3_DEPCFG_EP_TYPE(ep_type) |
              DWC3_DEPCFG_MAX_PACKET_SIZE(max_pkt) |
              (DWC3_DEPCFG_ACTION_INIT << 30);
    dwc3_write32(depcfg_addr, cfg);
    dwc3_write32(cmd_base, DWC3_DEPCMD_DEPSTARTCFG | DWC3_DEPCMD_CMDIOC | DWC3_DEPCMD_CMDACT);
}

static void dwc3_ep_interrupt_configure(u32 phys_ep_num, u8 logical_ep, u16 max_pkt)
{
    u32 cfg_base = (u32)(USB_DWC3_DEPCMDPAR0 + phys_ep_num * 0x100U);
    u32 cmd_base = cfg_base + 0xCU;
    u32 depcfg_addr = cfg_base + 0x10U;
    u32 ep_type = EP_TYPE_INTERRUPT;
    u32 cfg = DWC3_DEPCFG_EP_NUMBER(logical_ep & 0xFU) |
              DWC3_DEPCFG_EP_TYPE(ep_type) |
              DWC3_DEPCFG_MAX_PACKET_SIZE(max_pkt) |
              (DWC3_DEPCFG_ACTION_INIT << 30);
    dwc3_write32(depcfg_addr, cfg);
    dwc3_write32(cmd_base, DWC3_DEPCMD_DEPSTARTCFG | DWC3_DEPCMD_CMDIOC | DWC3_DEPCMD_CMDACT);
}

static void dwc3_start_bulk_out_transfer(void)
{
    usize space;
    if (ctx.rx_head >= ctx.rx_tail) {
        space = USB_SERIAL_RX_BUF - ctx.rx_head;
    } else {
        space = ctx.rx_tail - ctx.rx_head;
    }
    if (space < 64U) return;
    u32 buf_addr = (u32)(usize)(ctx.rx_buf + ctx.rx_head);
    u32 xfer_size = (space > 512U) ? 512U : (u32)space;
    dwc3_write32(USB_DWC3_DEP2_CMDPAR0, buf_addr);
    dwc3_write32(USB_DWC3_DEP2_CMDPAR1, xfer_size);
    dwc3_write32(USB_DWC3_DEP2_CMDPAR2, 0U);
    dwc3_write32(USB_DWC3_DEP2_CMD,
                 DWC3_DEPCMD_STARTTRANSFER |
                 DWC3_DEPCMD_PARAM(0) |
                 DWC3_DEPCMD_CMDIOC |
                 DWC3_DEPCMD_CMDACT);
    ctx.dfu_transfer_size = xfer_size;
}

static void dwc3_start_bulk_in_transfer(void)
{
    if (ctx.tx_head == ctx.tx_tail) return;
    usize available;
    if (ctx.tx_head > ctx.tx_tail) {
        available = ctx.tx_head - ctx.tx_tail;
    } else {
        available = USB_SERIAL_BUF_SIZE - ctx.tx_tail;
    }
    if (available == 0U) return;
    u32 xfer_size = (available > 512U) ? 512U : (u32)available;
    u32 buf_addr = (u32)(usize)(ctx.tx_buf + ctx.tx_tail);
    dwc3_write32(USB_DWC3_DEP3_CMDPAR0, buf_addr);
    dwc3_write32(USB_DWC3_DEP3_CMDPAR1, xfer_size);
    dwc3_write32(USB_DWC3_DEP3_CMDPAR2, 0U);
    dwc3_write32(USB_DWC3_DEP3_CMD,
                 DWC3_DEPCMD_STARTTRANSFER |
                 DWC3_DEPCMD_PARAM(0) |
                 DWC3_DEPCMD_CMDIOC |
                 DWC3_DEPCMD_CMDACT);
}

static void dwc3_complete_bulk_out(void)
{
    u32 requested = ctx.dfu_transfer_size;
    u32 residual = dwc3_read32(USB_DWC3_DEP2_CMDPAR1);
    u32 actual;
    if (residual <= requested) {
        actual = requested - residual;
    } else {
        actual = requested;
    }
    if (actual > 0) {
        ctx.rx_head = (ctx.rx_head + actual) % USB_SERIAL_RX_BUF;
        ctx.bytes_received += actual;
        log_verbose("USB EP2 OUT: %u bytes (req=%u res=%u)", actual, requested, residual);
    }
    dwc3_start_bulk_out_transfer();
}

static void dwc3_complete_bulk_in(void)
{
    u32 residual = dwc3_read32(USB_DWC3_DEP3_CMDPAR1);
    usize sent;
    if (ctx.tx_head > ctx.tx_tail) {
        sent = ctx.tx_head - ctx.tx_tail;
    } else {
        sent = USB_SERIAL_BUF_SIZE - ctx.tx_tail;
    }
    if (residual <= sent) {
        sent = sent - residual;
    } else {
        sent = 0;
    }
    ctx.tx_tail = (ctx.tx_tail + sent) % USB_SERIAL_BUF_SIZE;
    ctx.bytes_sent += sent;
    log_verbose("USB EP3 IN: %llu bytes sent", (u64)sent);
    if (ctx.tx_head != ctx.tx_tail) {
        dwc3_start_bulk_in_transfer();
    }
}

static void dwc3_configure_cdc_endpoints(void)
{
    dwc3_ep_bulk_configure(2, USB_CDC_BULK_EP_OUT, USB_MAX_PACKET_SIZE);
    dwc3_ep_bulk_configure(3, USB_CDC_BULK_EP_IN, USB_MAX_PACKET_SIZE);
    dwc3_ep_interrupt_configure(4, USB_CDC_NOTIFICATION_EP, 16);
    dwc3_start_bulk_out_transfer();
}

static void dwc3_connect(void)
{
    dwc3_write32(USB_DWC3_DCTL, DWC3_DCTL_RUN_STOP);
    log_trace("dwc3 connect issued");
}

static void dwc3_disconnect(void)
{
    dwc3_write32(USB_DWC3_DCTL, 0U);
    log_trace("dwc3 disconnect issued");
}

static void dwc3_set_address(u8 address)
{
    if (address > USB_MAX_DEVICE_ADDRESS) return;
    u32 dcfg = dwc3_read32(USB_DWC3_DCFG);
    dcfg &= ~(0x7fU << 3);
    dcfg |= DWC3_DCFG_DEVADDR(address);
    dwc3_write32(USB_DWC3_DCFG, dcfg);
    log_trace("dwc3 address set to %u", address);
}

static bool dwc3_is_connected(void)
{
    u32 dsts = dwc3_read32(USB_DWC3_DSTS);
    return (dsts & DWC3_DSTS_DCNRD) == 0U;
}

static u32 dwc3_speed(void)
{
    return dwc3_read32(USB_DWC3_DSTS) & DWC3_DSTS_CONNECTSPD;
}

static void flush_rx(void)
{
    __asm__ volatile("dmb sy");
}

static bool rx_available(void)
{
    flush_rx();
    return ctx.rx_head != ctx.rx_tail;
}

static bool write_tx_buffer(u8 byte)
{
    usize next = (ctx.tx_head + 1U) % USB_SERIAL_BUF_SIZE;
    if (next != ctx.tx_tail) {
        ctx.tx_buf[ctx.tx_head] = byte;
        ctx.tx_head = next;
        return true;
    }
    return false;
}

static u8 read_rx_buffer(void)
{
    u8 byte = 0U;
    if (ctx.rx_head != ctx.rx_tail) {
        byte = ctx.rx_buf[ctx.rx_tail];
        ctx.rx_tail = (ctx.rx_tail + 1U) % USB_SERIAL_RX_BUF;
    }
    flush_rx();
    return byte;
}

static const u8 dfu_device_descriptor[18] = {
    18,                          /* bLength */
    1,                           /* bDescriptorType = DEVICE */
    0x00, 0x02,                  /* bcdUSB = 0x0200 */
    0x00,                        /* bDeviceClass (per interface) */
    0x00,                        /* bDeviceSubClass */
    0x00,                        /* bDeviceProtocol */
    64,                          /* bMaxPacketSize0 */
    (USB_APPLE_VID & 0xFF), ((USB_APPLE_VID >> 8) & 0xFF),       /* idVendor */
    (USB_APPLE_DFU_PID & 0xFF), ((USB_APPLE_DFU_PID >> 8) & 0xFF), /* idProduct */
    0x00, 0x01,                  /* bcdDevice */
    1,                           /* iManufacturer */
    2,                           /* iProduct */
    3,                           /* iSerialNumber */
    1,                           /* bNumConfigurations */
};

static const u8 dfu_config_descriptor[] = {
    /* Configuration descriptor */
    9, 2,                        /* bLength, bDescriptorType = CONFIG */
    94, 0,                       /* wTotalLength = 94 */
    3,                           /* bNumInterfaces */
    1,                           /* bConfigurationValue */
    0,                           /* iConfiguration */
    0x80,                        /* bmAttributes (bus powered, no remote wake) */
    50,                          /* bMaxPower (100mA) */

    /* IAD: CDC ACM function (interfaces 0-1) */
    8, USB_DT_IAD,               /* bLength, bDescriptorType = IAD */
    0,                           /* bFirstInterface */
    2,                           /* bInterfaceCount */
    CDC_CLASS,                   /* bFunctionClass (CDC) */
    CDC_SUBCLASS_ACM,            /* bFunctionSubClass (ACM) */
    0x01,                        /* bFunctionProtocol (AT) */
    0,                           /* iFunction */

    /* Interface 0: CDC Communication Control */
    9, 4,                        /* bLength, bDescriptorType = INTERFACE */
    0,                           /* bInterfaceNumber */
    0,                           /* bAlternateSetting */
    1,                           /* bNumEndpoints */
    CDC_CLASS,                   /* bInterfaceClass (CDC) */
    CDC_SUBCLASS_ACM,            /* bInterfaceSubClass (ACM) */
    0x01,                        /* bInterfaceProtocol (AT) */
    0,                           /* iInterface */
    /* CDC Header functional descriptor */
    5, CS_INTERFACE, CDC_HEADER,
    0x10, 0x01,                  /* bcdCDC = 1.10 */
    /* CDC Call Management functional descriptor */
    5, CS_INTERFACE, CDC_CALL_MGMT,
    0x00,                        /* bmCapabilities (no call mgmt) */
    1,                           /* bDataInterface */
    /* CDC ACM functional descriptor */
    5, CS_INTERFACE, CDC_ACM,
    0x02,                        /* bmCapabilities (supports Set/Clear Line Coding) */
    /* CDC Union functional descriptor */
    5, CS_INTERFACE, CDC_UNION,
    0,                           /* bMasterInterface (control) */
    1,                           /* bSlaveInterface0 (data) */
    /* Notification endpoint (Interrupt IN) */
    7, 5,                        /* bLength, bDescriptorType = ENDPOINT */
    USB_CDC_NOTIFICATION_EP,     /* bEndpointAddress (0x83 IN) */
    EP_TYPE_INTERRUPT,           /* bmAttributes */
    16, 0,                       /* wMaxPacketSize = 16 */
    16,                          /* bInterval = 16ms */

    /* Interface 1: CDC Data */
    9, 4,                        /* bLength, bDescriptorType = INTERFACE */
    1,                           /* bInterfaceNumber */
    0,                           /* bAlternateSetting */
    2,                           /* bNumEndpoints */
    CDC_DATA_CLASS,              /* bInterfaceClass (CDC Data) */
    0x00,                        /* bInterfaceSubClass */
    0x00,                        /* bInterfaceProtocol */
    0,                           /* iInterface */
    /* Bulk OUT endpoint */
    7, 5,                        /* bLength, bDescriptorType = ENDPOINT */
    USB_CDC_BULK_EP_OUT,         /* bEndpointAddress (0x01 OUT) */
    EP_TYPE_BULK,                /* bmAttributes */
    USB_MAX_PACKET_SIZE & 0xFF, (USB_MAX_PACKET_SIZE >> 8) & 0xFF, /* wMaxPacketSize = 512 */
    0,                           /* bInterval */
    /* Bulk IN endpoint */
    7, 5,                        /* bLength, bDescriptorType = ENDPOINT */
    USB_CDC_BULK_EP_IN,          /* bEndpointAddress (0x82 IN) */
    EP_TYPE_BULK,                /* bmAttributes */
    USB_MAX_PACKET_SIZE & 0xFF, (USB_MAX_PACKET_SIZE >> 8) & 0xFF, /* wMaxPacketSize = 512 */
    0,                           /* bInterval */

    /* Interface 2: DFU */
    9, 4,                        /* bLength, bDescriptorType = INTERFACE */
    2,                           /* bInterfaceNumber */
    0,                           /* bAlternateSetting */
    0,                           /* bNumEndpoints */
    USB_DFU_IFACE_CLASS,         /* bInterfaceClass (0xFE = App Specific) */
    USB_DFU_IFACE_SUBCLASS,      /* bInterfaceSubClass (0x01 = DFU) */
    USB_DFU_IFACE_PROTOCOL_MODE, /* bInterfaceProtocol (0x02 = DFU Mode) */
    0,                           /* iInterface */
    /* DFU functional descriptor */
    9, USB_DT_DFU,               /* bLength, bDescriptorType = DFU func */
    (DFU_ATTR_CAN_DNLOAD),       /* bmAttributes */
    0, 0,                        /* wDetachTimeout */
    (USB_DFU_XFER_SIZE & 0xFF), ((USB_DFU_XFER_SIZE >> 8) & 0xFF), /* wTransferSize = 4096 */
    0x01, 0x01,                  /* bcdDFUVersion = 1.1 */
};

static const u8 *get_string_descriptor(u8 index, u8 *len_out)
{
    static const u8 langid[] = { 4, 3, 0x09, 0x04 };
    static const u8 mfr_str[] = {
        18, 3, 'A',0, 'p',0, 'p',0, 'l',0, 'e',0, ' ',0, 'I',0, 'n',0, 'c',0, '.',0
    };
    static const u8 prod_str[] = {
        36, 3, 'M',0, 'o',0, 'b',0, 'i',0, 'l',0, 'e',0, ' ',0,
        'D',0, 'e',0, 'v',0, 'i',0, 'c',0, 'e',0, ' ',0,
        '(',0, 'D',0, 'F',0, 'U',0, ' ',0, 'M',0, 'o',0, 'd',0, 'e',0, ')',0, 0,0
    };
    static const u8 ser_str[] = {
        24, 3, 'C',0, 'P',0, 'I',0, 'D',0, ':',0, '0',0, '0',0,
        '0',0, '0',0, '0',0, '0',0, '0',0, '0',0, '1',0, 0,0
    };
    switch (index) {
    case 0: *len_out = langid[0]; return langid;
    case 1: *len_out = mfr_str[0]; return mfr_str;
    case 2: *len_out = prod_str[0]; return prod_str;
    case 3: *len_out = ser_str[0]; return ser_str;
    default: *len_out = 0; return NULL;
    }
}

static bool send_descriptor(u8 type, u8 index, u16 langid,
                             u8 **data_ptr, usize *data_len)
{
    (void)index;
    (void)langid;
    switch (type) {
    case USB_DT_DEVICE:
        *data_ptr = (u8 *)(usize)dfu_device_descriptor;
        *data_len = dfu_device_descriptor[0];
        return true;
    case USB_DT_CONFIGURATION:
        *data_ptr = (u8 *)(usize)dfu_config_descriptor;
        *data_len = (usize)dfu_config_descriptor[2] |
                    ((usize)dfu_config_descriptor[3] << 8);
        return true;
    case USB_DT_STRING:
    {
        u8 slen = 0;
        const u8 *s = get_string_descriptor(index, &slen);
        if (s == NULL) return false;
        *data_ptr = (u8 *)(usize)s;
        *data_len = slen;
        return true;
    }
    default:
        return false;
    }
}

static void dfu_handle_dnload(u16 wLength)
{
    if (wLength == 0) {
        ctx.dfu_manifest = true;
        ctx.dfu_state = DFU_STATE_dfuMANIFEST_SYNC;
        log_info("DFU: manifest start (%llu bytes total)", (u64)ctx.dfu_img_size);
        return;
    }
    if (ctx.dfu_received + wLength > USB_IMG_BUF_SIZE) {
        ctx.dfu_status = DFU_STATUS_errFIRMWARE;
        ctx.dfu_state = DFU_STATE_dfuERROR;
        log_error("DFU: image too large (%u + %u > %u)",
                  ctx.dfu_received, wLength, USB_IMG_BUF_SIZE);
        return;
    }
    ctx.dfu_state = DFU_STATE_dfuDNLOAD_SYNC;
}

static void dfu_handle_getstatus(u8 *data)
{
    u32 timeout = 0;
    u32 poll_timeout = 0;
    u8 state = (u8)ctx.dfu_state;
    u8 status = (u8)ctx.dfu_status;
    if (data != NULL) {
        data[0] = status;
        data[1] = (u8)(timeout & 0xFF);
        data[2] = (u8)((timeout >> 8) & 0xFF);
        data[3] = (u8)((timeout >> 16) & 0xFF);
        data[4] = state;
        data[5] = (u8)(poll_timeout & 0xFF);
    }
    if (ctx.dfu_state == DFU_STATE_dfuDNLOAD_SYNC) {
        ctx.dfu_state = DFU_STATE_dfuDNLOAD_IDLE;
    } else if (ctx.dfu_state == DFU_STATE_dfuMANIFEST_SYNC) {
        ctx.dfu_state = DFU_STATE_dfuMANIFEST;
        if (ctx.dfu_img_size > 0U) {
            log_info("DFU: manifest complete, auto-executing %llu byte image",
                     (u64)ctx.dfu_img_size);
            usbliter8_load_dfu_image(ctx.dfu_img_buf, ctx.dfu_img_size, 0U);
            usbliter8_execute(0U);
        }
    }
}

static void dfu_handle_getstate(u8 *data)
{
    if (data != NULL) {
        data[0] = (u8)ctx.dfu_state;
    }
}

static void dfu_handle_clrstatus(void)
{
    ctx.dfu_status = DFU_STATUS_OK;
    ctx.dfu_state = DFU_STATE_dfuIDLE;
}

static void dfu_handle_abort(void)
{
    ctx.dfu_received = 0;
    ctx.dfu_manifest = false;
    ctx.dfu_state = DFU_STATE_dfuIDLE;
    ctx.dfu_status = DFU_STATUS_OK;
}

static int handle_cdc_request(usb_setup_packet_t *setup,
                              u8 **data_ptr, usize *data_len)
{
    u8 bRequest = setup->bRequest;
    u16 wValue = setup->wValue;
    u16 wLength = setup->wLength;
    switch (bRequest) {
    case CDC_REQ_SET_LINE_CODING:
        if (wLength < sizeof(usb_cdc_line_coding_t)) {
            return -1;
        }
        log_verbose("CDC SET_LINE_CODING");
        *data_ptr = NULL;
        *data_len = 0;
        return 0;
    case CDC_REQ_GET_LINE_CODING:
    {
        static usb_cdc_line_coding_t line_coding;
        line_coding.dwDTERate = 115200;
        line_coding.bCharFormat = 0;
        line_coding.bParityType = 0;
        line_coding.bDataBits = 8;
        *data_ptr = (u8 *)&line_coding;
        *data_len = sizeof(line_coding);
        return 0;
    }
    case CDC_REQ_SET_CONTROL_LINE_STATE:
        log_verbose("CDC SET_CONTROL_LINE_STATE: 0x%04x", wValue);
        *data_ptr = NULL;
        *data_len = 0;
        return 0;
    case CDC_REQ_SEND_BREAK:
        log_verbose("CDC SEND_BREAK: %u", wLength);
        *data_ptr = NULL;
        *data_len = 0;
        return 0;
    default:
        return -1;
    }
}

static int handle_class_request(usb_setup_packet_t *setup,
                                 u8 **data_ptr, usize *data_len)
{
    if ((setup->bmRequestType & USB_RECIP_INTERFACE) != USB_RECIP_INTERFACE) {
        return -1;
    }
    if (((setup->bmRequestType >> 5) & 3) != 1) {
        return -1;
    }
    u8 interface = (u8)(setup->wIndex & 0xFF);
    if (interface == 0 || interface == 1) {
        return handle_cdc_request(setup, data_ptr, data_len);
    }
    u8 bRequest = setup->bRequest;
    u16 wValue = setup->wValue;
    u16 wLength = setup->wLength;
    (void)wValue;
    switch (bRequest) {
    case DFU_REQ_DETACH:
        ctx.dfu_state = DFU_STATE_appDETACH;
        return 0;
    case DFU_REQ_DNLOAD:
        ctx.dfu_transfer_size = wLength;
        dfu_handle_dnload(wLength);
        *data_ptr = NULL;
        *data_len = 0;
        return 0;
    case DFU_REQ_UPLOAD:
    {
        u16 blk = setup->wValue;
        u16 len = setup->wLength;
        if (ctx.dfu_img_size == 0U || len == 0U) {
            return -1;
        }
        u32 offset = (u32)blk * USB_DFU_XFER_SIZE;
        if (offset >= ctx.dfu_img_size) {
            *data_ptr = NULL;
            *data_len = 0;
            return 0;
        }
        u32 remaining = (u32)ctx.dfu_img_size - offset;
        u32 chunk = (len < remaining) ? len : remaining;
        if (chunk > USB_DFU_XFER_SIZE) {
            chunk = USB_DFU_XFER_SIZE;
        }
        static u8 upload_buf[USB_DFU_XFER_SIZE];
        fm_memset(upload_buf, 0, USB_DFU_XFER_SIZE);
        fm_memcpy(upload_buf, ctx.dfu_img_buf + offset, chunk);
        *data_ptr = upload_buf;
        *data_len = chunk;
        ctx.dfu_state = DFU_STATE_dfuUPLOAD_IDLE;
        log_verbose("DFU: upload block %u (%u bytes at offset %u)", blk, chunk, offset);
        return 0;
    }
    case DFU_REQ_GETSTATUS:
    {
        static u8 status_resp[6];
        fm_memset(status_resp, 0, 6);
        dfu_handle_getstatus(status_resp);
        *data_ptr = status_resp;
        *data_len = 6;
        return 0;
    }
    case DFU_REQ_CLRSTATUS:
        dfu_handle_clrstatus();
        return 0;
    case DFU_REQ_GETSTATE:
    {
        static u8 state_resp[1];
        dfu_handle_getstate(state_resp);
        *data_ptr = state_resp;
        *data_len = 1;
        return 0;
    }
    case DFU_REQ_ABORT:
        dfu_handle_abort();
        return 0;
    default:
        return -1;
    }
}

bool usb_setup_handle_standard_request(usb_setup_packet_t *setup,
                                        u8 **data_ptr, usize *data_len)
{
    if (data_ptr == NULL || data_len == NULL) return false;
    u8 bmRT = setup->bmRequestType;
    u8 bReq = setup->bRequest;
    u16 wVal = setup->wValue;
    u16 wIdx = setup->wIndex;
    u8 recipient = bmRT & 0x1F;
    u8 type = (bmRT >> 5) & 3;
    if (type == 1) {
        return handle_class_request(setup, data_ptr, data_len) == 0;
    }
    if (type != 0) return false;
    if ((bmRT & USB_DIR_IN) && bReq == USB_REQ_GET_DESCRIPTOR) {
        u8 desc_type = (u8)((wVal >> 8) & 0xFF);
        u8 desc_idx = (u8)(wVal & 0xFF);
        return send_descriptor(desc_type, desc_idx, wIdx, data_ptr, data_len);
    }
    if (recipient == USB_RECIP_DEVICE && !(bmRT & USB_DIR_IN)) {
        if (bReq == USB_REQ_SET_ADDRESS) {
            u8 addr = (u8)(wVal & 0x7F);
            dwc3_set_address(addr);
            ctx.device_address = addr;
            ctx.state = USB_STATE_ADDRESS;
            log_info("USB SET_ADDRESS = %u", addr);
            return true;
        }
        if (bReq == USB_REQ_SET_CONFIGURATION) {
            ctx.configuration = (u8)(wVal & 0xFF);
            ctx.configured = (ctx.configuration != 0);
            ctx.state = USB_STATE_CONFIGURED;
            log_info("USB SET_CONFIGURATION = %u", ctx.configuration);
            if (ctx.configured) {
                dwc3_configure_cdc_endpoints();
            }
            return true;
        }
    }
    if (recipient == USB_RECIP_DEVICE && (bmRT & USB_DIR_IN)) {
        if (bReq == USB_REQ_GET_CONFIGURATION) {
            static u8 cfg_resp[1];
            cfg_resp[0] = ctx.configuration;
            *data_ptr = cfg_resp;
            *data_len = 1;
            return true;
        }
    }
    return false;
}

bool usb_set_vendor_request_handler(usb_vendor_handler_t handler)
{
    UNUSED(handler);
    return true;
}

void usb_stall_endpoint(u32 ep_cmd_reg)
{
    u32 cmd = dwc3_read32(ep_cmd_reg);
    cmd |= DWC3_DEPCMD_STALL | DWC3_DEPCMD_CMDACT;
    dwc3_write32(ep_cmd_reg, cmd);
    log_verbose("USB STALL on reg 0x%08x", (unsigned)ep_cmd_reg);
}

void usb_vendor_data_stage_complete(u8 bRequest, u32 actual_bytes)
{
    if (bRequest == VENDOR_REQ_SET_ADDR) {
        u64 addr = 0U;
        for (int i = 0; i < 8; i++) {
            addr |= (u64)ctx.vendor_buf[i] << (i * 8U);
        }
        ctx.vendor_target_addr = addr;
        log_info("VENDOR: set_addr = 0x%llx", addr);
    } else if (bRequest == VENDOR_REQ_MEM_WRITE) {
        ctx.vendor_target_addr += actual_bytes;
        log_verbose("VENDOR: mem_write advanced to 0x%llx", ctx.vendor_target_addr);
    }
    ctx.vendor_req_pending = -1;
}

static void process_setup_event(const u32 *evt_words)
{
    usb_setup_packet_t setup;
    fm_memset(&setup, 0, sizeof(setup));
    const u8 *setup_bytes = (const u8 *)(evt_words + 2);
    setup.bmRequestType = setup_bytes[0];
    setup.bRequest = setup_bytes[1];
    setup.wValue = (u16)setup_bytes[2] | ((u16)setup_bytes[3] << 8);
    setup.wIndex = (u16)setup_bytes[4] | ((u16)setup_bytes[5] << 8);
    setup.wLength = (u16)setup_bytes[6] | ((u16)setup_bytes[7] << 8);
    log_verbose("USB SETUP: rt=0x%02x rq=%u v=0x%04x i=0x%04x l=%u",
                setup.bmRequestType, setup.bRequest,
                setup.wValue, setup.wIndex, setup.wLength);
    u8 *resp_data = NULL;
    usize resp_len = 0;
    bool handled = usb_setup_handle_standard_request(&setup, &resp_data, &resp_len);
    if (handled && resp_data != NULL && resp_len > 0) {
        u32 xfer_param = (u32)resp_len;
        dwc3_write32(USB_DWC3_DEP1_CMDPAR0, (u32)(usize)resp_data);
        dwc3_write32(USB_DWC3_DEP1_CMDPAR1, xfer_param);
        dwc3_write32(USB_DWC3_DEP1_CMDPAR2, 0U);
        dwc3_write32(USB_DWC3_DEP1_CMD,
                      DWC3_DEPCMD_STARTTRANSFER |
                      DWC3_DEPCMD_PARAM(0) |
                      DWC3_DEPCMD_CMDIOC |
                      DWC3_DEPCMD_CMDACT);
        ctx.bytes_sent += (u64)resp_len;
    } else if (handled && setup.bRequest == DFU_REQ_DNLOAD &&
               ctx.dfu_transfer_size > 0 &&
               (setup.bmRequestType & USB_DIR_IN) == 0) {
        u32 buf_offset = ctx.dfu_received;
        if (buf_offset + ctx.dfu_transfer_size <= USB_IMG_BUF_SIZE) {
            dwc3_write32(USB_DWC3_DEPCMDPAR0,
                          (u32)(usize)(ctx.dfu_img_buf + buf_offset));
            dwc3_write32(USB_DWC3_DEPCMDPAR1, ctx.dfu_transfer_size);
            dwc3_write32(USB_DWC3_DEPCMDPAR2, 0U);
            dwc3_write32(USB_DWC3_DEPCMD,
                          DWC3_DEPCMD_STARTTRANSFER |
                          DWC3_DEPCMD_PARAM(0) |
                          DWC3_DEPCMD_CMDIOC |
                          DWC3_DEPCMD_CMDACT);
            log_verbose("DFU: OUT data stage prepared (%u bytes at offset %u)",
                        ctx.dfu_transfer_size, buf_offset);
        }
    }
    u8 req_type = (setup.bmRequestType >> 5) & 3U;
    if (!handled && req_type == 2U) {
        u8 vreq = setup.bRequest;
        if (vreq == VENDOR_REQ_SET_ADDR && (setup.bmRequestType & USB_DIR_IN) == 0U) {
            if (setup.wLength >= 8U) {
                ctx.vendor_req_pending = VENDOR_REQ_SET_ADDR;
                ctx.dfu_transfer_size = 8U;
                dwc3_write32(USB_DWC3_DEPCMDPAR0, (u32)(usize)ctx.vendor_buf);
                dwc3_write32(USB_DWC3_DEPCMDPAR1, 8U);
                dwc3_write32(USB_DWC3_DEPCMDPAR2, 0U);
                dwc3_write32(USB_DWC3_DEPCMD,
                             DWC3_DEPCMD_STARTTRANSFER |
                             DWC3_DEPCMD_PARAM(0) |
                             DWC3_DEPCMD_CMDIOC |
                             DWC3_DEPCMD_CMDACT);
                handled = true;
            }
        } else if (vreq == VENDOR_REQ_MEM_READ && (setup.bmRequestType & USB_DIR_IN) != 0U) {
            if (ctx.vendor_target_addr != 0U && setup.wLength > 0U) {
                resp_data = (u8 *)(usize)ctx.vendor_target_addr;
                resp_len = setup.wLength;
                ctx.vendor_target_addr += setup.wLength;
                handled = true;
                log_verbose("VENDOR: mem_read from 0x%llx, %u bytes",
                            (u64)(usize)resp_data, (unsigned)setup.wLength);
            }
        } else if (vreq == VENDOR_REQ_MEM_WRITE && (setup.bmRequestType & USB_DIR_IN) == 0U) {
            if (ctx.vendor_target_addr != 0U && setup.wLength > 0U) {
                ctx.vendor_req_pending = VENDOR_REQ_MEM_WRITE;
                ctx.dfu_transfer_size = setup.wLength;
                dwc3_write32(USB_DWC3_DEPCMDPAR0, (u32)(usize)ctx.vendor_target_addr);
                dwc3_write32(USB_DWC3_DEPCMDPAR1, setup.wLength);
                dwc3_write32(USB_DWC3_DEPCMDPAR2, 0U);
                dwc3_write32(USB_DWC3_DEPCMD,
                             DWC3_DEPCMD_STARTTRANSFER |
                             DWC3_DEPCMD_PARAM(0) |
                             DWC3_DEPCMD_CMDIOC |
                             DWC3_DEPCMD_CMDACT);
                handled = true;
                log_verbose("VENDOR: mem_write to 0x%llx, %u bytes",
                            ctx.vendor_target_addr, (unsigned)setup.wLength);
            }
        } else if (vreq == VENDOR_REQ_EXECUTE) {
            if (ctx.vendor_target_addr != 0U) {
                void (*fn)(void) = (void (*)(void))(usize)ctx.vendor_target_addr;
                log_info("VENDOR: execute at 0x%llx", ctx.vendor_target_addr);
                handled = true;
                __asm__ volatile("dsb sy" ::: "memory");
                __asm__ volatile("isb" ::: "memory");
                fn();
            }
        }
    }
    if (!handled) {
        log_verbose("USB stall on unknown setup request");
        usb_stall_endpoint(USB_DWC3_DEPCMD);
    }
    if (ctx.setup_callback != NULL) {
        usb_event_t ev;
        fm_memset(&ev, 0, sizeof(ev));
        ev.type = USB_EVENT_SETUP_PACKET;
        ev.setup = setup;
        ev.data = resp_data;
        ev.data_length = resp_len;
        ev.handled = handled;
        ctx.setup_callback(&ev);
    }
}

static void process_events(void)
{
    if (!ctx.initialized) return;
    u32 count = dwc3_read32(USB_DWC3_GEVNTCOUNT);
    if (count == 0U) {
        bool was_connected = ctx.connected;
        ctx.connected = dwc3_is_connected();
        if (ctx.connected && !was_connected) {
            ctx.state = USB_STATE_ATTACHED;
            ctx.last_connect_ms = timer_uptime_ms();
            log_info("USB connected (speed=%u)", (unsigned)dwc3_speed());
            (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE,
                                    "usb-connect", 1U, 0U);
        } else if (!ctx.connected && was_connected) {
            ctx.state = USB_STATE_DETACHED;
            ctx.configured = false;
            u64 duration = timer_uptime_ms() - ctx.last_connect_ms;
            log_info("USB disconnected after %llu ms", duration);
            (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE,
                                    "usb-disconnect", 1U, 0U);
        }
        if (ctx.connected && ctx.state == USB_STATE_ATTACHED) {
            ctx.state = USB_STATE_DEFAULT;
            ctx.speed = (usb_speed_t)dwc3_speed();
            log_verbose("USB state -> DEFAULT speed=%u",
                        (unsigned)ctx.speed);
        }
        return;
    }
    u16 num_events = (u16)(count & 0xFFFFU);
    u16 max_events = num_events;
    for (u16 i = 0; i < max_events && ctx.evt_cons_idx < DWC3_EVT_RING_ENTRIES; ++i) {
        u32 *evt = (u32 *)(ctx.evt_ring + (ctx.evt_cons_idx * 16U));
        u32 word0 = evt[0];
        u32 evt_type = (word0 >> 1) & 0x1F;
        bool ep_event = (word0 >> 7) & 1U;
        u32 ep_num = (word0 >> 8) & 0x1F;
        if (word0 == 0U) {
            ctx.evt_cons_idx = (ctx.evt_cons_idx + 1U) % DWC3_EVT_RING_ENTRIES;
            continue;
        }
        evt[0] = 0U; evt[1] = 0U; evt[2] = 0U; evt[3] = 0U;
        if (!ep_event && evt_type == DWC3_EVT_TYPE_CONNECT) {
            ctx.connected = true;
            ctx.state = USB_STATE_ATTACHED;
            log_info("USB connect event (speed=%u)", (unsigned)dwc3_speed());
        } else if (!ep_event && evt_type == DWC3_EVT_TYPE_DISCONNECT) {
            ctx.connected = false;
            ctx.state = USB_STATE_DETACHED;
            ctx.configured = false;
            log_info("USB disconnect event");
        } else if (!ep_event && evt_type == DWC3_EVT_TYPE_RESET) {
            ctx.state = USB_STATE_DEFAULT;
            ctx.configured = false;
            ctx.device_address = 0;
            ctx.configuration = 0;
            ++ctx.reset_count;
            log_info("USB bus reset");
        } else if (ep_event && evt_type == DWC3_EVT_TYPE_SETUP && ep_num == 0) {
            process_setup_event(evt);
        } else if (ep_event && evt_type == DWC3_EVT_TYPE_XFER_COMPLETE) {
            log_verbose("USB xfer complete on EP%u", (unsigned)ep_num);
            if (ep_num == 0 && ctx.vendor_req_pending >= 0) {
                u32 residual = dwc3_read32(USB_DWC3_DEPCMDPAR1);
                u32 actual = 0U;
                if (ctx.vendor_req_pending == VENDOR_REQ_SET_ADDR) {
                    actual = 8U;
                } else {
                    u32 req_size = (u32)ctx.dfu_transfer_size;
                    actual = (residual <= req_size) ? req_size - residual : req_size;
                }
                u8 pending_req = (u8)ctx.vendor_req_pending;
                ctx.vendor_req_pending = -1;
                ctx.dfu_transfer_size = 0;
                usb_vendor_data_stage_complete(pending_req, actual);
            } else if (ep_num == 0 && ctx.dfu_transfer_size > 0) {
                u32 residual = dwc3_read32(USB_DWC3_DEPCMDPAR1);
                u32 actual = (residual <= ctx.dfu_transfer_size)
                             ? ctx.dfu_transfer_size - residual
                             : ctx.dfu_transfer_size;
                ctx.dfu_img_size += actual;
                ctx.dfu_received += actual;
                ctx.dfu_transfer_size = 0;
                log_info("DFU: block received, total %llu bytes",
                         (u64)ctx.dfu_img_size);
            } else if (ep_num == 1) {
                ctx.bytes_sent += 512U;
            } else if (ep_num == 2) {
                dwc3_complete_bulk_out();
            } else if (ep_num == 3) {
                dwc3_complete_bulk_in();
            }
        }
        ctx.evt_cons_idx = (ctx.evt_cons_idx + 1U) % DWC3_EVT_RING_ENTRIES;
    }
    dwc3_write32(USB_DWC3_GEVNTCOUNT, count);
    ++ctx.irq_count;
}

void usb_init(u64 mmio_base)
{
    ctx_zero();
    ctx.mmio_base = mmio_base;
    ctx.state = USB_STATE_DETACHED;
    ctx.vendor_id = USB_APPLE_VID;
    ctx.product_id = USB_APPLE_DFU_PID;
    ctx.manufacturer = "Apple Inc.";
    ctx.product = "Mobile Device (DFU Mode)";
    ctx.serial = "CPID:00000001";
    ctx.dfu_state = DFU_STATE_appIDLE;
    ctx.dfu_status = DFU_STATUS_OK;
    ctx.dfu_mode = true;
    log_info("USB init at 0x%llx (Apple DFU mode)", mmio_base);
    if (mmio_base == 0U) {
        log_error("USB: zero MMIO base, init skipped");
        ctx.initialized = false;
        return;
    }
    ctx.initialized = true;
    if (!dwc3_check_id()) {
        log_warn("USB DWC3 not found at 0x%llx (GSNPSID mismatch)", mmio_base);
        ctx.initialized = false;
        return;
    }
    if (!dwc3_core_init()) {
        log_error("USB DWC3 core init FAILED at 0x%llx", mmio_base);
        ctx.initialized = false;
        return;
    }
    if (!dwc3_event_ring_init()) {
        log_error("USB DWC3 event ring FAILED at 0x%llx", mmio_base);
        ctx.initialized = false;
        return;
    }
    dwc3_enable_events();
    dwc3_ep0_configure();
    dwc3_connect();
    log_info("USB DWC3 ready at 0x%llx (DFU mode, VID=0x%04x PID=0x%04x)",
             mmio_base, USB_APPLE_VID, USB_APPLE_DFU_PID);
    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE,
                            "usb-init", 1U, 0U);
}

void usb_shutdown(void)
{
    if (ctx.initialized) {
        log_verbose("USB shutdown");
        dwc3_disconnect();
        ctx.initialized = false;
        ctx.state = USB_STATE_DETACHED;
    }
}

bool usb_ready(void)
{
    return ctx.initialized;
}

bool usb_healthy(void)
{
    return ctx.initialized && ctx.state >= USB_STATE_DEFAULT;
}

usb_device_status_t usb_status(void)
{
    usb_device_status_t status;
    fm_memset(&status, 0, sizeof(status));
    status.mmio_base = ctx.mmio_base;
    status.state = ctx.state;
    status.speed = ctx.speed;
    status.device_address = ctx.device_address;
    status.configuration = ctx.configuration;
    status.configured = ctx.configured;
    status.connected = ctx.connected;
    status.bytes_received = ctx.bytes_received;
    status.bytes_sent = ctx.bytes_sent;
    return status;
}

bool usb_configure(const usb_device_config_t *config)
{
    if (config == NULL) {
        log_warn("USB configure: NULL config");
        return false;
    }
    if (!ctx.initialized) {
        log_warn("USB configure: not initialized");
        return false;
    }
    ctx.vendor_id = config->vendor_id;
    ctx.product_id = config->product_id;
    ctx.manufacturer = config->manufacturer_string;
    ctx.product = config->product_string;
    ctx.serial = config->serial_string;
    ctx.setup_callback = config->setup_callback;
    ctx.bulk_out_callback = config->bulk_out_callback;
    ctx.bulk_in_callback = config->bulk_in_callback;
    log_verbose("USB configured: VID=0x%04x PID=0x%04x",
                config->vendor_id, config->product_id);
    return true;
}

bool usb_configure_dfu(void)
{
    if (!ctx.initialized) {
        log_warn("USB DFU configure: not initialized");
        return false;
    }
    ctx.vendor_id = USB_APPLE_VID;
    ctx.product_id = USB_APPLE_DFU_PID;
    ctx.manufacturer = "Apple Inc.";
    ctx.product = "Mobile Device (DFU Mode)";
    ctx.serial = "CPID:00000001";
    ctx.dfu_mode = true;
    ctx.dfu_state = DFU_STATE_appIDLE;
    ctx.dfu_status = DFU_STATUS_OK;
    ctx.dfu_received = 0;
    ctx.dfu_img_size = 0;
    log_info("USB configured for Apple DFU mode: VID=0x%04x PID=0x%04x",
             USB_APPLE_VID, USB_APPLE_DFU_PID);
    (void)event_bus_publish(FBR34KER_EVENT_COMPONENT_STATE,
                            "usb-dfu-mode", 1U, 0U);
    return true;
}

bool usb_set_address(u8 address)
{
    if (address > USB_MAX_DEVICE_ADDRESS) {
        log_warn("USB set_address: invalid %u", address);
        return false;
    }
    if (!ctx.initialized) {
        log_warn("USB set_address: not initialized");
        return false;
    }
    dwc3_set_address(address);
    ctx.device_address = address;
    ctx.state = USB_STATE_ADDRESS;
    log_verbose("USB address set to %u", address);
    return true;
}

bool usb_send(const u8 *data, usize length)
{
    if (!ctx.initialized || !ctx.configured || data == NULL) {
        return false;
    }
    for (usize i = 0U; i < length; ++i) {
        if (!write_tx_buffer(data[i])) {
            log_trace("USB send: tx buffer full at byte %llu/%llu",
                      (u64)i, (u64)length);
            break;
        }
    }
    ctx.bytes_sent += (u64)length;
    if (ctx.bulk_in_callback != NULL) {
        usb_event_t ev;
        fm_memset(&ev, 0, sizeof(ev));
        ev.type = USB_EVENT_BULK_IN_COMPLETE;
        ev.data = (u8 *)data;
        ev.data_length = length;
        ctx.bulk_in_callback(&ev);
    }
    return true;
}

usize usb_receive(u8 *buffer, usize max_length)
{
    if (!ctx.initialized || buffer == NULL || max_length == 0U) {
        return 0U;
    }
    usize count = 0U;
    while (count < max_length && rx_available()) {
        buffer[count] = read_rx_buffer();
        ++count;
    }
    ctx.bytes_received += (u64)count;
    if (count > 0U) {
        log_trace("USB receive: %llu bytes", (u64)count);
    }
    return count;
}

bool usb_console_putc(char c)
{
    if (!ctx.configured) return false;
    return write_tx_buffer((u8)c);
}

int usb_console_getc(void)
{
    if (!rx_available()) return -1;
    return (int)read_rx_buffer();
}

void usb_irq_handler(void)
{
    if (!ctx.initialized) return;
    process_events();
}

bool usb_is_connected(void)
{
    return ctx.connected && ctx.configured;
}

bool usb_dfu_in_progress(void)
{
    return ctx.dfu_img_size > 0 && ctx.dfu_state <= DFU_STATE_dfuMANIFEST;
}

usize usb_dfu_image_size(void)
{
    return ctx.dfu_img_size;
}

const u8 *usb_dfu_image_data(void)
{
    return ctx.dfu_img_buf;
}

void usb_dfu_reset_image(void)
{
    fm_memset(ctx.dfu_img_buf, 0, USB_IMG_BUF_SIZE);
    ctx.dfu_img_size = 0;
    ctx.dfu_received = 0;
    ctx.dfu_manifest = false;
}
