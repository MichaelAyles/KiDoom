<p align="center">
  <img src="assets/logo_transparent.png" alt="KiDoom Logo" width="400">
</p>

Run DOOM inside KiCad's PCB editor using real PCB traces and component footprints as the rendering medium. Features triple-mode rendering: SDL window, Python wireframe renderer, and KiCad PCB visualization.

<p align="center">
  <img src="assets/kidoom-demo.gif" alt="KiDoom Demo - DOOM running in KiCad" width="800">
</p>


## Features

🎮 **Triple-Mode Rendering**
- SDL window for standard gameplay
- Python wireframe renderer for reference visualization
- KiCad PCB traces and footprints for technical demonstration

🔧 **Real PCB Components**
- Walls rendered as copper traces (wireframe edges)
- Entities rendered as actual PCB footprints:
  - **SOT-23** (3-pin) for collectibles (health, ammo, keys)
  - **SOIC-8** (8-pin) for decorations (barrels, bodies, props)
  - **QFP-64** (64-pin) for enemies (zombies, demons, player)

⚡ **Performance Optimized**
- Vector extraction (200-500x faster than pixel rendering)
- Object pooling (pre-allocated PCB elements)
- 10-25 FPS in KiCad, 60+ FPS in standalone renderer

🎯 **Electrically Authentic**
- Real copper traces on F.Cu/B.Cu layers
- Industry-standard component packages
- Connected to shared net (could be fabricated!)

## Quick Start

### 1. Install Dependencies

```bash
# Python dependencies
pip3 install pygame  # For standalone renderer

# SDL2 (for dual-output mode)
brew install sdl2  # macOS
sudo apt install libsdl2-dev  # Linux
```

### 2. Build DOOM Engine

```bash
cd doom/source
./build.sh
```

This will:
- Clone doomgeneric if needed
- Apply KiDoom patches (entity type extraction)
- Build the DOOM binary
- Download shareware WAD file

### 3. Run Standalone (Testing)

```bash
# Terminal 1: Start Python wireframe renderer
./run_standalone_renderer.py

# Terminal 2: Launch DOOM with vectors
./run_doom.sh dual -w 1 1  # E1M1 with SDL + vectors
```

You'll see:
- SDL window (top-left) - Full DOOM graphics for gameplay
- Python window (top-right) - Wireframe visualization

### 4. Run in KiCad (Full Experience)

```bash
# Install plugin
ln -s $(pwd)/kicad_doom_plugin ~/.kicad/scripting/plugins/kidoom
```

Then in KiCad:
1. Open PCBnew
2. Create/open a PCB (A4 landscape recommended)
3. **Tools → External Plugins → KiDoom - DOOM on PCB**

Watch as DOOM appears on your PCB with:
- Blue copper traces for walls (thickness = depth)
- Real component footprints for entities
- Vias for projectiles

## How It Works

### Vector Extraction

Instead of scanning 64,000 pixels, we extract vectors directly from DOOM's internal arrays:

```c
// Extract from DOOM's rendering pipeline
drawsegs[]     → Wall segments (already 3D-projected!)
vissprites[]   → Entity positions with scale
vissprite.mobjtype → Real entity type (MT_SHOTGUY, MT_BARREL, etc.)
```

**Performance:** 200-500x faster than pixel buffer scanning

### Entity Type System

Custom DOOM patches extract real entity types:

```c
// Patch to r_defs.h
typedef struct vissprite_s {
    lighttable_t* colormap;
    int mobjtype;     // NEW: Captures MT_* enum during R_ProjectSprite()
    int mobjflags;
} vissprite_t;
```

Python categorizes 150+ entity types:

```python
MT_PLAYER → CATEGORY_ENEMY → QFP-64 footprint
MT_MISC11 → CATEGORY_COLLECTIBLE → SOT-23 footprint (medikit)
MT_BARREL → CATEGORY_DECORATION → SOIC-8 footprint
```

### PCB Rendering

