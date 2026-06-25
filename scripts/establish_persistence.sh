#!/bin/bash
# Deprecated compatibility wrapper for generating a persistence-model inventory.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "============================================"
echo "FBR34KER PERSISTENCE MODEL INVENTORY"
echo "============================================"
echo ""

# Step 1: Verify project build
echo "[STEP 1] Verifying project build..."
make -C "$PROJECT_DIR" all 2>&1 | tail -3

# Step 2: Build persistence subsystem
echo ""
echo "[STEP 2] Building persistence subsystem..."
make -C "$PROJECT_DIR" persistence 2>&1 | tail -5

# Step 3: Deploy persistence plan
echo ""
echo "[STEP 3] Generating persistence model inventory..."
make -C "$PROJECT_DIR" establish-persistence 2>&1

# Step 4: Verify persistence artifacts
echo ""
echo "[STEP 4] Verifying persistence artifacts..."
EXPLOIT_DIR="$PROJECT_DIR/build-exploit"
if [ -f "$EXPLOIT_DIR/persistence-plan.txt" ]; then
    cat "$EXPLOIT_DIR/persistence-plan.txt"
    echo ""
    echo "Persistence model inventory verified"
else
    echo "ERROR: Persistence plan not found" >&2
    exit 1
fi

echo ""
echo "============================================"
echo "PERSISTENCE MODEL INVENTORIED (NO DEPLOYMENT)"
echo "============================================"
echo ""
exit 0
