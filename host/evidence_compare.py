#!/usr/bin/env python3
"""Compare two FBR34KER bring-up evidence summaries."""
from __future__ import annotations
import argparse, json, pathlib, sys, zipfile

MAX_SIZE=2*1024*1024

def load(path:pathlib.Path):
    if path.stat().st_size>MAX_SIZE: raise ValueError("evidence exceeds size limit")
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as bundle:
            info=bundle.getinfo("summary.json")
            if info.file_size>MAX_SIZE: raise ValueError("summary exceeds size limit")
            return json.loads(bundle.read(info))
    return json.loads(path.read_text(encoding="utf-8"))

def pick(value,path):
    for key in path:
        value=value.get(key) if isinstance(value,dict) else None
    return value

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("first",type=pathlib.Path); p.add_argument("second",type=pathlib.Path)
    a=p.parse_args(argv)
    try:
        left,right=load(a.first),load(a.second)
        fields={"profile_id":("profile_id",),"device_cpid":("device","cpid"),"device_ecid":("device","ecid"),
                "image_sha256":("image","sha256"),"passed":("passed",),"failure":("failure",)}
        changes=[]
        for name,path in fields.items():
            x,y=pick(left,path),pick(right,path)
            if x!=y: changes.append({"field":name,"first":x,"second":y})
        ls={item.get("stage"):item.get("status") for item in left.get("stages",[]) if isinstance(item,dict)}
        rs={item.get("stage"):item.get("status") for item in right.get("stages",[]) if isinstance(item,dict)}
        for stage in sorted(set(ls)|set(rs)):
            if ls.get(stage)!=rs.get(stage): changes.append({"field":f"stage:{stage}","first":ls.get(stage),"second":rs.get(stage)})
        print(json.dumps({"schema_version":1,"equal":not changes,"changes":changes},indent=2,sort_keys=True)); return 0
    except (OSError,ValueError,json.JSONDecodeError,KeyError,zipfile.BadZipFile) as exc:
        print(f"evidence compare error: {exc}",file=sys.stderr); return 2
if __name__=="__main__": raise SystemExit(main())