| DOOM Element | PCB Element | Example |
|--------------|-------------|---------|
| Wall | 4x PCB_TRACK (wireframe box) | Blue traces, thick=close |
| Enemy | FOOTPRINT (QFP-64) | Shotgun Guy, Cyberdemon |
| Collectible | FOOTPRINT (SOT-23) | Health pack, ammo clip |
| Decoration | FOOTPRINT (SOIC-8) | Barrel, dead body |
| Projectile | PCB_VIA | Bullet, fireball |
| HUD | PCB_TEXT | Health/ammo counters |

## Project Structure

```
KiDoom/
├── run_doom.sh                # Main DOOM launcher
├── run_standalone_renderer.py # Wireframe renderer launcher
├── CLAUDE.md                  # AI assistant instructions
├── README.md                  # This file
│
├── kicad_doom_plugin/         # KiCad plugin (install to ~/.kicad/)
│   ├── doom_plugin_action.py  # Main plugin entry point
│   ├── pcb_renderer.py        # Wireframe + footprint rendering
│   ├── entity_types.py        # 150+ entity categorization
│   ├── doom_bridge.py         # Socket communication
│   ├── object_pool.py         # Pre-allocated PCB objects
│   └── coordinate_transform.py # DOOM pixels → KiCad nanometers
│
├── doom/                      # DOOM engine
│   ├── doomgeneric_kicad      # Compiled binary (dual-mode)
│   ├── doom1.wad              # Shareware game data
│   └── source/
│       ├── doomgeneric_kicad_dual_v2.c  # Vector extraction
│       ├── doom_socket.c      # Socket client
│       └── build.sh           # Automated build
│
├── src/
│   └── standalone_renderer.py # Pygame wireframe renderer
│
└── logs/docs/                 # Development documentation
    ├── 22_*_KICAD_WIREFRAME_PLAN.md
    ├── 23_*_KICAD_PLUGIN_INTEGRATION.md
    └── 24_*_FOOTPRINT_ENTITIES_COMPLETE.md
```

## Controls

- **WASD** - Move (forward/back/strafe)
- **Arrow keys** - Turn left/right
- **Ctrl** - Fire weapon
- **Space / E** - Use / Open doors
- **1-7** - Select weapon
- **ESC** - Menu / Quit

## Performance

| Environment | FPS | Notes |
|-------------|-----|-------|
| Standalone Renderer | 60+ | pygame is very fast |
| KiCad (M1 MacBook Pro) | 15-25 | PCB refresh overhead |
| KiCad (i7 + RTX 3050 Ti) | 18-28 | GPU-accelerated |
| KiCad (older hardware) | 8-15 | Still playable! |

**Bottleneck:** KiCad's PCB refresh, not DOOM or communication

## KiCad Optimization (Required)

For best performance in KiCad, disable these before running:

1. **View → Show Grid:** OFF (saves 5-10%)
2. **View → Ratsnest:** OFF (saves 20-30%)
3. **Preferences → PCB Editor → Display Options:**
   - Clearance outlines: OFF
   - Pad/Via holes: Do not show
4. **Preferences → Common → Graphics:**
   - Antialiasing: Fast or Disabled
   - Rendering engine: Accelerated

## Technical Highlights

### DOOM Source Patches

Custom patches to `doomgeneric` source capture entity types:

```c
// r_defs.h - Add mobjtype field
int mobjtype;  // Stores MT_PLAYER, MT_SHOTGUY, etc.

// r_things.c - Capture during sprite projection
vis->mobjtype = thing->type;
```

See `doom/source/patches/vissprite_mobjtype.patch` for details.

### Thread-Safe Architecture

KiCad crashes when modifying PCB objects from background threads on macOS.

**Solution:**
- Socket server and DOOM run in background
- Monitor thread watches process health
- All PCB operations on main thread via wx.Timer
- Clean shutdown without KiCad crash

### Coordinate System

- **DOOM:** 320×200 pixels, (0,0) top-left, Y down
- **KiCad:** nanometers, Y down on screen (same direction!)
- **Scaling:** 1 DOOM pixel = 0.5mm = 500,000 nm
- **Centering:** A4 landscape center (148.5mm, 105mm)

No Y-axis flip needed - both systems use screen-space coordinates.

## Development Timeline

See `logs/docs/` for chronological documentation:

