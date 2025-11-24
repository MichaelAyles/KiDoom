#!/bin/bash
#
# build.sh - Automated build script for KiCad DOOM platform
#
# This script automates the entire build process:
# 1. Clone doomgeneric (if not present)
# 2. Copy platform files
# 3. Build binary
# 4. Copy to plugin directory
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DOOMGENERIC_DIR="$(cd "$PROJECT_ROOT/.." && pwd)/doomgeneric"
PLUGIN_DOOM_DIR="$PROJECT_ROOT/doom"

echo ""
echo "========================================"
echo "  KiDoom Build Script"
echo "========================================"
echo ""
echo "Project root: $PROJECT_ROOT"
echo "Source files: $SCRIPT_DIR"
echo ""

# Step 1: Clone doomgeneric if needed
if [ ! -d "$DOOMGENERIC_DIR" ]; then
    echo -e "${YELLOW}Step 1: Cloning doomgeneric...${NC}"
    cd "$PROJECT_ROOT"
    git clone https://github.com/ozkl/doomgeneric.git
    echo -e "${GREEN}✓ doomgeneric cloned${NC}"
else
    echo -e "${GREEN}✓ doomgeneric already present${NC}"
fi

# Step 2: Copy platform files
echo ""
echo -e "${YELLOW}Step 2: Copying platform files...${NC}"
cp -v "$SCRIPT_DIR/doomgeneric_kicad_dual.c" "$DOOMGENERIC_DIR/doomgeneric/"
cp -v "$SCRIPT_DIR/doomgeneric_kicad_dual_v2.c" "$DOOMGENERIC_DIR/doomgeneric/"
cp -v "$SCRIPT_DIR/doomgeneric_sdl_dual.c" "$DOOMGENERIC_DIR/doomgeneric/"
cp -v "$SCRIPT_DIR/doom_socket.c" "$DOOMGENERIC_DIR/doomgeneric/"
cp -v "$SCRIPT_DIR/doom_socket.h" "$DOOMGENERIC_DIR/doomgeneric/"
cp -v "$SCRIPT_DIR/Makefile.kicad" "$DOOMGENERIC_DIR/doomgeneric/"
cp -v "$SCRIPT_DIR/Makefile.kicad_dual" "$DOOMGENERIC_DIR/doomgeneric/"
echo -e "${GREEN}✓ Platform files copied${NC}"

# Step 3: Build
echo ""
echo -e "${YELLOW}Step 3: Building DOOM (Dual Mode: SDL + Vectors)...${NC}"
cd "$DOOMGENERIC_DIR/doomgeneric"
make -f Makefile.kicad_dual clean || true  # Clean previous build
make -f Makefile.kicad_dual

if [ -f "doomgeneric_kicad_dual" ]; then
    echo -e "${GREEN}✓ Build successful!${NC}"
else
    echo -e "${RED}✗ Build failed - binary not created${NC}"
    exit 1
fi

# Step 4: Copy to plugin directory (rename dual to standard name)
echo ""
echo -e "${YELLOW}Step 4: Installing binary...${NC}"
mkdir -p "$PLUGIN_DOOM_DIR"
cp -v doomgeneric_kicad_dual "$PLUGIN_DOOM_DIR/doomgeneric_kicad"
chmod +x "$PLUGIN_DOOM_DIR/doomgeneric_kicad"
echo -e "${GREEN}✓ Dual-mode binary installed as $PLUGIN_DOOM_DIR/doomgeneric_kicad${NC}"
echo -e "${GREEN}  (Shows SDL window + sends vectors)${NC}"

# Step 5: Check for WAD file
echo ""
echo -e "${YELLOW}Step 5: Checking for WAD file...${NC}"
if [ -f "$PLUGIN_DOOM_DIR/doom1.wad" ]; then
    echo -e "${GREEN}✓ doom1.wad found${NC}"
else
    echo -e "${RED}✗ doom1.wad not found${NC}"
    echo ""
    echo "You need to download a DOOM WAD file:"
    echo ""
    echo "Option 1 - Shareware (free):"
    echo "  cd $PLUGIN_DOOM_DIR"
    echo "  wget https://distro.ibiblio.org/slitaz/sources/packages/d/doom1.wad"
    echo ""
    echo "Option 2 - Full version (if you own it):"
    echo "  Copy DOOM.WAD from your Steam/GOG installation"
    echo ""
fi

# Summary
echo ""
echo "========================================"
echo "  Build Complete!"
echo "========================================"
echo ""
echo "Binary location: $PLUGIN_DOOM_DIR/doomgeneric_kicad"
echo ""
echo "Next steps:"
echo "  1. Ensure doom1.wad is in $PLUGIN_DOOM_DIR/"
echo "  2. Implement Python KiCad plugin (Phase 2)"
echo "  3. Run KiCad plugin to start socket server"
echo "  4. Launch $PLUGIN_DOOM_DIR/doomgeneric_kicad"
echo ""
echo "To test socket connection:"
echo "  cd $PROJECT_ROOT/tests"
echo "  python3 benchmark_socket.py"
echo ""
