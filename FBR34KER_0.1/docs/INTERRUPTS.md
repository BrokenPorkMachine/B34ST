# Interrupt-controller support

FBR34KER chooses one of three modes:

1. loader-provided acknowledge/complete/enable callbacks;
2. direct GICv2 or GICv3 discovered from the validated FDT or fixed QEMU platform data;
3. polling-only mode when no controller is available.

## GICv2

The compact driver initializes the distributor and CPU interface, sets the priority mask, acknowledges and completes interrupts, and enables/disables sources through distributor registers.

## GICv3

The driver enables the EL1 system-register interface, uses `ICC_IAR1_EL1` and `ICC_EOIR1_EL1`, and controls distributor SPIs. SGI/PPI redistributor programming is intentionally not implemented; IDs below 32 are rejected in direct GICv3 mode.

## Safe self-test

`irq-selftest` toggles the highest available SPI enable bit and disables it immediately. It does not register a device handler, trigger an interrupt, or enable CPU delivery for an arbitrary source.

IRQ delivery begins masked. Handlers are installed before sources are enabled, failed enable operations roll back registration, and unhandled sources are disabled.
