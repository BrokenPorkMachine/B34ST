#!/usr/bin/env python3
"""Compare two deterministic FBR34KER archives without extracting them."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile


def members(path):
    out = {}
    with zipfile.ZipFile(path) as z:
        if z.testzip() is not None:
            raise ValueError(f"CRC failure in {path}")
        for info in z.infolist():
            rel = "/".join(info.filename.split("/")[1:])
            if not rel:
                continue
            out[rel] = hashlib.sha256(z.read(info)).hexdigest()
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("first")
    p.add_argument("second")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    try:
        x, y = members(a.first), members(a.second)
        added = sorted(y.keys() - x.keys())
        removed = sorted(x.keys() - y.keys())
        changed = sorted(k for k in x.keys() & y.keys() if x[k] != y[k])
        same = not (added or removed or changed)
        r = {"identical": same, "added": added, "removed": removed, "changed": changed}
    except (OSError, ValueError, zipfile.BadZipFile) as e:
        r = {"identical": False, "errors": [str(e)]}
    print(
        json.dumps(r, sort_keys=True)
        if a.json
        else (
            "archives are reproducible"
            if r.get("identical")
            else json.dumps(r, indent=2, sort_keys=True)
        )
    )
    return 0 if r.get("identical") else 1


if __name__ == "__main__":
    raise SystemExit(main())
