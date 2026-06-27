from __future__ import annotations
import dataclasses, json, pathlib, re, hashlib
from typing import Any

GoalType = str  # type alias for goal identifiers

BUILTIN_CVE_DB: dict[str, CVE] = {}


class CVELookupError(ValueError):
    pass


@dataclasses.dataclass(frozen=True)
class VersionRange:
    start: str
    end: str | None = None

    def contains(self, version: str) -> bool:
        def _parse(v):
            parts = v.split(".")
            result = []
            for p in parts:
                if p.replace(".", "").isdigit():
                    result.append(int(p))
                elif "x" in p.lower():
                    result.append(999)
                else:
                    result.append(0)
            return tuple(result)

        ver = _parse(version)
        start = _parse(self.start)
        if ver < start:
            return False
        if self.end is not None:
            end = _parse(self.end)
            if ver > end:
                return False
        return True


@dataclasses.dataclass(frozen=True)
class CVE:
    id: str
    description: str
    affected_versions: tuple[VersionRange, ...]
    affected_components: tuple[str, ...]
    exploit_type: tuple[str, ...]
    exploit_available: bool
    goals: tuple[str, ...]
    chainable_with: tuple[str, ...] = ()
    mitigations: tuple[str, ...] = ()
    patch_version: str | None = None
    severity: str = "high"
    published: str = ""
    references: tuple[str, ...] = ()
    credits: tuple[str, ...] = ()
    exploit_path: str | None = None


GOAL_TYPES = {
    "jailbreak": "Full jailbreak (kernel r/w + root + cs-bypass + amfi)",
    "kernel-rw": "Arbitrary kernel read/write primitive",
    "root-privesc": "Escalate from mobile to root",
    "codesign-bypass": "Bypass code signing / AMFI / entitlements",
    "sep-bypass": "Bypass SEP / Secure Enclave protections",
    "boot-unlock": "Unlock boot chain / iBoot",
    "persistence": "Survive reboot / persistent jailbreak",
    "disclosure": "Information disclosure",
    "remote-exec": "Remote code execution",
    "wifi-rce": "WiFi-based remote code execution",
    "bt-rce": "Bluetooth-based remote code execution",
    "sandbox-escape": "Escape sandbox restrictions",
    "lpe": "Local privilege escalation",
    "data-exfil": "Data exfiltration",
    "activation-bypass": "Bypass activation lock",
    "passcode-bypass": "Bypass device passcode",
    "bootrom-exploit": "BootROM exploit (permanent untether)",
    "iokit": "IOKit vulnerability exploitation",
}

EXPLOIT_TYPE_DESCRIPTIONS = {
    "remote": "Exploitable over the network without user interaction",
    "local": "Requires local access or already-running code",
    "physical": "Requires physical device access",
    "network-adjacent": "Requires same network (WiFi/BT)",
    "lpe": "Local privilege escalation (requires code execution already)",
    "dos": "Denial of service",
}

COMPONENT_DESCRIPTIONS = {
    "kernel": "XNU kernel",
    "webkit": "WebKit browser engine",
    "sep": "Secure Enclave Processor",
    "iboot": "iBoot bootloader",
    "wifi": "WiFi firmware/stack",
    "bluetooth": "Bluetooth stack",
    "baseband": "Baseband processor",
    "safari": "Safari browser",
    "foundation": "Foundation framework",
    "coreaudio": "Core Audio",
    "coretext": "Core Text / font parsing",
    "ioconsole": "IOConsole / IOKit",
    "sandbox": "Sandbox profile",
    "accounts": "Accounts framework / AA",
    "kext": "Kernel extension",
    "lockdown-mode": "Lockdown Mode bypass",
    "imageio": "ImageIO / image parsing",
    "fontparser": "Font parser",
}


