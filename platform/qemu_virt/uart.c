#include "fbr34ker/platform.h"

#define PL011_BASE 0x09000000ULL
#define UART_DR    0x000U
#define UART_FR    0x018U
#define UART_IBRD  0x024U
#define UART_FBRD  0x028U
#define UART_LCRH  0x02CU
#define UART_CR    0x030U
#define UART_IMSC  0x038U
#define UART_ICR   0x044U

#define UART_FR_RXFE (1U << 4)
#define UART_FR_TXFF (1U << 5)
#define UART_LCRH_FEN (1U << 4)
#define UART_LCRH_WLEN_8 (3U << 5)
#define UART_CR_UARTEN (1U << 0)
#define UART_CR_TXE (1U << 8)
#define UART_CR_RXE (1U << 9)

static volatile u32 *uart_register(u32 offset)
{
    return (volatile u32 *)(usize)(PL011_BASE + offset);
}

static u32 uart_read(u32 offset)
{
    return *uart_register(offset);
}

static void uart_write(u32 offset, u32 value)
{
    *uart_register(offset) = value;
}

void qemu_uart_init(void)
{
    uart_write(UART_CR, 0U);
    uart_write(UART_ICR, 0x7FFU);
    uart_write(UART_IMSC, 0U);

    /* QEMU virt PL011 uses a 24 MHz reference clock. */
    uart_write(UART_IBRD, 13U);
    uart_write(UART_FBRD, 1U);
    uart_write(UART_LCRH, UART_LCRH_WLEN_8 | UART_LCRH_FEN);
    uart_write(UART_CR, UART_CR_UARTEN | UART_CR_TXE | UART_CR_RXE);
}

void platform_uart_putc(char value)
{
    while ((uart_read(UART_FR) & UART_FR_TXFF) != 0U) {
        __asm__ volatile("yield");
    }
    uart_write(UART_DR, (u32)(u8)value);
}

int platform_uart_getc_nonblocking(void)
{
    if ((uart_read(UART_FR) & UART_FR_RXFE) != 0U) {
        return -1;
    }
    return (int)(uart_read(UART_DR) & 0xFFU);
}
