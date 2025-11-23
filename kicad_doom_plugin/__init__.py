"""
KiDoom - DOOM on PCB Traces Plugin for KiCad

This plugin renders DOOM gameplay using real PCB traces in KiCad PCBnew.
Wall segments become PCB_TRACK objects, entities become footprints, and
projectiles become vias.

Expected performance: 40-60 FPS on modern hardware (M1 MacBook: 60+ FPS)
"""

from .doom_plugin_action import DoomKiCadPlugin

# Register the plugin with KiCad
DoomKiCadPlugin().register()
