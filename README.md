# KiDoom

Run DOOM inside KiCad's PCB editor using real PCB traces as the rendering medium. Wall segments become copper traces, entities become footprints, and projectiles become vias.

## Quick Start

### 1. Install Dependencies

```bash
# Python dependencies
pip3 install pygame  # For standalone renderer

# SDL2 (for dual-output mode)
brew install sdl2  # macOS
```

### 2. Build DOOM Engine

```bash
cd doom/source
./build.sh
```

This will:
- Clone doomgeneric if needed
- Build the DOOM binary
- Download shareware WAD file

### 3. Run

**Dual Mode (Recommended)** - Shows both SDL window and vectors:
```bash
./run_doom.sh dual -w 1 1  # Skip straight to E1M1
```

**Standalone Testing** - Test vectors without KiCad:
```bash
# Terminal 1
./run_standalone_renderer.py

# Terminal 2
./run_doom.sh vector -w 1 1
```

## Project Structure

```
KiDoom/
├── run_doom.sh                # Main entry point for DOOM
├── run_standalone_renderer.py # Entry point for vector renderer
├── CLAUDE.md                  # Claude Code instructions
├── README.md                  # This file
│
├── src/                       # Source code
│   └── standalone_renderer.py # Pygame vector renderer
│
├── kicad_doom_plugin/         # KiCad plugin
│   ├── __init__.py
│   ├── doom_plugin_action.py  # Main plugin
│   ├── pcb_renderer.py        # PCB rendering
│   ├── doom_bridge.py         # Socket communication
│   └── ...
│
├── doom/                      # DOOM engine
│   ├── doomgeneric_kicad      # Vector-only binary
│   ├── doomgeneric_kicad_dual # SDL + vectors binary
│   ├── doom1.wad              # Game data
│   └── source/                # C source code
│
├── tests/                     # Test scripts
├── scripts/                   # Utility scripts
└── logs/docs/                 # Development documentation
```

## How It Works

### Vector Extraction

Instead of scanning the pixel buffer (64,000 pixels), we extract vectors directly from DOOM's internal data structures:

- **Walls**: Read from `drawsegs[]` array - actual 3D-to-2D projected line segments
- **Entities**: Read from `vissprites[]` array - sprite positions and scales
- **Depth**: Calculated from DOOM's scale values (closer = larger scale)

This provides a ~200-500x performance improvement over pixel scanning.

### Dual Output Mode

The `doomgeneric_kicad_dual` binary:
1. Renders original DOOM graphics to SDL window (for reference)
2. Extracts vectors from internal arrays
3. Sends vectors via Unix socket to standalone renderer (or KiCad plugin)

Perfect for side-by-side comparison!

### PCB Rendering

When used with KiCad:
- Walls → `PCB_TRACK` objects on F.Cu/B.Cu
- Entities → `FOOTPRINT` objects (QFP-64, SOT-23, etc.)
- Projectiles → `PCB_VIA` objects
- HUD → `PCB_TEXT` on F.SilkS

## Development Timeline

See `logs/docs/` for chronological documentation showing:
1. Initial implementation and Phase 2/3 completion
2. macOS threading challenges and crash fixes (V1, V2, V3)
3. Isolation testing with smiley face plugin
4. Standalone renderer development
5. Direct vector extraction from DOOM internals

Each file is timestamped showing when it was created during development.

## Performance

- **Standalone Renderer**: 60+ FPS (pygame is fast)
- **KiCad Plugin**: 10-30 FPS (PCB operations are slower)
- **DOOM Engine**: ~35 FPS (game logic)

The bottleneck is KiCad's PCB refresh, not DOOM or the communication layer.

## Testing

**Smiley Face Test** (simple timer test):
```bash
export KIDOOM_TEST_MODE=true
open -a KiCad
# Then run plugin normally
```

**Standalone Renderer** (full pipeline without KiCad):
```bash
./run_standalone_renderer.py    # Terminal 1
./run_doom.sh vector -w 1 1     # Terminal 2
```

## Known Issues

### macOS Threading

KiCad plugins on macOS crash when modifying PCB objects from background threads. The current solution uses:
- Queue-based architecture (background thread → queue → main thread timer)
- All PCB operations on main thread only
- wx.Timer for scheduled updates

See `logs/docs/11_*_FINAL_FIX_V3.md` for details.

### Vector Extraction Quality

Current extraction reads `drawsegs[]` for walls and outputs them as vertical lines. This works but doesn't look exactly like DOOM yet. The architecture is sound - just needs refinement of the extraction algorithm.

## Controls

- **WASD** - Move (forward/back/strafe)
- **Arrow keys** - Turn left/right
- **Ctrl** - Fire weapon
- **Space / E** - Use / Open doors
- **1-7** - Select weapon
- **ESC** - Menu / Quit

## License

See LICENSE file.

DOOM engine: https://github.com/ozkl/doomgeneric

## Credits

- **id Software** - Original DOOM (1993)
- **ozkl** - doomgeneric framework
- **KiCad** - Open source PCB design software
