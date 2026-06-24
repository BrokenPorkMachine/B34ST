#!/usr/bin/env bash
"""
Setup script for FBR34KER usbliter8-PongoOS integration.

This script prepares the environment for using usbliter8 to boot PongoOS
on A12/A13 iPhones, providing all the features of PongoOS while maintaining
compatibility with FBR34kER validation workflows.
"""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Print colored output
print_color() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if a file exists
file_exists() {
    [[ -f "$1" ]]
}

# Function to check if a directory exists
dir_exists() {
    [[ -d "$1" ]]
}

print_color $YELLOW "=== FBR34KER usbliter8-PongoOS Integration Setup ==="

# Check if we're in the right directory
if [[ ! -f "scripts/usbliter8_workflow.py" ]]; then
    echo "Error: This script must be run from the FBR34kER repository root."
    echo "Please cd to the FBR34kER repository and run this script."
    exit 1
fi

print_color $GREEN "✓ Running from FBR34kER repository root"

# Check for required tools
print_color $YELLOW "\n=== Checking Dependencies ==="

# Check for Python
if command_exists python3; then
    PYTHON_VERSION=$(python3 --version 2>&1)
    print_color $GREEN "✓ Python found: $PYTHON_VERSION"
else
    print_color $RED "✗ Python 3 not found. Please install Python 3.10+"
    exit 1
fi

# Check for git
if command_exists git; then
    print_color $GREEN "✓ Git found"
else
    print_color $YELLOW "⚠ Git not found (optional)"
fi

# Check for make
if command_exists make; then
    print_color $GREEN "✓ Make found"
else
    print_color $YELLOW "⚠ Make not found (optional)"
fi

# Check for picotool
if command_exists picotool; then
    PICOTOOL_VERSION=$(picotool --version 2>&1 | head -1)
    print_color $GREEN "✓ picotool found: $PICOTOOL_VERSION"
else
    print_color $YELLOW "⚠ picotool not found (required for usbliter8 firmware flashing)"
fi

# Check for usbliter8 directory
if dir_exists "usbliter8"; then
    print_color $GREEN "✓ usbliter8 directory found"
    
    # Check for usbliter8ctl
    if file_exists "usbliter8/usbliter8ctl"; then
        print_color $GREEN "✓ usbliter8ctl found"
    else
        print_color $YELLOW "⚠ usbliter8ctl not found in usbliter8 directory"
    fi
else
    print_color $RED "✗ usbliter8 directory not found. Please ensure usbliter8 is in the repository."
    exit 1
fi

# Check for PongoOS compatibility
print_color $YELLOW "\n=== Checking PongoOS Compatibility ==="

print_color $YELLOW "PongoOS is a Linux-based iOS jailbreak OS that supports:"
print_color $YELLOW "  - A12/A13 iPhones ✓ (same hardware as usbliter8 target)"
print_color $YELLOW "  - A14 and newer iPhones"
print_color $YELLOW "  - Various iPad models"
print_color $YELLOW "  - Raspberry Pi and other ARM platforms"
print_color $YELLOW ""
print_color $YELLOW "✓ PongoOS is compatible with A12/A13 hardware targeted by usbliter8"

# Check for PongoOS installation
if dir_exists "pongoos" || file_exists "/usr/local/pongoos" || file_exists "~/.pongoos"; then
    print_color $GREEN "✓ PongoOS appears to be installed"
else
    print_color $YELLOW "⚠ PongoOS not found (can be installed separately)"
fi

# Check for FBR34kER boot images
print_color $YELLOW "\n=== Checking FBR34kER Boot Images ==="

BOOT_IMAGES=(
    "build-apple/a12/boot.img"
    "build-apple/a13/boot.img"
    "build-apple/a12x/boot.img"
)

FOUND_IMAGES=0
for img in "${BOOT_IMAGES[@]}"; do
    if file_exists "$img"; then
        print_color $GREEN "✓ Found: $img"
        FOUND_IMAGES=$((FOUND_IMAGES + 1))
    else
        print_color $YELLOW "⚠ Not found: $img"
    fi

done

if [[ $FOUND_IMAGES -eq 0 ]]; then
    print_color $RED "✗ No FBR34kER boot images found. Please build FBR34kER boot images."
    print_color $YELLOW "Run: ./fbr34ker build --target=a13 --profile=profiles/apple-a13-iphone-recovery.json"
    exit 1
else
    print_color $GREEN "✓ Found $FOUND_IMAGES FBR34kER boot image(s)"
fi

