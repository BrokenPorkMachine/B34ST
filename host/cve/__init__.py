from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from host.cve.cve_db import CVE, VersionRange, CVEDatabase, CVELookupError, GoalType, BUILTIN_CVE_DB
    from host.cve.exploit_chain import ExploitGoal, ExploitChain, ChainPlanner, ChainPlannerError
    from host.cve.fuzzer import FuzzerFramework, FuzzerError

__all__ = [
    "BUILTIN_CVE_DB",
    "CVE",
    "CVEDatabase",
    "CVELookupError",
    "ChainPlanner",
    "ChainPlannerError",
    "ExploitChain",
    "ExploitGoal",
    "FuzzerError",
    "FuzzerFramework",
    "GoalType",
    "VersionRange",
    "DeviceInfo",
    "SocInfo",
    "SOC_DATABASE",
    "DEVICE_DATABASE",
    "get_device",
    "get_soc",
    "devices_for_version",
]


def __getattr__(name: str) -> Any:
    if name in {"CVE", "VersionRange", "CVEDatabase", "CVELookupError", "GoalType", "BUILTIN_CVE_DB"}:
        from host.cve.cve_db import CVE, VersionRange, CVEDatabase, CVELookupError, GoalType, BUILTIN_CVE_DB
        return locals()[name]
    if name in {"ExploitGoal", "ExploitChain", "ChainPlanner", "ChainPlannerError"}:
        from host.cve.exploit_chain import ExploitGoal, ExploitChain, ChainPlanner, ChainPlannerError
        return locals()[name]
    if name in {"FuzzerFramework", "FuzzerError"}:
        from host.cve.fuzzer import FuzzerFramework, FuzzerError
        return locals()[name]
    if name in {"DeviceInfo", "SocInfo", "SOC_DATABASE", "DEVICE_DATABASE",
                 "get_device", "get_soc", "devices_for_version"}:
        from host.cve.devices import DeviceInfo, SocInfo, SOC_DATABASE, DEVICE_DATABASE, get_device, get_soc, devices_for_version
        return locals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
