# KiCad DOOM Plugin Structure

## Main Plugin File
- `doom_plugin_action.py` - Enhanced ActionPlugin with logging and multi-process management

## Core Modules
- `config.py` - Configuration constants (paths, sizes, performance settings)
- `pcb_renderer.py` - Converts DOOM frames to PCB traces (wireframe mode)
- `doom_bridge.py` - Socket server for DOOM <-> Python communication
- `coordinate_transform.py` - DOOM pixels to KiCad nanometers conversion
- `object_pool.py` - Pre-allocated PCB objects for performance
- `input_handler.py` - Keyboard capture (currently disabled, using SDL input)
- `__init__.py` - Package initialization

## DOOM Files
- `doom/doomgeneric_kicad` - Dual-mode DOOM binary (SDL + socket output)
- `doom/doom1.wad` - DOOM shareware game data

## Documentation
- `README.md` - Original plugin documentation
- `STRUCTURE.md` - This file

## Features
1. **Triple Rendering**:
   - SDL window (playable DOOM)
   - Python wireframe window
   - KiCad PCB traces

2. **Logging**: Creates detailed logs in `~/Desktop/KiDoom/logs/plugin/`

3. **Non-blocking**: Uses background thread to monitor processes

4. **Coordinated shutdown**: Closes all components cleanly