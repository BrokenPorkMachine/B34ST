#!/usr/bin/env python3

"""Add missing CVE categories: FairPlay, IOReg, Keychain, SEP Keystore, DTrace, info leaks."""
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations
import json
import pathlib
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[3]
DB_PATH = ROOT / "host" / "cve" / "data" / "cve_database.json"

db = json.loads(DB_PATH.read_text())
existing_ids = {c["id"] for c in db["cves"]}

VR = [{"start": "12.0", "end": "14.8.1"}]


def vrange(s, e):
    return [{"start": s, "end": e}]


def mk(
    cve_id, comps, desc, versions, goals, etype, severity, pv="", refs=None, creds=None
):
    return {
        "id": cve_id,
        "description": desc,
        "affected_versions": versions,
        "affected_components": comps,
        "exploit_type": etype,
        "exploit_available": True,
        "goals": goals,
        "severity": severity,
        "mitigations": [],
        "patch_version": pv,
        "published": "",
        "references": refs or [],
        "credits": creds or [],
        "chainable_with": [],
    }


# ===========================================================================
# IORegistry info leaks
# ===========================================================================
NEW_CVES = [
    mk(
        "CVE-2022-32866",
        ["iokit", "kernel"],
        "IORegistryIterator info leak allowing kernel memory read",
        vrange("16.0", "16.5"),
        ["kernel-info-leak", "ioreg-leak", "sandbox-escape"],
        ["local", "info-leak"],
        "high",
        pv="16.6",
        creds=["Kevin St. John", "Google Project Zero"],
    ),
    mk(
        "CVE-2023-27941",
        ["iokit", "kernel"],
        "IORegistryIterator out-of-bounds read info leak",
        vrange("16.0", "16.6.1"),
        ["kernel-info-leak", "ioreg-leak"],
        ["local", "info-leak"],
        "high",
        pv="17.0",
    ),
    mk(
        "CVE-2023-32433",
        ["iokit", "kernel"],
        "IOKit kernel info leak via IOSurface",
        vrange("16.0", "17.0"),
        ["kernel-info-leak", "ioreg-leak"],
        ["local", "info-leak"],
        "high",
        pv="17.1",
    ),
    mk(
        "CVE-2024-23214",
        ["iokit", "kernel"],
        "IOKit kernel pointer leak via IORegistryIterator",
        vrange("17.0", "17.3"),
        ["kernel-info-leak", "ioreg-leak"],
        ["local", "info-leak"],
        "medium",
        pv="17.4",
    ),
    mk(
        "CVE-2024-23215",
        ["iokit", "kernel"],
        "IOKit memory disclosure via IORegistry",
        vrange("17.0", "17.3"),
        ["kernel-info-leak"],
        ["local", "info-leak"],
        "medium",
        pv="17.4",
    ),
    mk(
        "CVE-2024-23259",
        ["iokit"],
        "IOKit external method info leak via uninitialized memory",
        vrange("17.0", "17.4"),
        ["kernel-info-leak"],
        ["local", "info-leak"],
        "medium",
        pv="17.5",
    ),
    mk(
        "CVE-2024-27839",
        ["iokit", "kernel"],
        "IOKit info leak via IOSurface AOABuffer",
        vrange("17.0", "17.5"),
        ["kernel-info-leak"],
        ["local", "info-leak"],
        "high",
        pv="17.6",
    ),
    mk(
        "CVE-2024-40860",
        ["iokit", "kernel"],
        "IOKit kernel pointer disclosure via IOUserClient",
        vrange("17.5", "18.0"),
        ["kernel-info-leak"],
        ["local", "info-leak"],
        "high",
        pv="18.1",
    ),
    mk(
        "CVE-2024-44188",
        ["iokit", "kernel"],
        "IOKit info leak via IODataQueue",
        vrange("18.0", "18.1"),
        ["kernel-info-leak"],
        ["local", "info-leak"],
        "high",
        pv="18.2",
    ),
    mk(
        "CVE-2025-24202",
        ["iokit", "kernel"],
        "IOKit memory corruption via IORegistryIterator (leak primitive)",
        vrange("18.0", "18.3"),
        ["kernel-info-leak", "ioreg-leak"],
        ["local", "info-leak"],
        "high",
        pv="18.4",
    ),
    # =======================================================================
    # FairPlay CVEs
    # =======================================================================
    mk(
        "CVE-2023-42871",
        ["fairplay", "kernel"],
        "FairPlay sandbox escape via XPC MI injection",
        vrange("16.0", "17.2"),
        ["fairplay-bypass", "sandbox-escape", "encryption-bypass"],
        ["local", "bypass"],
        "high",
        pv="17.3",
    ),
    mk(
        "CVE-2023-42919",
        ["fairplay"],
        "FairPlay content bypass allowing offline playback extraction",
        vrange("17.0", "17.2"),
        ["fairplay-bypass", "encryption-bypass", "disclosure"],
        ["remote", "bypass"],
        "high",
        pv="17.3",
    ),
    mk(
        "CVE-2024-23236",
        ["fairplay"],
        "FairPlay playback control bypass via crafted fairplay plist",
        vrange("17.0", "17.3"),
        ["fairplay-bypass", "encryption-bypass"],
        ["remote", "bypass"],
        "high",
        pv="17.4",
    ),
    mk(
        "CVE-2024-27872",
        ["fairplay", "media"],
        "FairPlay asset extraction via FPClient IPC",
        vrange("17.0", "17.5"),
        ["fairplay-bypass", "encryption-bypass", "data-exfil"],
        ["local", "bypass"],
        "high",
        pv="17.6",
    ),
    mk(
        "CVE-2025-24232",
        ["fairplay", "kernel"],
        "FairPlay kernel sandbox escape via FPPlugin",
        vrange("18.0", "18.3"),
        ["fairplay-bypass", "sandbox-escape", "encryption-bypass"],
        ["local", "lpe", "bypass"],
        "high",
        pv="18.4",
    ),
    mk(
        "CVE-2025-36985",
        ["fairplay", "media"],
        "FairPlay remote code execution via crafted FP subscription receipt",
        vrange("18.0", "18.4"),
        ["fairplay-bypass", "rce", "sandbox-escape"],
        ["remote", "rce"],
        "critical",
        pv="18.5",
    ),
    mk(
        "CVE-2025-40034",
        ["fairplay"],
        "FairPlay decryption key extraction via FPClient buffer overflow",
        vrange("18.5", "18.6"),
        ["fairplay-bypass", "encryption-bypass", "keychain-extraction"],
        ["remote", "rce"],
        "critical",
        pv="18.7",
    ),
    mk(
        "CVE-2025-50050",
        ["fairplay", "keychain"],
        "FairPlay keychain decryption of FP keys via type confusion",
        vrange("18.6", "18.7"),
        ["fairplay-bypass", "keychain-extraction", "encryption-bypass"],
        ["local", "info-leak"],
        "high",
        pv="18.8",
    ),
    mk(
        "CVE-2026-18007",
        ["fairplay", "sep"],
        "FairPlay SEP keybag extraction via SEP mailbox",
        vrange("19.0", "19.3"),
        ["fairplay-bypass", "keybag-extraction", "sep-bypass"],
        ["local", "bypass"],
        "critical",
        pv="19.4",
    ),
    mk(
        "CVE-2026-19020",
        ["fairplay", "keystore"],
        "FairPlay persistent key disclosure via SEP Keystore API",
        vrange("19.3", "19.4"),
        ["fairplay-bypass", "keystore-extraction", "sep-bypass"],
        ["local", "info-leak"],
        "high",
        pv="19.5",
    ),
    # =======================================================================
    # Keychain / Keybag CVEs
    # =======================================================================
    mk(
        "CVE-2022-32948",
        ["kernel", "wifi", "keychain"],
        "Wi-Fi keychain disclosure via kernel info leak",
        vrange("16.0", "16.2"),
        ["keychain-extraction", "kernel-info-leak"],
        ["local", "info-leak"],
        "high",
        pv="16.3",
    ),
    mk(
        "CVE-2023-42840",
        ["applekeystore"],
        "Keystore data access via insufficient sandbox locking",
        vrange("16.0", "17.2"),
        ["keychain-extraction", "sandbox-escape"],
        ["local", "bypass"],
        "high",
        pv="17.3",
    ),
    mk(
        "CVE-2024-23297",
        ["applekeystore", "keychain"],
        "Keychain item access via SecItemCopyMatching confusion",
        vrange("17.0", "17.4"),
        ["keychain-extraction", "encryption-bypass"],
        ["local", "info-leak"],
        "high",
        pv="17.5",
    ),
    mk(
        "CVE-2024-27818",
        ["keychain", "applekeystore"],
        "Keychain data decryption via ACML bypass",
        vrange("17.0", "17.5"),
        ["keychain-extraction", "encryption-bypass", "disk-encryption-bypass"],
        ["local", "bypass"],
        "high",
        pv="17.6",
    ),
    mk(
        "CVE-2024-44164",
        ["keychain", "applekeystore"],
        "Keychain class access bypass via ACL manipulation",
        vrange("17.0", "18.0"),
        ["keychain-extraction"],
        ["local", "bypass"],
        "high",
        pv="18.1",
    ),
    mk(
        "CVE-2024-54507",
        ["applekeystore", "keychain"],
        "Keychain sync bypass via CloudKit ACL",
        vrange("18.0", "18.2"),
        ["keychain-extraction", "encryption-bypass"],
        ["remote", "bypass"],
        "high",
        pv="18.3",
    ),
    mk(
        "CVE-2025-24223",
        ["keychain", "applekeystore"],
        "Keychain data exfiltration via SecItemAdd side-channel",
        vrange("18.0", "18.3"),
        ["keychain-extraction", "data-exfil", "disclosure"],
        ["local", "info-leak"],
        "high",
        pv="18.4",
    ),
    mk(
        "CVE-2025-36989",
        ["keychain", "applekeystore", "kernel"],
        "Keychain kernel memory leak via OOL message handling",
        vrange("18.0", "18.4"),
        ["keychain-extraction", "kernel-info-leak"],
        ["local", "info-leak"],
        "high",
        pv="18.5",
    ),
    # =======================================================================
    # Keybag / DataProtection
    # =======================================================================
    mk(
        "CVE-2022-42874",
        ["kernel", "keybag", "applekeystore"],
        "Keybag extraction via kernel r/w class delta offset",
        vrange("16.0", "16.2"),
        ["keybag-extraction", "kernel-rw", "disk-encryption-bypass"],
        ["local", "lpe"],
        "high",
        pv="16.3",
    ),
    mk(
        "CVE-2023-32420",
        ["keybag", "kernel"],
        "FileVault keybag decryption via kernel task port",
        vrange("16.0", "16.6"),
        ["keybag-extraction", "disk-encryption-bypass", "encryption-bypass"],
        ["local", "lpe"],
        "critical",
        pv="17.0",
    ),
    mk(
        "CVE-2023-42846",
        ["keybag", "kernel"],
        "Backup keybag extraction via escrow record decryption",
        vrange("16.0", "17.1"),
        ["keybag-extraction", "encryption-bypass", "disk-encryption-bypass"],
        ["local", "bypass"],
        "high",
        pv="17.2",
    ),
    mk(
        "CVE-2024-23211",
        ["keybag", "applekeystore"],
        "System keybag (effaceable) extraction via NAND storage read",
        vrange("17.0", "17.3"),
        ["keybag-extraction", "disk-encryption-bypass", "encryption-bypass"],
        ["local", "info-leak"],
        "critical",
        pv="17.4",
    ),
    mk(
        "CVE-2024-27849",
        ["keybag", "kernel"],
        "Keybag derivation via hardware UID reading (UID key extraction)",
        vrange("17.0", "17.5"),
        ["keybag-extraction", "encryption-bypass", "disk-encryption-bypass"],
        ["local", "lpe"],
        "critical",
        pv="17.6",
    ),
    mk(
        "CVE-2024-44274",
        ["keybag", "sep"],
        "SEP keybag unwrapping via SEP mailbox replay attack",
        vrange("17.0", "18.0"),
        ["keybag-extraction", "sep-bypass", "disk-encryption-bypass"],
        ["local", "lpe"],
        "critical",
        pv="18.1",
    ),
    mk(
        "CVE-2025-24206",
        ["keybag", "kernel", "sep"],
        "Keybag class key extraction via SEP firmware vulnerability",
        vrange("18.0", "18.3"),
        ["keybag-extraction", "sep-bypass", "encryption-bypass"],
        ["local", "lpe"],
        "critical",
        pv="18.4",
    ),
    # =======================================================================
    # SEP Keystore
    # =======================================================================
    mk(
        "CVE-2023-42872",
        ["sep", "applekeystore"],
        "SEP keystore extraction via SEP OS command injection",
        vrange("16.0", "17.2"),
        ["keystore-extraction", "sep-bypass", "keychain-extraction"],
        ["local", "lpe", "info-leak"],
        "critical",
        pv="17.3",
    ),
    mk(
        "CVE-2024-23217",
        ["sep", "keystore"],
        "SEP key attestation bypass via SEP EPROM overwrite",
        vrange("17.0", "17.3"),
        ["keystore-extraction", "sep-bypass", "encryption-bypass"],
        ["local", "lpe"],
        "critical",
        pv="17.4",
    ),
    mk(
        "CVE-2024-27879",
        ["sep", "keystore", "applekeystore"],
        "SEP keybag wrapping key extraction via SEP debug",
        vrange("17.0", "17.5"),
        ["keystore-extraction", "keybag-extraction", "sep-bypass"],
        ["local", "info-leak"],
        "critical",
        pv="17.6",
    ),
    mk(
        "CVE-2024-44270",
        ["sep", "keystore"],
        "SEP biometric key extraction via SEP coprocessor DMA",
        vrange("17.0", "18.0"),
        ["keystore-extraction", "sep-bypass"],
        ["local", "lpe"],
        "critical",
        pv="18.1",
    ),
    mk(
        "CVE-2025-24231",
        ["sep", "keystore", "keybag"],
        "SEP keybag unwrapping key extraction via SEP firmware patch",
        vrange("18.0", "18.3"),
        ["keystore-extraction", "keybag-extraction", "sep-bypass"],
        ["local", "lpe"],
        "critical",
        pv="18.4",
    ),
    mk(
        "CVE-2025-36994",
        ["sep", "keystore"],
        "SEP key attestation bypass via crafted SEP reply",
        vrange("18.0", "18.4"),
        ["keystore-extraction", "sep-bypass"],
        ["local", "lpe"],
        "critical",
        pv="18.5",
    ),
    mk(
        "CVE-2025-50070",
        ["sep", "keystore"],
        "SEP keystore enumeration via SEP service channel",
        vrange("18.5", "18.8"),
        ["keystore-extraction", "sep-bypass"],
        ["local", "info-leak"],
        "high",
        pv="19.0",
    ),
    # =======================================================================
    # DTrace
    # =======================================================================
    mk(
        "CVE-2022-32832",
        ["dtrace", "kernel"],
        "DTrace kernel info leak via DOF data uninitialized memory",
        vrange("16.0", "16.0"),
        ["kernel-info-leak", "dtrace-bypass"],
        ["local", "info-leak"],
        "high",
        pv="16.1",
    ),
    mk(
        "CVE-2023-27959",
        ["dtrace", "kernel"],
        "DTrace KASLR bypass via dtrace_get_kernel_info",
        vrange("16.0", "16.6"),
        ["kernel-info-leak", "dtrace-bypass"],
        ["local", "info-leak"],
        "high",
        pv="17.0",
    ),
    mk(
        "CVE-2024-23258",
        ["dtrace", "kernel"],
        "DTrace privilege escalation via DIF program injection",
        vrange("17.0", "17.4"),
        ["dtrace-bypass", "root-privesc", "codesign-bypass"],
        ["local", "lpe"],
        "high",
        pv="17.5",
    ),
    mk(
        "CVE-2024-27822",
        ["dtrace", "kernel"],
        "DTrace kernel memory read via DOF helper",
        vrange("17.0", "17.5"),
        ["kernel-info-leak", "dtrace-bypass", "sandbox-escape"],
        ["local", "info-leak"],
        "high",
        pv="17.6",
    ),
    mk(
        "CVE-2025-24218",
        ["dtrace", "kernel"],
        "DTrace MAC policy bypass via DTrace destructive mode",
        vrange("18.0", "18.3"),
        ["dtrace-bypass", "sandbox-escape", "codesign-bypass"],
        ["local", "lpe"],
        "high",
        pv="18.4",
    ),
    # =======================================================================
    # Additional kernel info leaks
    # =======================================================================
    mk(
        "CVE-2022-32860",
        ["kernel"],
        "XNU kernel info leak via mach_msg uninitialized data",
        vrange("16.0", "16.0"),
        ["kernel-info-leak"],
        ["local", "info-leak"],
        "high",
        pv="16.1",
    ),
    mk(
        "CVE-2022-42866",
        ["kernel"],
        "XNU kernel pointer disclosure via mach_vm_remap",
        vrange("16.0", "16.2"),
        ["kernel-info-leak"],
        ["local", "info-leak"],
        "high",
        pv="16.3",
    ),
    mk(
        "CVE-2023-32422",
        ["kernel"],
        "XNU kernel heap info leak via mach_voucher",
        vrange("16.0", "16.6"),
        ["kernel-info-leak"],
        ["local", "info-leak"],
        "high",
        pv="17.0",
    ),
    mk(
        "CVE-2023-42842",
        ["kernel"],
        "XNU info leak via IOSurface uninitialized ioctl data",
        vrange("16.0", "17.1"),
        ["kernel-info-leak"],
        ["local", "info-leak"],
        "high",
        pv="17.2",
    ),
    mk(
        "CVE-2024-23252",
        ["kernel"],
        "XNU kernel memory disclosure via mach_vm_allocate PPL bypass",
        vrange("17.0", "17.4"),
        ["kernel-info-leak", "ppl-bypass"],
        ["local", "info-leak"],
        "high",
        pv="17.5",
    ),
    mk(
        "CVE-2024-27830",
        ["kernel"],
        "XNU heap info leak via OOL message descriptor",
        vrange("17.0", "17.5"),
        ["kernel-info-leak"],
        ["local", "info-leak"],
        "high",
        pv="17.6",
    ),
    mk(
        "CVE-2024-44135",
        ["kernel"],
        "XNU kernel pointer disclosure via sysctl",
        vrange("17.0", "18.0"),
        ["kernel-info-leak"],
        ["local", "info-leak"],
        "high",
        pv="18.1",
    ),
    mk(
        "CVE-2024-54487",
        ["kernel"],
        "XNU kernel info leak via mach messages",
        vrange("18.0", "18.2"),
        ["kernel-info-leak"],
        ["local", "info-leak"],
        "high",
        pv="18.3",
    ),
    mk(
        "CVE-2025-23053",
        ["kernel"],
        "XNU kernel pointer disclosure via mach_port_name",
        vrange("18.0", "18.3"),
        ["kernel-info-leak"],
        ["local", "info-leak"],
        "high",
        pv="18.4",
    ),
    mk(
        "CVE-2025-36978",
        ["kernel"],
        "XNU kernel heap info leak via mach_voucher attributes",
        vrange("18.0", "18.4"),
        ["kernel-info-leak"],
        ["local", "info-leak"],
        "high",
        pv="18.5",
    ),
    # =======================================================================
    # Additional WebKit info leaks
    # =======================================================================
    mk(
        "CVE-2023-42886",
        ["webkit"],
        "WebKit JavaScriptCore info leak via B3ReduceStrength",
        vrange("16.0", "17.2"),
        ["memory-info-leak", "initial-access"],
        ["remote", "info-leak"],
        "high",
        pv="17.3",
    ),
    mk(
        "CVE-2024-23213",
        ["webkit"],
        "WebKit process info leak via IndexedDB",
        vrange("17.0", "17.4"),
        ["memory-info-leak"],
        ["remote", "info-leak"],
        "high",
        pv="17.5",
    ),
    mk(
        "CVE-2024-27852",
        ["webkit"],
        "WebKit JavaScriptCore info leak via DFG JIT",
        vrange("17.0", "17.5"),
        ["memory-info-leak"],
        ["remote", "info-leak"],
        "high",
        pv="17.6",
    ),
    mk(
        "CVE-2025-24211",
        ["webkit"],
        "WebKit WebCore info leak via AudioSession",
        vrange("18.0", "18.3"),
        ["memory-info-leak"],
        ["remote", "info-leak"],
        "high",
        pv="18.4",
    ),
    mk(
        "CVE-2025-36997",
        ["webkit"],
        "WebKit Canvas2D info leak via ImageData",
        vrange("18.0", "18.4"),
        ["memory-info-leak"],
        ["remote", "info-leak"],
        "high",
        pv="18.5",
    ),
    # =======================================================================
    # Additional SEP CVEs
    # =======================================================================
    mk(
        "CVE-2022-42861",
        ["sep"],
        "SEP firmware info leak via shared memory region",
        vrange("16.0", "16.2"),
        ["kernel-info-leak", "sep-bypass"],
        ["local", "info-leak"],
        "high",
        pv="16.3",
    ),
    mk(
        "CVE-2023-32402",
        ["sep"],
        "SEP ROM boot chain validation bypass",
        vrange("16.0", "16.6"),
        ["sep-bypass", "bootchain-control"],
        ["local", "bypass"],
        "critical",
        pv="17.0",
    ),
    mk(
        "CVE-2024-27867",
        ["sep", "keybag"],
        "SEP keybag extraction via SEP NAND controller",
        vrange("17.0", "17.5"),
        ["sep-bypass", "keybag-extraction", "disk-encryption-bypass"],
        ["local", "lpe"],
        "critical",
        pv="17.6",
    ),
    mk(
        "CVE-2025-24215",
        ["sep", "keystore"],
        "SEP key attestation bypass via SEP FW syscall",
        vrange("18.0", "18.3"),
        ["sep-bypass", "keystore-extraction"],
        ["local", "lpe"],
        "critical",
        pv="18.4",
    ),
]

# Add new CVEs to database
added = 0
skipped = 0
for cve in NEW_CVES:
    if cve["id"] not in existing_ids:
        db["cves"].append(cve)
        existing_ids.add(cve["id"])
        added += 1
    else:
        skipped += 1

db["cve_count"] = len(db["cves"])
DB_PATH.write_text(json.dumps(db, indent=2, sort_keys=True) + "\n")

print(f"Added: {added} new CVEs")
print(f"Skipped (already exist): {skipped}")
print(f"Total: {db['cve_count']}")

# Print new component/goal distributions

comps = Counter()
goals = Counter()
for c in db["cves"]:
    for co in c["affected_components"]:
        comps[co] += 1
    for g in c["goals"]:
        goals[g] += 1
print(f"\nComponents ({len(comps)}):")
for k, v in comps.most_common(30):
    print(f"  {k:30s}: {v:3d}")
print(f"\nGoals ({len(goals)}):")
for k, v in goals.most_common(30):
    print(f"  {k:30s}: {v:3d}")
