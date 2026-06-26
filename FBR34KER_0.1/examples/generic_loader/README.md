# Generic authorized-loader adapter

This directory demonstrates construction of a handoff-v4 object and transfer to an already loaded FBR34KER generic ARM64 image. It is intentionally transport- and device-neutral.

`fbr34ker_loader_config_t` accepts resident memory regions, optional boot modules, FDT and framebuffer descriptors, optional platform service callbacks, legacy-compatible runtime input/timer/power callbacks, platform identity, and module policy.

The adapter validates obvious local configuration errors, copies descriptors into a resident workspace, sets flags consistently, and calls the supplied monitor entry point. FBR34KER performs the authoritative validation again at boot.

The example does not locate devices, obtain execution, change firmware security state, patch protected memory, or contain platform offsets. A loader author must only integrate it in an environment they are authorized to control.
