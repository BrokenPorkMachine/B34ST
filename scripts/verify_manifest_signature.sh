#!/usr/bin/env sh

# SPDX-License-Identifier: BSD-2-Clause
set -eu

if [ "$#" -ne 3 ]; then
    echo "usage: $0 MANIFEST SIGNATURE PUBLIC_KEY" >&2
    exit 2
fi

manifest=$1
signature=$2
public_key=$3

if command -v minisign >/dev/null 2>&1 && grep -q 'untrusted comment:' "$signature" 2>/dev/null; then
    exec minisign -V -p "$public_key" -m "$manifest" -x "$signature"
fi

command -v openssl >/dev/null 2>&1 || {
    echo "openssl is required to verify this signature" >&2
    exit 1
}
exec openssl dgst -sha256 -verify "$public_key" -signature "$signature" "$manifest"
