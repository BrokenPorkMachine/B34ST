#pragma once
// SPDX-License-Identifier: BSD-2-Clause
#include "fbr34ker/types.h"

#define USB_MAX_ENDPOINTS 8U
#define USB_DWC3_MMIO_BASE 0x860000000ULL
#define USB_DWC3_MMIO_SIZE 0x100000ULL
#define USB_BUFFER_SIZE 4096U
#define USB_MAX_PACKET_SIZE 512U
#define USB_CDC_ACM_INTERFACE 0U
#define USB_CDC_DATA_INTERFACE 1U
#define USB_CDC_BULK_EP_OUT 0x01U
#define USB_CDC_BULK_EP_IN 0x82U
#define USB_CDC_NOTIFICATION_EP 0x83U

#define USB_EVT_RING_SIZE 256U
#define USB_DFU_XFER_SIZE 4096U
#define USB_IMG_BUF_SIZE (1024U * 1024U)

typedef enum {
    USB_SPEED_UNKNOWN = 0,
    USB_SPEED_LOW,
    USB_SPEED_FULL,
    USB_SPEED_HIGH,
    USB_SPEED_SUPER
} usb_speed_t;

typedef enum {
    USB_STATE_DETACHED = 0,
    USB_STATE_ATTACHED,
    USB_STATE_POWERED,
    USB_STATE_DEFAULT,
    USB_STATE_ADDRESS,
    USB_STATE_CONFIGURED,
    USB_STATE_SUSPENDED
} usb_device_state_t;

typedef enum {
    USB_EVENT_RESET = 0,
    USB_EVENT_CONNECT,
    USB_EVENT_DISCONNECT,
    USB_EVENT_SUSPEND,
    USB_EVENT_RESUME,
    USB_EVENT_SETUP_PACKET,
    USB_EVENT_BULK_OUT,
    USB_EVENT_BULK_IN_COMPLETE
} usb_event_type_t;

typedef struct {
    u8 bmRequestType;
    u8 bRequest;
    u16 wValue;
    u16 wIndex;
    u16 wLength;
} PACKED usb_setup_packet_t;

typedef struct {
    usb_event_type_t type;
    usb_setup_packet_t setup;
    u8 *data;
    usize data_length;
    u8 endpoint;
    bool handled;
} usb_event_t;

typedef struct {
    u8 bLength;
    u8 bDescriptorType;
    u16 bcdUSB;
    u8 bDeviceClass;
    u8 bDeviceSubClass;
    u8 bDeviceProtocol;
    u8 bMaxPacketSize0;
    u16 idVendor;
    u16 idProduct;
    u16 bcdDevice;
    u8 iManufacturer;
    u8 iProduct;
    u8 iSerialNumber;
    u8 bNumConfigurations;
} PACKED usb_device_descriptor_t;

typedef struct {
    u8 bLength;
    u8 bDescriptorType;
    u16 wTotalLength;
    u8 bNumInterfaces;
    u8 bConfigurationValue;
    u8 iConfiguration;
    u8 bmAttributes;
    u8 bMaxPower;
} PACKED usb_config_descriptor_t;

typedef struct {
    u8 bLength;
    u8 bDescriptorType;
    u8 bInterfaceNumber;
    u8 bAlternateSetting;
    u8 bNumEndpoints;
    u8 bInterfaceClass;
    u8 bInterfaceSubClass;
    u8 bInterfaceProtocol;
    u8 iInterface;
} PACKED usb_interface_descriptor_t;

typedef struct {
    u8 bLength;
    u8 bDescriptorType;
    u8 bEndpointAddress;
    u8 bmAttributes;
    u16 wMaxPacketSize;
    u8 bInterval;
} PACKED usb_endpoint_descriptor_t;

typedef struct {
    u8 bFunctionLength;
    u8 bDescriptorType;
    u8 bDescriptorSubtype;
    u8 bmCapabilities;
    u8 bDataInterface;
} PACKED usb_cdc_header_func_desc_t;

typedef struct {
    u8 bFunctionLength;
    u8 bDescriptorType;
    u8 bDescriptorSubtype;
    u8 bmCapabilities;
} PACKED usb_cdc_call_mgmt_desc_t;

typedef struct {
    u8 bFunctionLength;
    u8 bDescriptorType;
    u8 bDescriptorSubtype;
    u8 bDataInterface;
} PACKED usb_cdc_acm_desc_t;

