#!/usr/bin/env sh
set -eu

if [ "$#" -ne 2 ]; then
    echo "usage: $0 MANIFEST PRIVATE_KEY" >&2
    exit 2
fi

manifest=$1
key=$2
[ -f "$manifest" ] || { echo "manifest not found: $manifest" >&2; exit 1; }
[ -f "$key" ] || { echo "private key not found: $key" >&2; exit 1; }

signature="${manifest}.sig"
if command -v minisign >/dev/null 2>&1; then
    minisign -S -s "$key" -m "$manifest" -x "$signature"
    echo "$signature"
    exit 0
fi

if command -v openssl >/dev/null 2>&1; then
    openssl dgst -sha256 -sign "$key" -out "$signature" "$manifest"
    echo "$signature"
    exit 0
fi

echo "neither minisign nor openssl is installed" >&2
exit 1
