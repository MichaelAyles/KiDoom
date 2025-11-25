#!/usr/bin/env python3
"""
ScopeDoom Launcher

Starts the oscilloscope-style DOOM renderer.
Run DOOM separately with: ./run_doom.sh dual -w 1 1
"""

import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scope_renderer import ScopeRenderer


def main():
    print("=" * 70)
    print("ScopeDoom - Oscilloscope-style DOOM Renderer")
    print("=" * 70)
    print()
    print("This renderer displays DOOM as vector graphics.")
    print()
    print("To start DOOM, run in another terminal:")
    print("  ./run_doom.sh dual -w 1 1")
    print()
    print("=" * 70)

    renderer = ScopeRenderer()
    renderer.run()


if __name__ == '__main__':
    main()
