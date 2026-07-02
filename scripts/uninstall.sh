#!/usr/bin/env sh

# SPDX-License-Identifier: BSD-2-Clause
set -eu

usage() {
    cat <<'USAGE'
Usage: scripts/uninstall.sh [--prefix PATH] [--destdir PATH]

Remove files installed by scripts/install.sh. PREFIX defaults to /usr/local.
USAGE
}

PREFIX=${PREFIX:-/usr/local}
DESTDIR=${DESTDIR:-}
while [ "$#" -gt 0 ]; do
    case "$1" in
        --prefix) [ "$#" -ge 2 ] || { echo "missing --prefix value" >&2; exit 2; }; PREFIX=$2; shift 2 ;;
        --destdir) [ "$#" -ge 2 ] || { echo "missing --destdir value" >&2; exit 2; }; DESTDIR=$2; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
done
case "$PREFIX" in /*) ;; *) echo "PREFIX must be absolute" >&2; exit 2 ;; esac
case "$DESTDIR" in ""|/*) ;; *) echo "DESTDIR must be empty or absolute" >&2; exit 2 ;; esac

rm -f "$DESTDIR$PREFIX/bin/fbr34ker"
rm -f "$DESTDIR$PREFIX/bin/B34ST"
rm -f "$DESTDIR$PREFIX/bin/b34stctl"
rm -f "$DESTDIR$PREFIX/share/man/man1/fbr34ker.1"
rm -f "$DESTDIR$PREFIX/share/man/man1/B34ST.1"
rm -f "$DESTDIR$PREFIX/share/bash-completion/completions/fbr34ker"
rm -f "$DESTDIR$PREFIX/share/zsh/site-functions/_fbr34ker"
rm -rf "$DESTDIR$PREFIX/share/fbr34ker"
printf 'removed FBR34KER from %s\n' "$DESTDIR$PREFIX"
