#!/bin/bash
# KiDoom - Run DOOM Binary
# Entry point for running DOOM with various options

cd "$(dirname "$0")"

DOOM_BINARY="doom/doomgeneric_kicad"
DOOM_DUAL="doom/doomgeneric_kicad_dual"

show_help() {
    echo "KiDoom - Run DOOM on PCB"
    echo ""
    echo "Usage:"
    echo "  $0 [mode] [options]"
    echo ""
    echo "Modes:"
    echo "  vector    - Vector-only mode (requires standalone renderer)"
    echo "  dual      - Dual mode: SDL window + vectors (default)"
    echo ""
    echo "Options:"
    echo "  -w E M    - Warp to episode E, map M (e.g., -w 1 1)"
    echo "  -h        - Show this help"
    echo ""
    echo "Examples:"
    echo "  $0              # Dual mode, start from menu"
    echo "  $0 dual -w 1 1  # Dual mode, skip to E1M1"
    echo "  $0 vector       # Vector only (start renderer first!)"
}

MODE="dual"
WARP_ARGS=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        vector)
            MODE="vector"
            shift
            ;;
        dual)
            MODE="dual"
            shift
            ;;
        -w)
            WARP_ARGS="-warp $2 $3"
            shift 3
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

if [[ "$MODE" == "dual" ]]; then
    if [[ ! -f "$DOOM_DUAL" ]]; then
        echo "ERROR: Dual mode binary not found: $DOOM_DUAL"
        echo "Build it with: cd doom/source && ./build.sh"
        exit 1
    fi
    echo "Starting DOOM in dual mode (SDL + Vectors)..."
    "$DOOM_DUAL" -iwad doom/doom1.wad $WARP_ARGS
elif [[ "$MODE" == "vector" ]]; then
    if [[ ! -f "$DOOM_BINARY" ]]; then
        echo "ERROR: Vector mode binary not found: $DOOM_BINARY"
        echo "Build it with: cd doom/source && ./build.sh"
        exit 1
    fi
    echo "Starting DOOM in vector-only mode..."
    echo "Make sure standalone renderer is running first!"
    "$DOOM_BINARY" -iwad doom/doom1.wad $WARP_ARGS
fi
