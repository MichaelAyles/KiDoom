# KiDoom - DOOM on PCB Plugin

Python plugin for KiCad that renders DOOM gameplay using real PCB traces as the display medium.

## What This Is

This plugin converts DOOM's 3D graphics into PCB elements:
- **Wall segments** → Copper traces (PCB_TRACK)
- **Player & enemies** → Component footprints (QFP, SOT-23, TO-220, DIP-8)
- **Projectiles** → Vias (drilled holes)
- **HUD** → Silkscreen text

The result is a fully playable DOOM game rendered as an electrically authentic PCB design.

## Performance

Benchmarked performance (M1 MacBook Pro, 2020):
- **82.6 FPS** in benchmarks (200 traces)
- **Expected gameplay: 40-60 FPS**
- Display refresh is 96.3% of frame time (GPU bottleneck)
- Socket IPC overhead: 0.049ms (negligible)

## Installation

### Prerequisites

1. **KiCad 6+** with Python scripting support
2. **Python 3.7+**
3. **pynput** library for keyboard capture:
   ```bash
   pip install pynput
   ```

### Install Plugin

1. Find KiCad plugin directory:
   - In KiCad: `Tools → External Plugins → Open Plugin Directory`

2. Copy or symlink the plugin:
   ```bash
   # Option 1: Symlink (recommended for development)
   ln -s /path/to/KiDoom/kicad_doom_plugin ~/.kicad/scripting/plugins/

   # Option 2: Copy
   cp -r /path/to/KiDoom/kicad_doom_plugin ~/.kicad/scripting/plugins/
   ```

3. Restart KiCad

### Build DOOM Engine

The plugin requires a compiled DOOM binary (`doomgeneric_kicad`). See the main project README for build instructions.

## Usage

### Running DOOM

1. Open KiCad PCBnew
2. Create or open a PCB (blank PCB works fine)
3. Click: `Tools → External Plugins → DOOM on PCB`
4. Wait for DOOM to launch and connect
5. Play!

### Controls

**Movement:**
- W/S - Forward/Backward
- A/D - Strafe Left/Right
- Arrow keys - Turn Left/Right

**Actions:**
- Ctrl - Fire weapon
- Space/E - Use/Open doors
- 1-7 - Select weapon
- Esc - Menu/Quit

### Performance Tips

For best FPS, configure these settings in KiCad:

1. **View → Show Grid:** OFF (saves 5-10%)
2. **View → Ratsnest:** OFF (saves 20-30%)
3. **Preferences → Display Options:**
   - Clearance outlines: OFF
   - Pad/Via holes: Do not show
4. **Preferences → Graphics:**
   - Antialiasing: Fast or Disabled (saves 5-15%)
   - Rendering engine: Accelerated

These settings can improve FPS by 50-100%!

## Architecture

### File Structure

```
kicad_doom_plugin/
├── __init__.py                 # Plugin registration
├── config.py                   # Configuration constants
├── coordinate_transform.py     # DOOM ↔ KiCad coordinate conversion
├── doom_bridge.py              # Unix socket IPC server
├── doom_plugin_action.py       # Main ActionPlugin entry point
├── input_handler.py            # OS-level keyboard capture
├── object_pool.py              # Pre-allocated PCB objects
├── pcb_renderer.py             # Core rendering engine
└── doom/                       # DOOM engine binaries
    ├── doomgeneric_kicad       # Compiled DOOM binary
    └── doom1.wad               # Game data (shareware)
```

### Communication Protocol

Binary protocol over Unix domain socket (`/tmp/kicad_doom.sock`):

```
[4 bytes: message_type][4 bytes: payload_length][N bytes: JSON payload]
```

**Message Types:**
- `0x01` FRAME_DATA - DOOM → Python (rendering data)
- `0x02` KEY_EVENT - Python → DOOM (keyboard input)
- `0x03` INIT_COMPLETE - Python → DOOM (ready signal)
- `0x04` SHUTDOWN - Bidirectional (cleanup)

### Rendering Pipeline

