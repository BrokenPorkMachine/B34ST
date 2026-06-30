#!/usr/bin/env python3
"""Generate deterministic success, failure, and recovered bring-up evidence."""
from __future__ import annotations
import argparse
import json
import pathlib
import shutil
import subprocess
import sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'host'))
from project_version import RELEASE_VERSION  # noqa: E402

def run(command, expected):
    result=subprocess.run(command,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
    if result.returncode!=expected: raise RuntimeError(f"unexpected exit {result.returncode}: {result.stderr}")
    return json.loads(result.stdout)

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--output',type=pathlib.Path,required=True); p.add_argument('--image',type=pathlib.Path,required=True); p.add_argument('--profile',type=pathlib.Path,default=pathlib.Path('profiles/apple-a13-recovery.json')); p.add_argument('--device-info',type=pathlib.Path,default=pathlib.Path('examples/a13-device-info.json')); a=p.parse_args()
    out=a.output.resolve(); shutil.rmtree(out,ignore_errors=True); out.mkdir(parents=True)
    common=[sys.executable,'host/hardware_bringup.py','run','--device-info',str(a.device_info),'--profile',str(a.profile),'--image',str(a.image),'--authorized-session','--authorization-id','release-simulation-session','--acknowledge-unsigned-code']
    success=run([*common,'--state-dir',str(out/'success-state'),'--evidence',str(out/'success-evidence.zip')],0)
    failed=run([*common,'--state-dir',str(out/'recovery-state'),'--inject-failure','timer','--evidence',str(out/'failure-evidence.zip')],1)
    recovered=run([*common,'--state-dir',str(out/'recovery-state'),'--evidence',str(out/'recovered-evidence.zip')],0)
    summary={'schema_version':1,'project':'FBR34KER','release_version':RELEASE_VERSION,'success':success['passed'],'failure_observed':not failed['passed'],'reset_invalidated_authorization':failed['authorization_invalidated_after_recovery'],'recovered_after_reauthorization':recovered['passed']}
    (out/'simulation-summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    print(out/'simulation-summary.json'); return 0
if __name__=='__main__': raise SystemExit(main())
