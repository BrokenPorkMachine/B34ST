#!/usr/bin/env python3
"""B34ST (B34KER/STAR) - Runtime Authentication Tool

B34ST provides deterministic physical validation and bridge verification
for A12/A13 iPhone hardware bring-up with evidence-based maturity enforcement.

This is the main entry point for the B34ST validation framework.
"""

from __future__ import annotations

import sys

from b34st.version import __version__, __release_name__
from b34st.engine import B34STCLI
from b34st.control_panel import run_control_panel


def main() -> int:
    """Main B34ST entry point."""
    cli = B34STCLI()

    if len(sys.argv) == 1 and "--help" not in sys.argv:
        if sys.stdin.isatty() and sys.stdout.isatty():
            return run_control_panel()
        print("B34ST - FBR34KER Runtime Authentication Tool")
        print(f"Version {__version__} ({__release_name__})")
        print("\nB34ST (B34KER/STAR) - Runtime Authentication Tool")
        print(f"Version {__version__} ({__release_name__})")
        print("\nB34ST provides deterministic physical validation and bridge verification")
        print("for A12/A13 iPhone hardware bring-up with evidence-based maturity enforcement.")
        print("\nThis is the main entry point for the B34ST validation framework.\n")
        print("\nAvailable commands:")
        print("  b34st control-panel           Open the operator control panel")
        print("  b34st validate-session         Validate a session bundle")
        print("  b34st physical-validation       Perform physical validation operations")
        print("  b34st hardware-prepare         Read-only hardware preparation")
        print("  b34st environment-plan         Plan an iOS 17+ research environment")
        print("  b34st environment-validate     Validate an environment manifest")
        print("  b34st forensics                Forensics and data acquisition")
        print("  b34st forensics secrets         iCloud/Keychain/Keybag acquisition")
        print("  b34st forensics activation      Activation bypass, baseband, FMI control")
        print("  b34st forensics passcode        Passcode on/off/change/bypass")
        print("  b34st cve                      CVE database & exploit chain planner")
        print("  b34st cve search <q>            Search CVEs")
        print("  b34st cve query <v>             Get CVEs for iOS version")
        print("  b34st cve stats                 Database statistics")
        print("  b34st cve chain <g> <v>         Plan exploit chain")
        print("  b34st cve suggest <v>           Suggest achievable goals")
        print("  b34st cve goals                 List exploit goals")
        print("\nCommand-specific help:")
        print("  b34st <command> --help\n")
        print("Examples:")
        print("  b34st validate-session --bundle runtime-artifacts/success-session.zip")
        print("  b34st physical-validation candidate-report --success success.zip --failure failure.zip --recovered recovered.zip --output report.json")
        print("  b34st hardware-prepare --save-checklists ./checklists/\n")
        print("B34ST v0.2.3 is part of FBR34KER 0.2.3 Physical Validation Candidate\n")
        print("For detailed documentation, see b34st/README.md and b34st/.b34st-config\n")
        return 0

    return cli.run(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
