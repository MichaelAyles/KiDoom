#!/usr/bin/env python3
"""
KiDoom Standalone Renderer - Entry Point

Runs the standalone vector renderer for testing DOOM without KiCad.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from standalone_renderer import main

if __name__ == '__main__':
    main()
