# Callback safety contract

External-loader callbacks cross the monitor/loader trust boundary. FBR34KER
0.6.0_beta applies the following checks before and during use:

- callback pointers must be non-null when their capability is advertised;
- callback addresses must be 4-byte aligned;
- callback code must lie in a loader-declared readable/executable region;
- platform service tables must be loader-owned, readable, aligned, and sized;
- recursive entry into the same service is denied;
- calls, failures, recursion denials, and budget overruns are counted;
- repeatedly failing services are disabled and the monitor falls back safely;
- `service-health` reports status without invoking any service.

Timing budgets are **post-return soft budgets**. A callback that never returns
cannot be preempted by a freestanding monitor without a separately validated
interrupt/timer isolation mechanism. Loaders must keep callbacks bounded and
must not hold locks shared with monitor code.

Console and power callbacks have explicit recursion protection. Power actions
remain locked in the immutable physical probe. Crash evidence and the memory
ring console remain available when an external service is disabled.
