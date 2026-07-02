#!/usr/bin/env sh

# SPDX-License-Identifier: BSD-2-Clause
set -eu
cd "$(dirname "$0")/.."
make all
exec qemu-system-aarch64 \
  -machine virt,gic-version=3 \
  -cpu cortex-a72 \
  -m 256M \
  -nographic \
  -monitor none \
  -serial stdio \
  -kernel build/fbr34ker.bin
