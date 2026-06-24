#!/usr/bin/env python3
"""Relocatable FBR34KER handoff-v4 binary design format.

The FBHB container is an address-neutral loader contract. Pointers in its
embedded handoff are file-relative offsets. Callback declarations are stored
in the header and must be resolved by the authorized loader before launch.
"""
from __future__ import annotations
import hashlib, json, pathlib, struct
from typing import Any
from handoff_schema import load_and_validate, HandoffSchemaError

MAGIC=b"FBHB"; FORMAT_VERSION=1; ABI_VERSION=4
HEADER=struct.Struct("<4sHH" + "I"*10 + "32s")
HANDOFF_SIZE=284; REGION=struct.Struct("<QQII")
SERVICE_BITS={"console-write":1<<0,"console-read":1<<1,"console-flush":1<<2,
 "framebuffer-flush":1<<3,"interrupt-controller":1<<4,
 "watchdog-configure":1<<5,"watchdog-kick":1<<6}
RUNTIME_BITS={"input":1<<0,"timer":1<<1,"power":1<<2}
REGION_TYPES={"usable":1,"reserved":2,"mmio":3,"monitor":4,"framebuffer":5}
ATTR_BITS={"read":1,"write":2,"execute":4,"device":8,"dma":16}
PIXEL_FORMATS={"xrgb8888":0,"argb8888":1,"bgra8888":2,"rgb565":3}
MODULE_CAPS={"console":1,"log":2,"time":4,"dt":8,"state":16,"host":32}
HANDOFF_MAGIC=0x464F524745484F46

class HandoffBinaryError(ValueError): pass

def _n(v: Any)->int: return int(v,0) if isinstance(v,str) else int(v)
def _align(v:int,a:int=8)->int: return (v+a-1)&~(a-1)
def _canonical(doc:dict[str,Any])->bytes:
    return (json.dumps(doc,sort_keys=True,separators=(",",":"))+"\n").encode()

def _pack_handoff(doc:dict[str,Any], region_offset:int)->bytes:
    monitor=doc["monitor"]; fb=doc.get("framebuffer") or {}; policy=doc.get("module_policy") or {}
    flags=0
    if fb: flags|=1<<2
    if policy: flags|=1<<7
    capmask=policy.get("allowed_capability_mask")
    if capmask is None: capmask=sum(MODULE_CAPS[x] for x in policy.get("allowed_capabilities",[]))
    out=bytearray()
    out += struct.pack("<QIIQQQIIQQQQ", HANDOFF_MAGIC,4,HANDOFF_SIZE,
        _n(monitor["base"]),_n(monitor["size"]),region_offset,len(doc["regions"]),0,0,0,0,0)
    out += struct.pack("<QQIIQIIIIQ",flags,0,0,0,_n(fb.get("base",0)),fb.get("width",0),
        fb.get("height",0),fb.get("pixels_per_row",0),fb.get("pixel_format_id",PIXEL_FORMATS.get(fb.get("pixel_format","xrgb8888"),0)),0)
    out += struct.pack("<"+"Q"*9,0,0,0,0,0,0,0,0,0)
    out += struct.pack("<QIIIIQIIIHHIQQQ",0,0,doc["entry_exception_level"],doc["page_granule"],
        doc["boot_cpu_id"],_n(fb.get("size",0)),fb.get("bytes_per_pixel",0),fb.get("rotation",0),
        capmask,policy.get("dynamic_slots",0),0,policy.get("instruction_budget",0),_n(doc["firmware_revision"]),0,0)
    if len(out)!=HANDOFF_SIZE: raise AssertionError(len(out))
    return bytes(out)

def build_blob(path:pathlib.Path)->bytes:
    doc=load_and_validate(path)
    js=_canonical(doc)
    json_offset=HEADER.size
    handoff_offset=_align(json_offset+len(js),8)
    regions_offset=_align(handoff_offset+HANDOFF_SIZE,8)
    regions=b"".join(REGION.pack(_n(r["base"]),_n(r["size"]),REGION_TYPES[r["type"]],sum(ATTR_BITS[x] for x in r["attributes"])) for r in doc["regions"])
    handoff=_pack_handoff(doc,regions_offset)
    total=regions_offset+len(regions)
    payload=bytearray(total-HEADER.size)
    payload[json_offset-HEADER.size:json_offset-HEADER.size+len(js)]=js
    payload[handoff_offset-HEADER.size:handoff_offset-HEADER.size+len(handoff)]=handoff
    payload[regions_offset-HEADER.size:regions_offset-HEADER.size+len(regions)]=regions
    digest=hashlib.sha256(payload).digest()
    service_mask=sum(SERVICE_BITS[x] for x in doc.get("services",[]))
    runtime_mask=sum(RUNTIME_BITS[x] for x in doc.get("runtime_callbacks",[]))
    header=HEADER.pack(MAGIC,FORMAT_VERSION,ABI_VERSION,HEADER.size,total,json_offset,len(js),
        handoff_offset,HANDOFF_SIZE,regions_offset,len(doc["regions"]),service_mask,runtime_mask,digest)
    return header+payload

