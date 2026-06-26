#!/usr/bin/env python3
"""Create bounded FBR34KER board, driver, module, or transport templates."""
from __future__ import annotations
import argparse, pathlib, re, shutil, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
TEMPLATES=ROOT/"sdk/templates"
KINDS={"board","driver","module","transport"}

def safe_name(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,47}", value):
        raise ValueError("name must begin with a letter and contain only letters, digits, '_' or '-'")
    return value

def render_tree(kind: str, name: str, destination: pathlib.Path, force: bool=False) -> list[pathlib.Path]:
    source=TEMPLATES/kind
    if not source.is_dir(): raise ValueError(f"missing {kind} template")
    if destination.exists() and any(destination.iterdir()) and not force:
        raise ValueError(f"destination is not empty: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    identifier=name.replace('-','_').lower(); upper=identifier.upper()
    written=[]
    for item in sorted(source.rglob('*')):
        if item.is_dir(): continue
        rel=pathlib.Path(item.relative_to(source).as_posix().replace('__name__',identifier))
        target=destination/rel; target.parent.mkdir(parents=True, exist_ok=True)
        text=item.read_text(encoding='utf-8').replace('{{NAME}}',name).replace('{{IDENT}}',identifier).replace('{{UPPER}}',upper)
        target.write_text(text, encoding='utf-8'); written.append(target)
    return written

def main(argv=None)->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("kind", choices=sorted(KINDS)); p.add_argument("name"); p.add_argument("destination", type=pathlib.Path)
    p.add_argument("--force",action="store_true")
    a=p.parse_args(argv)
    try:
        paths=render_tree(a.kind,safe_name(a.name),a.destination.resolve(),a.force)
    except (OSError,ValueError) as exc:
        print(f"scaffold error: {exc}",file=sys.stderr); return 2
    for path in paths: print(path)
    return 0
if __name__=="__main__": raise SystemExit(main())
