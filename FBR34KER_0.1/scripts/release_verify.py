#!/usr/bin/env python3
"""Verify a FBR34KER release manifest, artifact hashes, and optional signature."""
from __future__ import annotations
import argparse, hashlib, json, pathlib, subprocess, sys
MAX_MANIFEST=2*1024*1024

def sha256(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()
def safe_relative(value):
    p=pathlib.PurePosixPath(value)
    if p.is_absolute() or not p.parts or '..' in p.parts or '\\' in value: raise ValueError(f"unsafe artifact path: {value}")
    return p
def verify_signature(manifest,signature,public_key):
    cmd=['openssl','pkeyutl','-verify','-rawin','-pubin','-inkey',str(public_key),'-sigfile',str(signature),'-in',str(manifest)]
    return subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,check=False).returncode==0

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('manifest',type=pathlib.Path)
    p.add_argument('--root',type=pathlib.Path); p.add_argument('--signature',type=pathlib.Path); p.add_argument('--public-key',type=pathlib.Path); p.add_argument('--json',action='store_true')
    a=p.parse_args(argv); errors=[]
    try:
        if a.manifest.stat().st_size>MAX_MANIFEST: raise ValueError('manifest exceeds 2 MiB')
        data=json.loads(a.manifest.read_text(encoding='utf-8'))
        if data.get('schema_version') not in {1,2}: raise ValueError('unsupported release manifest schema')
        root=(a.root or a.manifest.parent).resolve(); artifacts=data.get('artifacts')
        if not isinstance(artifacts,list) or len(artifacts)>512: raise ValueError('invalid artifact list')
        seen=set()
        for record in artifacts:
            if not isinstance(record,dict): errors.append('artifact record is not an object'); continue
            rel=safe_relative(record.get('path','')).as_posix()
            if rel in seen: errors.append(f'duplicate artifact: {rel}'); continue
            seen.add(rel); path=(root/rel).resolve()
            try: path.relative_to(root)
            except ValueError: errors.append(f'artifact escapes root: {rel}'); continue
            if not path.is_file(): errors.append(f'missing artifact: {rel}'); continue
            if path.stat().st_size!=record.get('size'): errors.append(f'size mismatch: {rel}')
            if sha256(path)!=record.get('sha256'): errors.append(f'hash mismatch: {rel}')
        if bool(a.signature) != bool(a.public_key): errors.append('signature and public key must be supplied together')
        elif a.signature and not verify_signature(a.manifest,a.signature,a.public_key): errors.append('signature verification failed')
        result={'passed':not errors,'version':data.get('version'),'artifacts_checked':len(artifacts),'signature_checked':bool(a.signature),'errors':errors}
    except (OSError,ValueError,json.JSONDecodeError) as exc:
        result={'passed':False,'artifacts_checked':0,'signature_checked':False,'errors':[str(exc)]}
    if a.json: print(json.dumps(result,sort_keys=True))
    elif result['passed']: print(f"release verification passed ({result['artifacts_checked']} artifacts)")
    else:
        for e in result['errors']: print(f"VERIFY ERROR: {e}",file=sys.stderr)
    return 0 if result['passed'] else 1
if __name__=='__main__': raise SystemExit(main())
