# Physical-memory ownership

The physical-memory manager tracks ownership at a 4 KiB page granularity using
fixed tables:

- 16 usable ranges;
- 64 reserved ranges; and
- 128 active allocations.

Platform usable ranges are page-trimmed. Monitor, MMIO, framebuffer, firmware,
and other non-usable platform regions are reserved. FDT reservation-map entries
are imported after validation.

Allocation is first-fit across usable ranges with power-of-two page alignment.
Candidates must not overlap a reservation or existing allocation. Free requires
the exact base and page count originally allocated.

The subsystem plans ownership only. It does not configure page tables, map
unowned addresses, or provide a physical-memory read/write command.