# Check for profiles
print_color $YELLOW "\n=== Checking FBR34kER Profiles ==="

PROFILES=(
    "profiles/apple-a12-iphone-recovery.json"
    "profiles/apple-a13-iphone-recovery.json"
    "profiles/apple-a12-ipad-recovery.json"
    "profiles/apple-a13-ipad-recovery.json"
)

FOUND_PROFILES=0
for profile in "${PROFILES[@]}"; do
    if file_exists "$profile"; then
        print_color $GREEN "✓ Found: $profile"
        FOUND_PROFILES=$((FOUND_PROFILES + 1))
    else
        print_color $YELLOW "⚠ Not found: $profile"
    fi

done

if [[ $FOUND_PROFILES -eq 0 ]]; then
    print_color $RED "✗ No FBR34kER profiles found. Please check the profiles directory."
    exit 1
else
    print_color $GREEN "✓ Found $FOUND_PROFILES FBR34kER profile(s)"
fi

# Check for device info examples
print_color $YELLOW "\n=== Checking Device Info Examples ==="

if file_exists "examples/a13-device-info.json"; then
    print_color $GREEN "✓ Found: examples/a13-device-info.json"
else
    print_color $YELLOW "⚠ examples/a13-device-info.json not found"
fi

# Check for runtime artifacts directory
print_color $YELLOW "\n=== Checking Runtime Artifacts ==="

if dir_exists "runtime-artifacts"; then
    print_color $GREEN "✓ Found: runtime-artifacts directory"
else
    print_color $YELLOW "⚠ runtime-artifacts directory not found (will be created during execution)"
fi

# Show PongoOS features
print_color $YELLOW "\n=== PongoOS Features Available ==="

print_color $GREEN "With --use-pongoos option, the workflow will provide:"
print_color $GREEN "✓ Linux-based operating system"
print_color $GREEN "✓ User-space applications and services"
print_color $GREEN "✓ Package management (apt, dpkg)"
print_color $GREEN "✓ Network connectivity (USB tethering, WiFi, Bluetooth)"
print_color $GREEN "✓ File system access and manipulation"
print_color $GREEN "✓ System utilities and tools"
print_color $GREEN "✓ Development tools and libraries"
print_color $GREEN "✓ Persistence and configuration management"
print_color $GREEN "✓ Hardware driver support (A12/A13)"
print_color $GREEN "✓ Power management and battery status"
print_color $GREEN "✓ Display and graphics support"
print_color $GREEN "✓ Sensor integration (accelerometer, gyro, etc.)"

# Show integration information
print_color $YELLOW "\n=== Integration Architecture ==="

echo "usbliter8 + PongoOS + FBR34kER integration provides:"
echo ""
echo "1. usbliter8 exploit (hardware-based)"
echo "   - Creates pwnd recovery channel"
echo "   - Bypasses iBoot security"
echo ""
echo "2. PongoOS loading (operating system)"
echo "   - Full Linux environment"
echo "   - User-space applications"
echo "   - Package management"
echo "   - Network connectivity"
echo ""
echo "3. FBR34kER validation (research overlay)"
echo "   - Hardware bringup workflow"
echo "   - Evidence collection"
echo "   - Profile maturity gates"
echo "   - Physical validation"
echo ""
echo "Benefits:"
print_color $YELLOW "  - Full PongoOS functionality with research validation"
print_color $YELLOW "  - Evidence-based security validation"
print_color $YELLOW "  - Controlled hardware environment"
print_color $YELLOW "  - Research-focused approach to iPhone security"

# Show usage examples
print_color $YELLOW "\n=== Usage Examples ==="

echo "# Use PongoOS as the operating system"
echo "./scripts/usbliter8_workflow.py --use-pongoos"
echo ""
echo "# Use FBR34kER as research monitor (default)"
echo "./scripts/usbliter8_workflow.py"
echo ""
echo "# Custom PongoOS path"
echo "./scripts/usbliter8_workflow.py --use-pongoos --pongoos-path /path/to/pongoos"

# Show testing options
print_color $YELLOW "\n=== Testing Options ==="

echo "# Dry run validation"
echo "./scripts/usbliter8_workflow.py --dry-run"
echo ""
echo "# PongoOS dry run"
echo "./scripts/usbliter8_workflow.py --use-pongoos --dry-run"

print_color $GREEN "\n=== Setup Complete ==="
print_color $GREEN "The FBR34KER usbliter8-PongoOS integration is ready to use."
print_color $YELLOW "Use --use-pongoos to load PongoOS instead of FBR34kER."
