#!/usr/bin/env python3
"""Unified FBR34KER public developer-preview command line."""
from __future__ import annotations
import argparse, json, os, pathlib, re, shutil, subprocess, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
VERSION_RE=re.compile(r'^#define FBR34KER_MONITOR_VERSION "([^"]+)"$',re.M)
VERSION=VERSION_RE.search((ROOT/'include/fbr34ker/version.h').read_text()).group(1)

class CliError(RuntimeError):
    def __init__(self,message,code=1): super().__init__(message); self.code=code

def execute(command, *, json_mode=False, cwd=ROOT):
    proc=subprocess.run([str(x) for x in command],cwd=cwd,text=True,stdout=subprocess.PIPE if json_mode else None,stderr=subprocess.STDOUT if json_mode else None,check=False)
    if json_mode:
        print(json.dumps({'ok':proc.returncode==0,'exit_code':proc.returncode,'command':[str(x) for x in command],'output':proc.stdout},sort_keys=True))
    return proc.returncode

def make(targets, json_mode=False, variables=()): return execute(['make','--no-print-directory',*variables,*targets],json_mode=json_mode)
def require_qemu():
    if not shutil.which('qemu-system-aarch64'): raise CliError('qemu-system-aarch64 is required for this command')

def parser():
    p=argparse.ArgumentParser(prog='fbr34ker',description=__doc__,
        epilog='Compatibility aliases: -b/--build, -r/--run, -c/--clean, --verify, --gate, --package, --permissions.')
    p.add_argument('--json',action='store_true',help='emit a stable JSON result')
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('version'); sub.add_parser('doctor')
    b=sub.add_parser('build'); b.add_argument('--jobs',type=int,default=int(os.environ.get('FBR34KER_JOBS','4')))
    t=sub.add_parser('test'); t.add_argument('--qemu',action='store_true'); t.add_argument('--jobs',type=int,default=4)
    r=sub.add_parser('run'); r.add_argument('profile',choices=['direct','generic','probe'],nargs='?',default='direct')
    sub.add_parser('clean'); sub.add_parser('package'); sub.add_parser('gate'); sub.add_parser('permissions')
    for name in ('deploy','recover','inspect','evidence'):
        x=sub.add_parser(name); x.add_argument('arguments',nargs=argparse.REMAINDER)
    for name in ('boot-image','irecovery','bringup','device','bridge','session','crash','trace','hardware','physical-validation'):
        x=sub.add_parser(name); x.add_argument('arguments',nargs=argparse.REMAINDER)
    m=sub.add_parser('module'); m.add_argument('arguments',nargs=argparse.REMAINDER)
    for kind in ('board','driver','module','transport'):
        x=sub.add_parser('new-'+kind); x.add_argument('name'); x.add_argument('destination',type=pathlib.Path); x.add_argument('--force',action='store_true')
    a=sub.add_parser('abi-check'); a.add_argument('manifest',nargs='?'); a.add_argument('--against')
    v=sub.add_parser('verify-release'); v.add_argument('manifest'); v.add_argument('--root'); v.add_argument('--signature'); v.add_argument('--public-key')
    c=sub.add_parser('compare-releases'); c.add_argument('first'); c.add_argument('second')
    e=sub.add_parser('evidence-compare'); e.add_argument('first'); e.add_argument('second')
    return p

def legacy(argv):
    if not argv or not argv[0].startswith('-') or argv[0] in {'--json'}: return None
    mapping={'--version':['version'],'--doctor':['doctor'],'-b':['build'],'--build':['build'],'--verify':['test'],'--gate':['gate'],'--package':['package'],'-c':['clean'],'--clean':['clean'],'--permissions':['permissions'],'--deployment-sim':['deploy','--simulator'],'-r':['run','direct'],'--run':['run','direct'],'--run-generic':['run','generic'],'--run-probe':['run','probe']}
    if len(argv)==1 and argv[0] in mapping: return mapping[argv[0]]
    return None