def write_blob(input_path:pathlib.Path, output_path:pathlib.Path)->dict[str,Any]:
    data=build_blob(input_path); output_path.parent.mkdir(parents=True,exist_ok=True); output_path.write_bytes(data)
    return inspect_blob_bytes(data, source=str(output_path))

def inspect_blob_bytes(data:bytes, source:str="<memory>")->dict[str,Any]:
    if len(data)<HEADER.size: raise HandoffBinaryError("handoff blob is shorter than its header")
    values=HEADER.unpack_from(data); magic,fmt,abi=values[:3]
    if magic!=MAGIC or fmt!=FORMAT_VERSION or abi!=ABI_VERSION: raise HandoffBinaryError("unsupported handoff blob header")
    (header_size,total,json_offset,json_size,handoff_offset,handoff_size,regions_offset,region_count,service_mask,runtime_mask,digest)=values[3:]
    if header_size!=HEADER.size or total!=len(data) or handoff_size!=HANDOFF_SIZE: raise HandoffBinaryError("handoff blob sizes are inconsistent")
    if hashlib.sha256(data[HEADER.size:]).digest()!=digest: raise HandoffBinaryError("handoff blob SHA-256 mismatch")
    def covered(offset:int,size:int)->bool: return HEADER.size<=offset<=len(data) and 0<=size<=len(data)-offset
    if not covered(json_offset,json_size) or not covered(handoff_offset,handoff_size) or not covered(regions_offset,region_count*REGION.size):
        raise HandoffBinaryError("handoff blob section is outside the file")
    try: doc=json.loads(data[json_offset:json_offset+json_size].decode())
    except (UnicodeDecodeError,json.JSONDecodeError) as exc: raise HandoffBinaryError(f"embedded JSON is invalid: {exc}") from exc
    normalized=load_and_validate_document(doc)
    raw=data[handoff_offset:handoff_offset+handoff_size]
    magic_value,version,structure_size=struct.unpack_from("<QII",raw)
    region_ptr=struct.unpack_from("<Q",raw,32)[0]; count=struct.unpack_from("<I",raw,40)[0]
    if magic_value!=HANDOFF_MAGIC or version!=4 or structure_size!=HANDOFF_SIZE or region_ptr!=regions_offset or count!=region_count:
        raise HandoffBinaryError("embedded handoff header or offset pointer is invalid")
    regions=[]
    for i in range(region_count):
        base,size,typ,attrs=REGION.unpack_from(data,regions_offset+i*REGION.size)
        regions.append({"base":f"0x{base:x}","size":f"0x{size:x}","type":typ,"attributes":attrs})
    return {"format":"FBHB","format_version":fmt,"abi_version":abi,"source":source,
        "size":len(data),"sha256":hashlib.sha256(data).hexdigest(),"payload_sha256":digest.hex(),
        "service_declaration_mask":service_mask,"runtime_declaration_mask":runtime_mask,
        "sections":{"json":{"offset":json_offset,"size":json_size},"handoff":{"offset":handoff_offset,"size":handoff_size},
                    "regions":{"offset":regions_offset,"count":region_count,"entry_size":REGION.size}},
        "runtime_ready":service_mask==0 and runtime_mask==0,"normalized":normalized,"regions_binary":regions}

def load_and_validate_document(doc:dict[str,Any])->dict[str,Any]:
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p=pathlib.Path(td)/"h.json"; p.write_text(json.dumps(doc),encoding="utf-8")
        return load_and_validate(p)

def inspect_blob(path:pathlib.Path)->dict[str,Any]: return inspect_blob_bytes(path.read_bytes(),source=str(path))
def roundtrip_blob(path:pathlib.Path)->dict[str,Any]:
    first=inspect_blob(path); original=path.read_bytes()
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        j=pathlib.Path(td)/"handoff.json"; j.write_text(json.dumps(first["normalized"],indent=2),encoding="utf-8")
        rebuilt=build_blob(j)
    return {"roundtrip_equal":rebuilt==original,"original_sha256":hashlib.sha256(original).hexdigest(),
            "rebuilt_sha256":hashlib.sha256(rebuilt).hexdigest(),"normalized":first["normalized"]}