typedef struct {
    u8 bFunctionLength;
    u8 bDescriptorType;
    u8 bDescriptorSubtype;
    u8 iMaster;
    u8 bControl0;
    u8 bControl1;
} PACKED usb_cdc_union_desc_t;

typedef struct {
    u8 bLength;
    u8 bDescriptorType;
    u8 bmAttributes;
    u16 wDetachTimeOut;
    u16 wTransferSize;
    u16 bcdDFUVersion;
} PACKED usb_dfu_func_desc_t;

typedef struct {
    u8 bLength;
    u8 bDescriptorType;
    u8 bFirstInterface;
    u8 bInterfaceCount;
    u8 bFunctionClass;
    u8 bFunctionSubClass;
    u8 bFunctionProtocol;
    u8 iFunction;
} PACKED usb_iad_descriptor_t;

typedef struct {
    u32 dwDTERate;
    u8 bCharFormat;
    u8 bParityType;
    u8 bDataBits;
} PACKED usb_cdc_line_coding_t;

typedef void (*usb_callback_t)(usb_event_t *event);

typedef struct {
    u32 vendor_id;
    u32 product_id;
    const char *manufacturer_string;
    const char *product_string;
    const char *serial_string;
    usb_callback_t setup_callback;
    usb_callback_t bulk_out_callback;
    usb_callback_t bulk_in_callback;
} usb_device_config_t;

typedef struct {
    u64 mmio_base;
    u64 mmio_size;
    usb_speed_t speed;
    usb_device_state_t state;
    u8 device_address;
    u8 configuration;
    bool configured;
    bool connected;
    u32 last_irq_status;
    u64 bytes_received;
    u64 bytes_sent;
    u8 rx_buffer[USB_BUFFER_SIZE];
    u8 tx_buffer[USB_BUFFER_SIZE];
    usize rx_count;
    usize tx_count;
    bool tx_ready;
    bool rx_ready;
} usb_device_status_t;

typedef enum {
    DFU_STATE_appIDLE = 0,
    DFU_STATE_appDETACH,
    DFU_STATE_dfuIDLE,
    DFU_STATE_dfuDNLOAD_SYNC,
    DFU_STATE_dfuDNBUSY,
    DFU_STATE_dfuDNLOAD_IDLE,
    DFU_STATE_dfuMANIFEST_SYNC,
    DFU_STATE_dfuMANIFEST,
    DFU_STATE_dfuMANIFEST_WAIT_RESET,
    DFU_STATE_dfuUPLOAD_IDLE,
    DFU_STATE_dfuERROR,
} dfu_state_t;

typedef enum {
    DFU_STATUS_OK = 0x00,
    DFU_STATUS_errTARGET = 0x01,
    DFU_STATUS_errFILE = 0x02,
    DFU_STATUS_errWRITE = 0x03,
    DFU_STATUS_errERASE = 0x04,
    DFU_STATUS_errCHECK_ERASED = 0x05,
    DFU_STATUS_errPROG = 0x06,
    DFU_STATUS_errVERIFY = 0x07,
    DFU_STATUS_errADDRESS = 0x08,
    DFU_STATUS_errNOTDONE = 0x09,
    DFU_STATUS_errFIRMWARE = 0x0A,
    DFU_STATUS_errVENDOR = 0x0B,
    DFU_STATUS_errUSBR = 0x0C,
    DFU_STATUS_errPOR = 0x0D,
    DFU_STATUS_errUNKNOWN = 0x0E,
    DFU_STATUS_errSTALLEDPKT = 0x0F,
} dfu_status_t;

bool usb_configure_dfu(void);
void usb_init(u64 mmio_base);
void usb_shutdown(void);
bool usb_ready(void);
bool usb_healthy(void);
usb_device_status_t usb_status(void);
bool usb_configure(const usb_device_config_t *config);
bool usb_set_address(u8 address);
bool usb_send(const u8 *data, usize length);
usize usb_receive(u8 *buffer, usize max_length);
bool usb_console_putc(char c);
int usb_console_getc(void);
void usb_irq_handler(void);
bool usb_is_connected(void);
bool usb_dfu_in_progress(void);
usize usb_dfu_image_size(void);
const u8 *usb_dfu_image_data(void);
void usb_dfu_reset_image(void);
bool usb_setup_handle_standard_request(usb_setup_packet_t *setup, u8 **data_ptr, usize *data_len);
typedef int (*usb_vendor_handler_t)(usb_setup_packet_t *setup, u8 **data_ptr, usize *data_len);
bool usb_set_vendor_request_handler(usb_vendor_handler_t handler);
void usb_vendor_data_stage_complete(u8 bRequest, u32 actual_bytes);
void usb_stall_endpoint(u32 ep_cmd_reg);