def main(argv=None):
    raw=list(sys.argv[1:] if argv is None else argv); converted=legacy(raw)
    if converted is not None:
        raw=converted
    elif raw and raw[0].startswith('-') and raw[0] not in {'--json','-h','--help'}:
        print(f'error: unknown option {raw[0]}', file=sys.stderr)
        return 2
    args=parser().parse_args(raw); j=args.json
    try:
        cmd=args.command
        if cmd=='version':
            print(json.dumps({'project':'FBR34KER','version':VERSION},sort_keys=True) if j else f'FBR34KER {VERSION}'); return 0
        if cmd=='doctor': return execute([sys.executable,'scripts/doctor.py'],json_mode=j)
        if cmd=='build': return make(['all','modules','generic','hardware-probe','sdk','generic-loader','loader-check','loader-conformance-test','deployment-simulate','apple-boot-images','apple-bringup-simulate','physical-validation-candidate'],j,[f'-j{args.jobs}'])
        if cmd=='test':
            rc=make(['verify'],j,[f'BUILD_JOBS={args.jobs}'])
            if rc or not args.qemu: return rc
            require_qemu(); return make(['integration','smoke','generic-qemu-smoke','probe-qemu-smoke'],j)
        if cmd=='clean': return make(['clean'],j)
        if cmd=='package': return make(['package'],j)
        if cmd=='gate': return make(['release-gate'],j)
        if cmd=='permissions': return make(['permissions'],j)
        if cmd=='run':
            require_qemu(); target={'direct':'run','generic':'generic-qemu-run','probe':'probe-qemu-smoke'}[args.profile]; return make([target],j)
        if cmd in {'deploy','recover','inspect','evidence'}:
            action={'recover':'reset'}.get(cmd,cmd)
            return execute([sys.executable,'host/fbr34kdeploy.py',action,*args.arguments],json_mode=j)
        if cmd=='module': return execute([sys.executable,'host/fbr34kctl.py',*args.arguments],json_mode=j)
        if cmd=='boot-image': return execute([sys.executable,'host/boot_image.py',*args.arguments],json_mode=j)
        if cmd=='irecovery': return execute([sys.executable,'host/irecovery_boot.py',*args.arguments],json_mode=j)
        if cmd=='bringup': return execute([sys.executable,'host/hardware_bringup.py',*args.arguments],json_mode=j)
        if cmd=='device': return execute([sys.executable,'host/device_tools.py',*args.arguments],json_mode=j)
        if cmd=='bridge': return execute([sys.executable,'host/reference_bridge.py',*args.arguments],json_mode=j)
        if cmd=='session': return execute([sys.executable,'host/session_tools.py',*args.arguments],json_mode=j)
        if cmd=='crash':
            values=list(args.arguments)
            if values and values[0]=='decode': values[0]='crash-decode'
            return execute([sys.executable,'host/session_tools.py',*values],json_mode=j)
        if cmd=='trace':
            values=list(args.arguments)
            if values and values[0]=='timeline': values[0]='trace-timeline'
            return execute([sys.executable,'host/session_tools.py',*values],json_mode=j)
        if cmd=='hardware': return execute([sys.executable,'host/hardware_workflow.py',*args.arguments],json_mode=j)
        if cmd=='physical-validation': return execute([sys.executable,'host/physical_validation.py',*args.arguments],json_mode=j)
        if cmd.startswith('new-'):
            argv2=[sys.executable,'scripts/scaffold.py',cmd[4:],args.name,args.destination]
            if args.force: argv2.append('--force')
            return execute(argv2,json_mode=j)
        if cmd=='abi-check':
            argv2=[sys.executable,'scripts/abi_check.py'];
            if args.manifest: argv2.append(args.manifest)
            if args.against: argv2 += ['--against',args.against]
            if j: argv2.append('--json')
            return execute(argv2,json_mode=False)
        if cmd=='verify-release':
            argv2=[sys.executable,'scripts/release_verify.py',args.manifest]
            for flag,value in [('--root',args.root),('--signature',args.signature),('--public-key',args.public_key)]:
                if value: argv2 += [flag,value]
            if j: argv2.append('--json')
            return execute(argv2,json_mode=False)
        if cmd=='compare-releases':
            argv2=[sys.executable,'scripts/compare_releases.py',args.first,args.second]
            if j: argv2.append('--json')
            return execute(argv2,json_mode=False)
        if cmd=='evidence-compare':
            return execute([sys.executable,'host/evidence_compare.py',args.first,args.second],json_mode=j)
        raise CliError('unknown command',2)
    except CliError as exc:
        if j: print(json.dumps({'ok':False,'exit_code':exc.code,'error':str(exc)},sort_keys=True))
        else: print(f'error: {exc}',file=sys.stderr)
        return exc.code
if __name__=='__main__': raise SystemExit(main())