class CVEDatabase:
    def __init__(self, cves: dict[str, CVE] | None = None):
        self._cves: dict[str, CVE] = cves or {}

    @property
    def count(self) -> int:
        return len(self._cves)

    @property
    def all_cves(self) -> tuple[CVE, ...]:
        return tuple(self._cves.values())

    def add(self, cve: CVE) -> None:
        self._cves[cve.id] = cve

    def add_from_dict(self, data: dict[str, Any]) -> None:
        vr_data = data.get("affected_versions", [])
        vrs = tuple(
            VersionRange(start=v["start"], end=v.get("end"))
            for v in vr_data
        )
        cve = CVE(
            id=data["id"],
            description=data.get("description", ""),
            affected_versions=vrs,
            affected_components=tuple(data.get("affected_components", [])),
            exploit_type=tuple(data.get("exploit_type", [])),
            exploit_available=bool(data.get("exploit_available", False)),
            goals=tuple(data.get("goals", [])),
            chainable_with=tuple(data.get("chainable_with", [])),
            mitigations=tuple(data.get("mitigations", [])),
            patch_version=data.get("patch_version"),
            severity=data.get("severity", "high"),
            published=data.get("published", ""),
            references=tuple(data.get("references", [])),
            credits=tuple(data.get("credits", [])),
            exploit_path=data.get("exploit_path"),
        )
        self.add(cve)

    def query_by_version(self, version: str) -> tuple[CVE, ...]:
        results = []
        for cve in self._cves.values():
            for vr in cve.affected_versions:
                if vr.contains(version):
                    results.append(cve)
                    break
        return tuple(results)

    def query_by_goal(self, goal: str, version: str | None = None) -> tuple[CVE, ...]:
        results = []
        for cve in self._cves.values():
            if goal in cve.goals:
                if version is None:
                    results.append(cve)
                else:
                    for vr in cve.affected_versions:
                        if vr.contains(version):
                            results.append(cve)
                            break
        return tuple(results)

    def query_by_component(self, component: str, version: str | None = None) -> tuple[CVE, ...]:
        results = []
        for cve in self._cves.values():
            if component in cve.affected_components:
                if version is None:
                    results.append(cve)
                else:
                    for vr in cve.affected_versions:
                        if vr.contains(version):
                            results.append(cve)
                            break
        return tuple(results)

    def query_by_severity(self, severity: str, version: str | None = None) -> tuple[CVE, ...]:
        results = []
        for cve in self._cves.values():
            if cve.severity == severity:
                if version is None:
                    results.append(cve)
                else:
                    for vr in cve.affected_versions:
                        if vr.contains(version):
                            results.append(cve)
                            break
        return tuple(results)

    def query_exploit_available(self, version: str | None = None) -> tuple[CVE, ...]:
        results = []
        for cve in self._cves.values():
            if cve.exploit_available:
                if version is None:
                    results.append(cve)
                else:
                    for vr in cve.affected_versions:
                        if vr.contains(version):
                            results.append(cve)
                            break
        return tuple(results)

    def search(self, query: str) -> tuple[CVE, ...]:
        q = query.lower()
        results = []
        for cve in self._cves.values():
            if q in cve.id.lower() or q in cve.description.lower():
                results.append(cve)
        return tuple(results)

    def filter(
        self,
        *,
        version: str | None = None,
        goals: set[str] | None = None,
        components: set[str] | None = None,
        exploit_types: set[str] | None = None,
        exploit_available: bool | None = None,
        min_severity: str | None = None,
    ) -> tuple[CVE, ...]:
        results = list(self._cves.values())

        if version:
            results = [c for c in results if any(vr.contains(version) for vr in c.affected_versions)]

        if goals:
            results = [c for c in results if any(g in c.goals for g in goals)]

        if components:
            results = [c for c in results if any(co in c.affected_components for co in components)]

        if exploit_types:
            results = [c for c in results if any(et in c.exploit_type for et in exploit_types)]

        if exploit_available is not None:
            results = [c for c in results if c.exploit_available == exploit_available]

        if min_severity:
            severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            min_val = severity_order.get(min_severity, 1)
            results = [c for c in results if severity_order.get(c.severity, 99) <= min_val]

        return tuple(results)

    def to_dict(self) -> list[dict[str, Any]]:
        result = []
        for cve_id, cve in sorted(self._cves.items()):
            result.append({
                "id": cve.id,
                "description": cve.description,
                "affected_versions": [
                    {"start": vr.start, "end": vr.end}
                    for vr in cve.affected_versions
                ],
                "affected_components": list(cve.affected_components),
                "exploit_type": list(cve.exploit_type),
                "exploit_available": cve.exploit_available,
                "goals": list(cve.goals),
                "chainable_with": list(cve.chainable_with),
                "mitigations": list(cve.mitigations),
                "patch_version": cve.patch_version,
                "severity": cve.severity,
                "published": cve.published,
                "references": list(cve.references),
                "credits": list(cve.credits),
                "exploit_path": cve.exploit_path,
            })
        return result

    def save_json(self, path: pathlib.Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "schema": "cve-database-v1",
            "cve_count": self.count,
            "cves": self.to_dict(),
        }
        path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    @classmethod
    def load_json(cls, path: pathlib.Path) -> CVEDatabase:
        data = json.loads(path.read_text(encoding="utf-8"))
        db = cls()
        for entry in data.get("cves", []):
            db.add_from_dict(entry)
        return db

    def compute_stats(self) -> dict[str, Any]:
        total = self.count
        by_severity = {}
        by_component = {}
        by_goal = {}
        by_exploit_type = {}
        exploit_available = 0

        for cve in self._cves.values():
            by_severity[cve.severity] = by_severity.get(cve.severity, 0) + 1
            for comp in cve.affected_components:
                by_component[comp] = by_component.get(comp, 0) + 1
            for goal in cve.goals:
                by_goal[goal] = by_goal.get(goal, 0) + 1
            for et in cve.exploit_type:
                by_exploit_type[et] = by_exploit_type.get(et, 0) + 1
            if cve.exploit_available:
                exploit_available += 1

        return {
            "total_cves": total,
            "exploit_available": exploit_available,
            "by_severity": dict(sorted(by_severity.items())),
            "by_component": dict(sorted(by_component.items(), key=lambda x: -x[1])),
            "by_goal": dict(sorted(by_goal.items(), key=lambda x: -x[1])),
            "by_exploit_type": dict(sorted(by_exploit_type.items(), key=lambda x: -x[1])),
        }
