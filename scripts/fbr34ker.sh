#!/usr/bin/env sh

# SPDX-License-Identifier: BSD-2-Clause
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec "$ROOT/fbr34ker" "$@"
