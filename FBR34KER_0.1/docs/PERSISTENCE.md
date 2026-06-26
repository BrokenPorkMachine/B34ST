# Persistence state model

This module models bounded persistence-related state for policy, status, and
failure-path testing. It does not write a filesystem, create launchd jobs,
load kernel extensions, hide files or processes, resist removal, or survive a
reboot or software update.

Release builds keep all mutation functions disabled. The compatibility target
`make establish-persistence` writes a text inventory of modeled concepts; it
does not connect to or modify a target.

The `persistence status` shell command reports inactive in-memory state.
Deployment, activation, and evasion subcommands are rejected by the release
policy gate.