1. **DOOM engine** (C) generates frame data
2. **Socket bridge** receives frame via Unix socket (0.049ms)
3. **PCB renderer** converts to PCB objects:
   - Walls → Update trace positions (0.44ms)
   - Entities → Update footprint positions
   - Projectiles → Update via positions
   - HUD → Update text elements
4. **Display refresh** calls `pcbnew.Refresh()` (11.67ms)
5. **Repeat** 20-60 times per second

## Performance Optimizations

### Object Pooling

All PCB objects are pre-allocated at startup:
- **500 traces** (walls)
- **20 footprints** (entities)
- **50 vias** (projectiles)
- **10 text elements** (HUD)

Objects are reused by updating positions, not destroyed/recreated. This provides:
- 1.08x average speedup
- 53% reduction in worst-case frame time (33ms → 15ms)
- Prevents garbage collection pauses

### Single Shared Net

All DOOM geometry connects to one net (`DOOM_WORLD`):
- Eliminates ratsnest calculation (20-30% speedup)
- Electrically authentic (could be fabricated)
- Improves KiCad rendering performance

### Minimal Layers

Only 2 copper layers + 1 silkscreen:
- F.Cu (red) - Close walls
- B.Cu (cyan) - Far walls
- F.SilkS (white) - HUD text

This reduces rendering overhead by 30-40%.

## Troubleshooting

### Plugin doesn't appear in KiCad

**Check:**
1. Plugin files in correct directory
2. KiCad version supports Python plugins (6+)
3. No Python syntax errors (check scripting console)

### DOOM binary not found

**Solution:**
Compile the DOOM engine first. See main project README for instructions.

### Input doesn't work

**Check:**
1. `pynput` is installed: `pip install pynput`
2. On macOS: Grant accessibility permissions to Terminal/KiCad
3. KiCad window has focus

### Performance is slow (< 10 FPS)

**Check:**
1. All manual settings configured (see Performance Tips above)
2. Grid is disabled
3. Ratsnest is disabled
4. Antialiasing is Fast or Disabled

**Hardware:**
- M1/M2/M3 Mac: 60-90 FPS expected
- Intel Mac with discrete GPU: 40-60 FPS
- Integrated GPU: 20-35 FPS

## Environment Variables

Debug settings (set before starting KiCad):

```bash
# Enable debug logging
export KIDOOM_DEBUG=1

# Log frame times
export KIDOOM_LOG_FRAMES=1

# Log socket communication
export KIDOOM_LOG_SOCKET=1

# Then start KiCad
kicad
```

## Technical Details

### Coordinate Systems

**DOOM:**
- Origin (0,0) at top-left
- X increases right (0-320)
- Y increases down (0-200)
- Units: pixels

**KiCad:**
- Origin (0,0) at board center
- X increases right
- Y increases UP (inverted)
- Units: nanometers

**Conversion:**
1. Center: `x_centered = doom_x - 160`
2. Flip Y: `y_flipped = -(doom_y - 100)`
3. Scale: `kicad_nm = centered * 500000`

### Entity Footprint Mappings

| Entity | Footprint | Package |
|--------|-----------|---------|
| Player | QFP-64 | 10x10mm |
| Imp | SOT-23 | Small demon |
| Baron | TO-220 | Large demon |
| Cacodemon | DIP-8 | Round-ish |

## License

See main project LICENSE file.

## Credits

- DOOM: id Software
- doomgeneric: @ozkl
- KiCad: KiCad Project
- Plugin: KiDoom Project

## Known Issues

1. **3D Viewer not supported** - Only 2D editor view works
2. **Global keyboard capture** - May interfere with other apps if KiCad loses focus
3. **macOS Accessibility permissions** - Required for pynput keyboard capture

## Future Enhancements

- [ ] Color via 4 copper layers
- [ ] Textured walls using filled zones
- [ ] Sound effects via Python
- [ ] Multiplayer on multiple PCBs
- [ ] Gerber export (fabricate each frame!)

---

**Project Status:** Phase 2 Complete - Python Plugin Implementation

For more details, see `/Users/tribune/Desktop/KiDoom/plan.md`