#define USB_DWC3_GSNPSID 0x33373453U
#define USB_DWC3_DCFG 0xC700U
#define USB_DWC3_DCTL 0xC704U
#define USB_DWC3_DEVTEN 0xC708U
#define USB_DWC3_DSTS 0xC70CU
#define USB_DWC3_DGCMDPAR 0xC710U
#define USB_DWC3_DGCMD 0xC714U
#define USB_DWC3_DALEPENA 0xC720U
#define USB_DWC3_DEPCMDPAR0 0xC800U
#define USB_DWC3_DEPCMDPAR1 0xC804U
#define USB_DWC3_DEPCMDPAR2 0xC808U
#define USB_DWC3_DEPCMD 0xC80CU
#define USB_DWC3_DEPCFG 0xC810U
#define USB_DWC3_GCTL 0xC100U
#define USB_DWC3_GUSB3PIPECTL 0xC2C0U
#define USB_DWC3_GUSB2PHYCFG 0xC2E0U
#define USB_DWC3_GEVNTADRLO 0xC400U
#define USB_DWC3_GEVNTADRHI 0xC404U
#define USB_DWC3_GEVNTSIZ 0xC408U
#define USB_DWC3_GEVNTCOUNT 0xC40CU
#define USB_DWC3_GHWPARAMS0 0xC040U
#define USB_DWC3_GHWPARAMS1 0xC044U
#define USB_DWC3_GHWPARAMS2 0xC048U
#define USB_DWC3_GHWPARAMS3 0xC04CU
#define USB_DWC3_GHWPARAMS4 0xC050U
#define USB_DWC3_GHWPARAMS5 0xC054U
#define USB_DWC3_GHWPARAMS6 0xC058U
#define USB_DWC3_GHWPARAMS7 0xC05CU
#define USB_DWC3_GDBGFIFOSPACE 0xC1000U
#define USB_DWC3_EP0_PHYS_START 0xC900U
#define USB_DWC3_DEP1_CMDPAR0 0xC900U
#define USB_DWC3_DEP1_CMDPAR1 0xC904U
#define USB_DWC3_DEP1_CMDPAR2 0xC908U
#define USB_DWC3_DEP1_CMD    0xC90CU
#define USB_DWC3_DEP2_CMDPAR0 0xCA00U
#define USB_DWC3_DEP2_CMDPAR1 0xCA04U
#define USB_DWC3_DEP2_CMDPAR2 0xCA08U
#define USB_DWC3_DEP2_CMD    0xCA0CU
#define USB_DWC3_DEP2_CFG    0xCA10U
#define USB_DWC3_DEP3_CMDPAR0 0xCB00U
#define USB_DWC3_DEP3_CMDPAR1 0xCB04U
#define USB_DWC3_DEP3_CMDPAR2 0xCB08U
#define USB_DWC3_DEP3_CMD    0xCB0CU
#define USB_DWC3_DEP3_CFG    0xCB10U
#define USB_DWC3_DEP4_CMDPAR0 0xCC00U
#define USB_DWC3_DEP4_CMDPAR1 0xCC04U
#define USB_DWC3_DEP4_CMDPAR2 0xCC08U
#define USB_DWC3_DEP4_CMD    0xCC0CU
#define USB_DWC3_DEP4_CFG    0xCC10U

#define DWC3_DCFG_DEVADDR(addr) ((addr) << 3)
#define DWC3_DCFG_DEVSPEED(speed) ((speed) << 0)
#define DWC3_DCTL_RUN_STOP (1U << 31)
#define DWC3_DCTL_CSFTRST (1U << 30)
#define DWC3_DSTS_CONNECTSPD (0x7U << 0)
#define DWC3_DSTS_DCNRD (1U << 29)
#define DWC3_DEVTEN_ULSTCNGEN (1U << 4)
#define DWC3_DEVTEN_CONNECTDETEN (1U << 3)
#define DWC3_DEVTEN_USBRSTEN (1U << 1)
#define DWC3_DEVTEN_EVNTOVERFLOWEN (1U << 0)

#define DWC3_DEPEVT_SETUPPHASE 4U
#define DWC3_DEPEVT_XFERCOMPLETE 6U
#define DWC3_DEPEVT_CMDCMPLT 2U
#define DWC3_DEVT_WESHORTR 36U

