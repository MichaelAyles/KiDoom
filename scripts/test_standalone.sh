#!/bin/bash
# Quick test script for standalone renderer

echo "======================================================================="
echo "KiDoom Standalone Renderer Test"
echo "======================================================================="
echo ""

# Check if pygame is installed
echo "Checking dependencies..."
if ! python3 -c "import pygame" 2>/dev/null; then
    echo "ERROR: pygame not installed!"
    echo ""
    echo "Install with:"
    echo "  pip3 install pygame"
    echo ""
    exit 1
fi
echo "✓ pygame installed"
echo ""

# Check if DOOM binary exists
if [ ! -f "doom/doomgeneric_kicad" ]; then
    echo "ERROR: DOOM binary not found!"
    echo ""
    echo "Expected: doom/doomgeneric_kicad"
    echo ""
    echo "Build it with:"
    echo "  cd doom && make -f Makefile.kicad"
    echo ""
    exit 1
fi
echo "✓ DOOM binary found"
echo ""

# Remove old socket
if [ -e "/tmp/kicad_doom.sock" ]; then
    echo "Removing old socket..."
    rm /tmp/kicad_doom.sock
fi

echo "======================================================================="
echo "Instructions:"
echo "======================================================================="
echo ""
echo "1. This terminal: Standalone renderer will start"
echo "2. Open ANOTHER terminal and run:"
echo "     cd /Users/tribune/Desktop/KiDoom/doom"
echo "     ./doomgeneric_kicad"
echo ""
echo "3. Play DOOM in the pygame window!"
echo ""
echo "Press Ctrl+C to abort startup, or close window to quit later."
echo ""
echo "======================================================================="
echo ""

# Give user a moment to read
sleep 3

# Launch renderer
echo "Starting renderer..."
python3 standalone_renderer.py
