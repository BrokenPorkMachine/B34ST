#!/usr/bin/env sh
set -eu

if [ "$#" -lt 3 ]; then
    echo "usage: run_static_analysis.sh INCLUDE_DIR SOURCE_ID SOURCE..." >&2
    exit 2
fi
include_dir=$1
source_id=$2
shift 2
clang_bin=${CLANG:-clang}
case "$clang_bin" in
    */*) [ -x "$clang_bin" ] || { echo "clang not executable: $clang_bin" >&2; exit 1; } ;;
    *) command -v "$clang_bin" >/dev/null 2>&1 || { echo "clang not found: $clang_bin" >&2; exit 1; } ;;
esac
if command -v timeout >/dev/null 2>&1; then
    timeout_bin=timeout
elif command -v gtimeout >/dev/null 2>&1; then
    timeout_bin=gtimeout
else
    timeout_bin=
fi
total=$#
index=0
for source in "$@"; do
    index=$((index + 1))
    printf '[analyze %02d/%02d] %s\n' "$index" "$total" "$source"
    [ -f "$source" ] || { echo "missing source: $source" >&2; exit 1; }
    if [ -n "$timeout_bin" ]; then
        "$timeout_bin" 30 "$clang_bin" --target=aarch64-none-elf --analyze \
            -std=c11 -ffreestanding -fno-builtin -fno-omit-frame-pointer \
            -mgeneral-regs-only -march=armv8-a \
            -DFBR34KER_BUILD_TARGET=\"analysis\" \
            -DFBR34KER_SOURCE_ID=\"$source_id\" \
            -I"$include_dir" -Wall -Wextra -Werror "$source" -o /dev/null
    else
        "$clang_bin" --target=aarch64-none-elf --analyze \
            -std=c11 -ffreestanding -fno-builtin -fno-omit-frame-pointer \
            -mgeneral-regs-only -march=armv8-a \
            -DFBR34KER_BUILD_TARGET=\"analysis\" \
            -DFBR34KER_SOURCE_ID=\"$source_id\" \
            -I"$include_dir" -Wall -Wextra -Werror "$source" -o /dev/null
    fi
done
printf 'clang static analysis passed without findings (%d files)\n' "$total"
