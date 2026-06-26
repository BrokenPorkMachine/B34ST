#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
SOCKET_PATH="${FBR34KER_SOCKET:-build/fbr34ker.sock}"
rm -f "$SOCKET_PATH"
make all modules
printf 'FBR34KER serial socket: %s\n' "$SOCKET_PATH"
printf 'Framed hello: python3 host/fbr34kctl.py hello --unix %s\n' "$SOCKET_PATH"
printf 'Raw console:  python3 host/fbr34kctl.py console --unix %s\n' "$SOCKET_PATH"
exec qemu-system-aarch64 \
  -machine virt,gic-version=3 \
  -cpu cortex-a72 \
  -m 256M \
  -display none \
  -monitor none \
  -serial "unix:${SOCKET_PATH},server=on,wait=off" \
  -kernel build/fbr34ker.bin
