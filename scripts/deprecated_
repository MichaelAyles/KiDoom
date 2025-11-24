"""
KiDoom - DOOM on PCB Traces Plugin for KiCad

This plugin renders DOOM gameplay using real PCB traces in KiCad PCBnew.
Wall segments become PCB_TRACK objects, entities become footprints, and
projectiles become vias.

Expected performance: 40-60 FPS on modern hardware (M1 MacBook: 60+ FPS)
"""

import pcbnew
import os
import sys

print("=" * 70)
print("KiDoom plugin loading...")
print("=" * 70)

# Add plugin directory to path so we can import the modules
plugin_dir = os.path.join(os.path.dirname(__file__), 'kicad_doom_plugin')
print(f"Plugin directory: {plugin_dir}")

if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)
    print(f"Added to sys.path")

try:
    print("Importing DoomKiCadPlugin...")
    from doom_plugin_action import DoomKiCadPlugin

    print("Registering plugin with KiCad...")
    # Register the plugin with KiCad
    DoomKiCadPlugin().register()

    print("✓ KiDoom plugin registered successfully!")
    print("  Look for 'KiDoom - DOOM on PCB' in Tools → External Plugins")
    print("=" * 70)

except Exception as e:
    print(f"✗ ERROR loading KiDoom plugin: {e}")
    import traceback
    traceback.print_exc()
    print("=" * 70)
