#!/bin/bash
# SPDX-License-Identifier: BSD-2-Clause

# FBR34KER persistence deployment plan generator.
# Builds the persistence subsystem and generates the deployment inventory.
#
# For operational mode with mutation paths enabled:
#   make SECURITY_MODEL=1 build-operational

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "============================================"
echo "FBR34KER PERSISTENCE DEPLOYMENT PLAN"
echo "============================================"
echo ""

# Step 1: Verify project build
echo "[STEP 1] Verifying project build..."
make -C "$PROJECT_DIR" all 2>&1 | tail -3

# Step 2: Build persistence subsystem
echo ""
echo "[STEP 2] Building persistence subsystem..."
make -C "$PROJECT_DIR" persistence 2>&1 | tail -5

# Step 3: Generate persistence deployment plan
echo ""
echo "[STEP 3] Generating persistence deployment plan..."
make -C "$PROJECT_DIR" establish-persistence 2>&1

# Step 4: Build operational persistence (SECURITY_MODEL=1)
echo ""
echo "[STEP 4] Building operational persistence..."
make -C "$PROJECT_DIR" SECURITY_MODEL=1 persistence 2>&1 | tail -5

# Step 5: Verify persistence artifacts
echo ""
echo "[STEP 5] Verifying persistence artifacts..."
EXPLOIT_DIR="$PROJECT_DIR/build-exploit"
if [ -f "$EXPLOIT_DIR/persistence-plan.txt" ]; then
    cat "$EXPLOIT_DIR/persistence-plan.txt"
    echo ""
    echo "Persistence deployment plan verified"
else
    echo "ERROR: Persistence plan not found" >&2
    exit 1
fi

echo ""
echo "============================================"
echo "PERSISTENCE DEPLOYMENT PLAN READY"
echo "============================================"
echo ""
echo "Default build (mutation disabled): make"
echo "Operational build (mutation enabled): make SECURITY_MODEL=1 build-operational"
echo ""
exit 0
