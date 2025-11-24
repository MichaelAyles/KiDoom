#!/bin/bash
# KiDoom - Run DOOM Binary
# Entry point for running DOOM with various options

cd "$(dirname "$0")"

DOOM_BINARY="doom/doomgeneric_kicad"  # Single binary, always dual mode

show_help() {
    echo "KiDoom - Run DOOM (Dual Mode: SDL + Vectors)"
    echo ""
    echo "Usage:"
    echo "  $0 [options]"
    echo ""
    echo "Options:"
    echo "  -w E M    - Warp to episode E, map M (e.g., -w 1 1)"
    echo "  -h        - Show this help"
    echo ""
    echo "Examples:"
    echo "  $0          # Start from menu"
    echo "  $0 -w 1 1   # Skip to E1M1"
    echo ""
    echo "Note: Always shows SDL window + sends vectors to Python renderer"
}

WARP_ARGS=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
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

# Check binary exists
if [[ ! -f "$DOOM_BINARY" ]]; then
    echo "ERROR: DOOM binary not found: $DOOM_BINARY"
    echo "Build it with: cd doom/source && ./build.sh"
    exit 1
fi

echo "Starting DOOM (Dual Mode: SDL + Vectors)..."
"$DOOM_BINARY" -iwad doom/doom1.wad $WARP_ARGS
