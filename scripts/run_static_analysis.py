#!/usr/bin/env python3
"""Run bounded parallel Clang static analysis over FBR34KER translation units."""
from __future__ import annotations
import argparse,concurrent.futures,os,pathlib,subprocess,sys,time
from dataclasses import dataclass
@dataclass(frozen=True)
class Result: index:int;source:pathlib.Path;return_code:int;diagnostics:str;duration:float;timed_out:bool=False
def one(index,source,clang,timeout,source_id,includes,environment):
    command=[clang,"--target=aarch64-none-elf","--analyze","-std=c11","-ffreestanding","-fno-builtin","-fno-omit-frame-pointer","-mgeneral-regs-only","-march=armv8-a",'-DFBR34KER_BUILD_TARGET="analysis"',f'-DFBR34KER_SOURCE_ID="{source_id}"',*[f"-I{x}" for x in includes],"-Wall","-Wextra","-Werror",str(source),"-o","/dev/null"]
    started=time.monotonic()
    try: p=subprocess.run(command,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,env=environment,timeout=timeout,check=False)
    except subprocess.TimeoutExpired as e:
        out=e.stdout or "";out=out.decode(errors="replace") if isinstance(out,bytes) else out;return Result(index,source,124,out.strip(),time.monotonic()-started,True)
    return Result(index,source,p.returncode,p.stdout.strip(),time.monotonic()-started,False)
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument("--clang",default="clang");ap.add_argument("--timeout",type=float,default=45.0);ap.add_argument("--jobs",type=int,default=4);ap.add_argument("--source-id",default="analysis");ap.add_argument("--include-dir",action="append",default=[]);ap.add_argument("sources",nargs="+");a=ap.parse_args()
    if a.timeout<=0 or a.jobs<=0: ap.error("timeout and jobs must be positive")
    sources=[pathlib.Path(x) for x in a.sources]
    for x in sources:
        if not x.is_file(): print(f"static analysis failed: missing source {x}",file=sys.stderr);return 1
    env=os.environ.copy()
    for k in("MAKEFLAGS","MFLAGS","MAKELEVEL","TARGET"):env.pop(k,None)
    includes=a.include_dir or ["include"];jobs=min(a.jobs,len(sources));started=time.monotonic();print(f"starting bounded static analysis ({len(sources)} files, {jobs} workers)",flush=True)
    results=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as ex:
        futures=[ex.submit(one,i,s,a.clang,a.timeout,a.source_id,includes,env) for i,s in enumerate(sources,1)]
        for f in concurrent.futures.as_completed(futures):
            r=f.result();results.append(r);status="timeout" if r.timed_out else("ok" if r.return_code==0 and not r.diagnostics else"failed");print(f"[analyze {r.index:02d}/{len(sources):02d}] {r.source}: {status} ({r.duration:.2f}s)",flush=True)
    failures=sorted((r for r in results if r.timed_out or r.return_code!=0 or r.diagnostics),key=lambda r:r.index)
    if failures:
        for r in failures:
            print((f"static analysis timed out after {a.timeout:.1f}s: " if r.timed_out else "static analysis failed: ")+str(r.source),file=sys.stderr)
            if r.diagnostics:print(r.diagnostics,file=sys.stderr)
        return 1
    print(f"clang static analysis passed without findings ({len(sources)} files, {time.monotonic()-started:.2f}s, {jobs} workers)");return 0
if __name__=="__main__":raise SystemExit(main())
