#!/usr/bin/env python3

"""Compatibility launcher for the renamed FBR34KER host controller."""
# SPDX-License-Identifier: BSD-2-Clause
from fbr34kctl import main

if __name__ == "__main__":
    raise SystemExit(main())