1. **Phase 1-5:** Initial implementation (socket, renderer, plugin)
2. **macOS Threading:** Crash fixes (V1, V2, V3 iterations)
3. **Standalone Renderer:** Pygame wireframe visualization
4. **Vector Extraction:** Direct access to DOOM internals
5. **Wireframe Rendering:** Edge-based wall rendering
6. **Triple-Mode Integration:** SDL + Python + KiCad
7. **Entity Type Extraction:** DOOM source patches for real types
8. **Footprint System:** Category-based component rendering

## Testing

**Standalone Renderer Test:**
```bash
./run_standalone_renderer.py    # Terminal 1
./run_doom.sh dual -w 1 1        # Terminal 2
```

**KiCad Smiley Test:**
```bash
export KIDOOM_TEST_MODE=true
# Then run plugin in KiCad
```

**Full Integration:**
```bash
# Install plugin, open KiCad PCBnew
# Tools → External Plugins → KiDoom
```

## Known Limitations

1. **KiCad Performance:** PCB refresh is inherently slow (10-25 FPS)
2. **macOS Threading:** wx.Timer must stay on main thread
3. **Footprint Loading:** Initial load ~10-50ms per footprint type
4. **Socket Timing:** Must create socket before launching DOOM

All major issues have been solved. See `CLAUDE.md` for technical details.

## Architecture

```
┌─────────────┐                 ┌──────────────┐
│ DOOM Engine │  Unix Socket    │ KiCad Plugin │
│   (C/SDL)   │ ─────────────→  │   (Python)   │
│             │  JSON Vectors   │              │
└─────────────┘                 └──────────────┘
      │                                 │
      ├─ SDL Window (gameplay)          ├─ PCB Traces (walls)
      ├─ Vector Extraction              ├─ Footprints (entities)
      └─ Entity Types (MT_*)            └─ Vias (projectiles)
              │
              ↓
      ┌──────────────────┐
      │ Python Renderer  │
      │   (Pygame/Ref)   │
      └──────────────────┘
```

## Entity Examples

| Entity | Type | Category | PCB Component | Visual |
|--------|------|----------|---------------|--------|
| Player | MT_PLAYER (0) | Enemy | LQFP-64 | 64-pin complex IC |
| Shotgun Guy | MT_SHOTGUY (2) | Enemy | LQFP-64 | 64-pin complex IC |
| Imp | MT_TROOP (11) | Enemy | LQFP-64 | 64-pin complex IC |
| Medikit | MT_MISC11 (38) | Collectible | SOT-23 | 3-pin small package |
| Ammo Clip | MT_CLIP (52) | Collectible | SOT-23 | 3-pin small package |
| Barrel | MT_BARREL (68) | Decoration | SOIC-8 | 8-pin flat package |
| Dead Body | MT_MISC53 (95) | Decoration | SOIC-8 | 8-pin flat package |

**Visual Hierarchy:** Package complexity = Gameplay importance! 🎯

## Dependencies

**Python:**
- pygame (standalone renderer)
- pynput (optional, keyboard capture)

**C/Build:**
- GCC or Clang
- SDL2 development libraries
- make, pkg-config

**KiCad:**
- KiCad 7 or 8 (Python scripting support)
- Standard footprint libraries included

## License

See LICENSE file.

**DOOM Engine:** Based on [doomgeneric](https://github.com/ozkl/doomgeneric) by ozkl
**Original DOOM:** id Software (1993)
**KiCad:** Open source PCB design software

## Related Projects

**[ScopeDoom](https://github.com/MichaelAyles/ScopeDoom)** - DOOM rendered on an oscilloscope in XY mode, inspired by KiDoom's vector extraction approach. Some original development code remains in this repo under `scopedoom/`.

## Credits

- **id Software** - Original DOOM (1993)
- **ozkl** - doomgeneric framework
- **KiCad Project** - Open source PCB design tools
- **Community** - Testing and feedback

## Highlights

✨ **First DOOM port using real PCB components as the rendering medium**
🏆 **Entity system with semantic component selection**
🎨 **Triple-mode rendering for different use cases**
⚡ **Vector extraction 200-500x faster than pixel scanning**
🔧 **Electrically authentic PCB design (could be fabricated!)**

---

**Status:** Fully working with triple-mode rendering and footprint-based entities!

For technical details and development guidance, see [CLAUDE.md](CLAUDE.md).
