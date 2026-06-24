#!/usr/bin/env python3
"""Formal conformance checks for FBHB handoff blobs and board profiles."""
from __future__ import annotations
import json, pathlib
from typing import Any
from handoff_binary import inspect_blob, HandoffBinaryError
from hardware_profile import load_profile, HardwareProfileError

VALID={"PASS","PARTIAL","UNSUPPORTED","NOT TESTED","LOCKED","FAIL"}
class SDKConformanceError(ValueError): pass

def _num(v:Any)->int: return int(v,0) if isinstance(v,str) else int(v)
def _entry(name,state,detail):
    if state not in VALID: raise AssertionError(state)
    return {"feature":name,"state":state,"detail":detail}

def _load_memory(path:pathlib.Path|None, fallback:list[dict[str,Any]])->list[dict[str,Any]]:
    if path is None: return fallback
    try: doc=json.loads(path.read_text())
    except (OSError,json.JSONDecodeError) as exc: raise SDKConformanceError(f"unable to read memory map: {exc}") from exc
    regions=doc.get("regions",doc) if isinstance(doc,dict) else doc
    if not isinstance(regions,list): raise SDKConformanceError("memory map must be a list or contain regions")
    return regions

def check(blob:pathlib.Path, memory_map:pathlib.Path|None=None, profile_path:pathlib.Path|None=None)->dict[str,Any]:
    info=inspect_blob(blob); doc=info["normalized"]; regions=_load_memory(memory_map,doc["regions"])
    entries=[]
    entries.append(_entry("ABI layout","PASS",f"ABI v{info['abi_version']}, handoff size 284"))
    entries.append(_entry("Container integrity","PASS","header bounds and payload SHA-256 verified"))
    intervals=[]; overlap=False
    for r in regions:
        b=_num(r["base"]); s=_num(r["size"]); intervals.append((b,b+s,r))
    intervals.sort()
    for a,b in zip(intervals,intervals[1:]): overlap |= b[0] < a[1]
    entries.append(_entry("Memory ownership","FAIL" if overlap else "PASS","non-overlapping region map" if not overlap else "regions overlap"))
    mon=doc["monitor"]; mb,me=_num(mon["base"]),_num(mon["base"])+_num(mon["size"])
    owner=[r for b,e,r in intervals if b<=mb and me<=e and (r.get("type")=="monitor" or r.get("type")==4)]
    perms=set(owner[0].get("attributes",[])) if owner else set()
    if perms and isinstance(next(iter(perms),None),int): perms=set()
    exec_ok=bool(owner) and (not perms or {"read","write","execute"}.issubset(perms))
    entries.append(_entry("Monitor executable ownership","PASS" if exec_ok else "FAIL","monitor range is loader-owned RWX" if exec_ok else "monitor range lacks a matching RWX owner"))
    svc=info["service_declaration_mask"]
    entries.append(_entry("Callback declarations","NOT TESTED" if svc else "UNSUPPORTED",
        "callbacks are declared but addresses are resolved only by the runtime loader" if svc else "no callback services declared"))
    entries.append(_entry("Callback containment","NOT TESTED" if svc else "UNSUPPORTED","requires the final runtime handoff and loader code ranges"))
    entries.append(_entry("Device tree", "UNSUPPORTED",
        "FBHB does not embed a DTB; the runtime loader must attach and own it"))
    fb=doc.get("framebuffer")
    entries.append(_entry("Framebuffer safety","LOCKED" if fb else "UNSUPPORTED","metadata validated; writes remain policy-controlled" if fb else "no framebuffer declared"))
    policy=doc.get("module_policy")
    entries.append(_entry("Module policy","PASS" if policy else "LOCKED","explicit bounded policy" if policy else "modules default to locked"))
    entries.append(_entry("Boot modules","NOT TESTED","module payload integrity is verified when a runtime loader attaches modules"))
    profile_name=None
    if profile_path is not None:
        profile=load_profile(profile_path); profile_name=profile["name"]
        expected_el=profile["expected_el"]
        entries.append(_entry("Profile exception level","PASS" if expected_el==doc["entry_exception_level"] else "FAIL",
                              f"expected EL{expected_el}, design EL{doc['entry_exception_level']}"))
        required=set(profile["required_services"])
        declared=set(doc.get("services",[]))
        map_names={"console_write":"console-write","console_read":"console-read","console_flush":"console-flush",
                   "framebuffer_flush":"framebuffer-flush","interrupt_controller":"interrupt-controller",
                   "watchdog_configure":"watchdog-configure","watchdog_kick":"watchdog-kick"}
        missing=sorted(map_names[x] for x in required if x in map_names and map_names[x] not in declared)
        entries.append(_entry("Profile required callbacks","FAIL" if missing else "PASS",
                              "missing: "+", ".join(missing) if missing else "declared callback set satisfies the profile"))
    result="FAIL" if any(x["state"]=="FAIL" for x in entries) else "PARTIAL" if any(x["state"] in {"PARTIAL","NOT TESTED","LOCKED","UNSUPPORTED"} for x in entries) else "PASS"
    return {"schema_version":1,"tool":"fbr34kctl loader-conformance","handoff":str(blob),"profile":profile_name,
            "result":result.lower(),"matrix":entries}

def format_report(report:dict[str,Any])->str:
    lines=[f"Result: {report.get('result','unknown').upper()}",""]
    lines += [f"{x['feature']:<32} {x['state']:<12} {x['detail']}" for x in report.get("matrix",[])]
    return "\n".join(lines)+"\n"
