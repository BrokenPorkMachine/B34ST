# Board description layer

The board layer converts platform, loader, and validated FDT information into a
fixed-capacity `fbr34ker_board_descriptor_t`.

Selection order:

1. The direct QEMU build selects the built-in `qemu-virt-arm64` profile.
2. The generic build records loader-handoff ownership when a handoff is active.
3. A validated FDT may refine the root compatibility string and add recognized
   PL011, GICv2/GICv3, and SP805 resources.
4. Unknown systems retain the `generic-arm64` fallback rather than guessing
   device addresses.

Each device records a type, compatibility string, base, size, clock, interrupt,
and flags. DTB devices are marked as discovered but are not active-probe-safe by
default. Board capacity is 16 devices and no dynamic allocation is used.

The built-in QEMU profile is also represented in
`profiles/qemu-virt-board.json`. `profiles/generic-arm64-board.json` documents
the generic selection and safety policy.