#define DWC3_DEPCFG_EP_NUMBER(n) ((n) << 0)
#define DWC3_DEPCFG_EP_TYPE(t) ((t) << 1)
#define DWC3_DEPCFG_FIFO_BASE(s) ((s) << 17)
#define DWC3_DEPCFG_MAX_PACKET_SIZE(s) ((s) << 22)
#define DWC3_DEPCFG_ACTION_INIT 0x3U
#define DWC3_DEPCFG_ACTION_RESTORE 0x2U
#define DWC3_DEPCFG_ACTION_MODIFY 0x1U

#define DWC3_DEPCMD_DEPSTARTCFG (3U << 0)
#define DWC3_DEPCMD_ENDTRANSFER (4U << 0)
#define DWC3_DEPCMD_STARTTRANSFER (5U << 0)
#define DWC3_DEPCMD_CMDIOC (1U << 31)
#define DWC3_DEPCMD_PARAM(n) ((n) << 16)
#define DWC3_DEPCMD_CMDACT (1U << 10)
#define DWC3_DEPCMD_HIPRI_FORCERM (1U << 11)
#define DWC3_DEPCMD_STALL (1U << 29)

#define VENDOR_REQ_SET_ADDR   0x01
#define VENDOR_REQ_MEM_READ   0x02
#define VENDOR_REQ_MEM_WRITE  0x03
#define VENDOR_REQ_EXECUTE    0x04

#define USB_DWC3_GDBGLSP     0xC1004U
#define USB_DWC3_GDBGMULT    0xC1008U
#define USB_DWC3_GDBGDBG     0xC100CU

#define USB_DIR_OUT 0
#define USB_DIR_IN (1U << 7)
#define USB_TYPE_STANDARD (0U << 5)
#define USB_TYPE_CLASS (1U << 5)
#define USB_TYPE_VENDOR (2U << 5)
#define USB_RECIP_DEVICE 0
#define USB_RECIP_INTERFACE 1
#define USB_RECIP_ENDPOINT 2

#define USB_REQ_GET_DESCRIPTOR 6
#define USB_REQ_SET_ADDRESS 5
#define USB_REQ_SET_CONFIGURATION 9
#define USB_REQ_GET_CONFIGURATION 8
#define USB_REQ_GET_INTERFACE 10
#define USB_REQ_SET_INTERFACE 11

#define USB_DT_DEVICE 1
#define USB_DT_CONFIGURATION 2
#define USB_DT_STRING 3
#define USB_DT_INTERFACE 4
#define USB_DT_ENDPOINT 5
#define USB_DT_CS_INTERFACE 36
#define USB_DT_IAD 0x0B
#define USB_DT_DFU 0x21

#define DFU_REQ_DETACH 0
#define DFU_REQ_DNLOAD 1
#define DFU_REQ_UPLOAD 2
#define DFU_REQ_GETSTATUS 3
#define DFU_REQ_CLRSTATUS 4
#define DFU_REQ_GETSTATE 5
#define DFU_REQ_ABORT 6

#define DFU_ATTR_WILL_DETACH (1U << 3)
#define DFU_ATTR_MANIFESTATION_TOLERANT (1U << 2)
#define DFU_ATTR_CAN_UPLOAD (1U << 1)
#define DFU_ATTR_CAN_DNLOAD (1U << 0)

#define CDC_CLASS 2U
#define CDC_DATA_CLASS 0x0AU
#define CDC_SUBCLASS_ACM 2U
#define CDC_SUBCLASS_NCM 13U
#define CDC_PROTOCOL_AT 1U
#define CDC_PROTOCOL_NONE 0U

#define CS_INTERFACE 0x24U
#define CDC_HEADER 0U
#define CDC_CALL_MGMT 1U
#define CDC_ACM 2U
#define CDC_UNION 6U

#define EP_TYPE_BULK 2U
#define EP_TYPE_INTERRUPT 3U

#define CDC_REQ_SET_LINE_CODING 0x20U
#define CDC_REQ_GET_LINE_CODING 0x21U
#define CDC_REQ_SET_CONTROL_LINE_STATE 0x22U
#define CDC_REQ_SEND_BREAK 0x23U

#define USB_DFU_IFACE_CLASS 0xFEU
#define USB_DFU_IFACE_SUBCLASS 0x01U
#define USB_DFU_IFACE_PROTOCOL_RUNTIME 0x01U
#define USB_DFU_IFACE_PROTOCOL_MODE 0x02U
#define USB_APPLE_VID 0x05ACU
#define USB_APPLE_DFU_PID 0x1227U
