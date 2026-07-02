#!/usr/bin/env python3

"""Root script wrapper for the B34ST guided research-runtime orchestrator."""
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from b34st.research_runtime import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
