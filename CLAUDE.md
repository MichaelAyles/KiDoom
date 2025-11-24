# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

KiDoom is a technical demonstration that runs DOOM within KiCad's PCBnew using real PCB traces and footprints as the rendering medium. The project features a complete triple-mode rendering system: SDL window for gameplay, Python wireframe renderer for reference, and KiCad PCB traces for the technical demonstration.

**Key Innovation:** Instead of raster pixel rendering (64,000 pixels = unworkable), this uses vector rendering with PCB traces (100-300 line segments per frame) and real component footprints for entities, providing a 200-500x performance improvement.

**Entity Innovation:** Entities (enemies, items, decorations) are rendered as real PCB footprints with component complexity matching gameplay importance:
- **Collectibles** (health, ammo) → SOT-23 (3-pin small packages)
- **Decorations** (barrels, bodies) → SOIC-8 (8-pin flat packages)
- **Enemies** (zombies, demons) → QFP-64 (64-pin complex packages)

**Expected Performance:** 10-25 FPS in KiCad, 60+ FPS in standalone renderer

## Architecture

### Triple-Mode Rendering System

**Mode 1: SDL Window (Gameplay)**
- Full DOOM graphics for keyboard input and reference
- Standard SDL2 rendering
- Position: (0, 420) on screen (below Python renderer)

**Mode 2: Python Wireframe Renderer**
- Standalone pygame-based wireframe visualization
- Displays extracted vectors from DOOM engine
- Position: (0, 0) on screen

**Mode 3: KiCad PCB Rendering**
- Real PCB traces for walls
- Real component footprints for entities
- Electrically authentic design

All three modes receive identical vector data from DOOM via Unix socket.

### Core Components

**DOOM Engine (C):**
- Uses doomgeneric framework (designed for porting DOOM to new platforms)
- Dual-mode operation: SDL rendering + vector extraction
- Located in `doom/source/doomgeneric_kicad_dual_v2.c`
- Compiled binary: `doom/doomgeneric_kicad`
- Custom patches to vissprite_t for entity type extraction

**KiCad Plugin (Python):**
- Main entry point: `doom_plugin_action.py` (ActionPlugin with file logging)
- PCB renderer: `pcb_renderer.py` (wireframe edges + footprint placement)
- Communication bridge: `doom_bridge.py` (two-phase socket server)
- Entity types: `entity_types.py` (150+ DOOM entities categorized)
- Object pools: `object_pool.py` (pre-allocated PCB objects by category)
- Coordinate transform: `coordinate_transform.py` (DOOM pixels → KiCad nm with A4 centering)

### Communication Protocol

Binary protocol over Unix domain socket (`/tmp/kicad_doom.sock`):
```
[4 bytes: message type][4 bytes: payload length][N bytes: JSON payload]
```

Message types:
- 0x01: FRAME_DATA (DOOM → Python)
- 0x02: KEY_EVENT (Python → DOOM)
- 0x03: INIT_COMPLETE (Python → DOOM)
- 0x04: SHUTDOWN (bidirectional)

### PCB Element Mapping

| DOOM Element | PCB Element | Specification | Visual Meaning |
|-------------|-------------|---------------|----------------|
| Wall segments | `PCB_TRACK` (wireframe) | F.Cu/B.Cu, width encodes distance | Blue traces, thick=close |
| Collectibles | `FOOTPRINT` (SOT-23) | 3-pin small package | Health, ammo, keys |
| Decorations | `FOOTPRINT` (SOIC-8) | 8-pin flat package | Barrels, bodies, props |
| Enemies | `FOOTPRINT` (QFP-64) | 64-pin complex package | Zombies, demons, player |
| Projectiles | `PCB_VIA` | Drilled holes | Bullets, fireballs |
| HUD elements | `PCB_TEXT` | F.SilkS silkscreen | Health, ammo counters |

**Wall Rendering:** Wireframe edges (4 traces per wall: top, bottom, left, right)
- All walls use B.Cu (blue) layer
- Distance encoded as trace width (thick = close, thin = far)

**Entity Rendering:** Real PCB footprints based on DOOM entity type (MT_* enum)
- Type extracted from vissprite_t.mobjtype (custom DOOM patch)
- Categorized by gameplay significance
- Pre-loaded from KiCad standard libraries

## Development Commands

### Building DOOM Engine

```bash
# Automated build (recommended)
cd doom/source
./build.sh

# Manual build
git clone https://github.com/ozkl/doomgeneric.git
cd doomgeneric/doomgeneric

# Apply KiDoom patches to doomgeneric source
# Patch 1: Add mobjtype field to vissprite_t structure
sed -i '' '/lighttable_t.*colormap;/a\
\
    // KiDoom: Store entity type for footprint selection\
    int			mobjtype;\
' r_defs.h

# Patch 2: Capture entity type during vissprite creation
sed -i '' '/vis->mobjflags = thing->flags;/a\
    vis->mobjtype = thing->type;  // KiDoom: Capture entity type\
' r_things.c

# Copy platform files
cp /path/to/KiDoom/doom/source/doomgeneric_kicad_dual_v2.c .
cp /path/to/KiDoom/doom/source/doom_socket.c .
cp /path/to/KiDoom/doom/source/doom_socket.h .
cp /path/to/KiDoom/doom/source/Makefile.kicad_dual .

# Build
make -f Makefile.kicad_dual

# Copy binary and WAD back to plugin
cp doomgeneric_kicad_dual /path/to/KiDoom/doom/doomgeneric_kicad
cp doom1.wad /path/to/KiDoom/doom/
```

### Running Tests

**Standalone Renderer Test:**
```bash
# Terminal 1: Start Python wireframe renderer
./run_standalone_renderer.py

# Terminal 2: Launch DOOM
./run_doom.sh dual -w 1 1  # E1M1 with both SDL + vectors
```

**KiCad Plugin Test:**
```bash
# In KiCad:
# 1. Tools → External Plugins → Open Plugin Directory
# 2. Create symlink: ln -s /path/to/KiDoom/kicad_doom_plugin ~/.kicad/scripting/plugins/
# 3. Open PCBnew
# 4. Tools → External Plugins → KiDoom - DOOM on PCB
```

### Installing Plugin

```bash
# Find KiCad plugin directory
# In KiCad: Tools → External Plugins → Open Plugin Directory

# Create symlink (recommended) or copy plugin
ln -s /path/to/KiDoom/kicad_doom_plugin ~/.kicad/scripting/plugins/kidoom
```

### Running DOOM in KiCad

1. Open KiCad PCBnew
2. Create/open a PCB (A4 landscape page recommended)
3. Tools → External Plugins → KiDoom - DOOM on PCB (Enhanced)
4. Wait for three windows:
   - SDL window (gameplay with keyboard input)
   - Python wireframe renderer (reference view)
   - KiCad PCB (trace/footprint rendering)
5. Controls: WASD (move), Arrow keys (turn), Ctrl (shoot), ESC (quit)
6. To exit: Close Python renderer window or ESC in SDL window

## Critical Implementation Details

### Two-Phase Socket Setup (CRITICAL)

DOOM launches faster than Python can create the socket. Solution:

```python
# Phase 1: Setup socket BEFORE launching DOOM
bridge.setup_socket()  # Creates /tmp/kicad_doom.sock and starts listening

# Phase 2: Launch DOOM process
processes = launch_doom_processes()

# Phase 3: Accept connection from DOOM
bridge.accept_connection()  # Blocks until DOOM connects
```

**Wrong approach (causes "Connection refused"):**
```python
processes = launch_doom_processes()  # DOOM tries to connect immediately
bridge.start()  # Too late! Socket doesn't exist yet
```

### Thread Safety with wx Objects (CRITICAL)

wx.Timer and PCB objects can ONLY be modified from main thread on macOS.

**Safe pattern:**
```python
# Monitor thread (daemon)
def _monitor_processes(doom_process, python_renderer):
    while doom_process.poll() is None:
        time.sleep(1)
    # Clean up ONLY thread-safe objects
    doom_process.terminate()
    python_renderer.terminate()
    bridge.stop()  # Socket cleanup is safe
    # DO NOT: renderer.stop_refresh_timer()  # wx.Timer NOT thread-safe!
```

### Coordinate System Transformations

**Units:**
- KiCad: nanometers (nm)
- DOOM: pixels (320×200 screen)
- Conversion: 1 DOOM pixel = 0.5mm = 500,000nm

**Coordinate systems (CORRECTED):**
- DOOM: (0,0) top-left, Y increases downward
- KiCad: (0,0) at origin, Y increases downward ON SCREEN (same as DOOM)
- A4 landscape center: (148.5mm, 105mm) = (148,500,000nm, 105,000,000nm)

**Implementation:**
```python
# Center on DOOM screen
x_centered = doom_x - (DOOM_WIDTH / 2)
y_centered = doom_y - (DOOM_HEIGHT / 2)

# No Y-axis flip needed (both increase downward on screen)
kicad_x = int(x_centered * SCALE)
kicad_y = int(y_centered * SCALE)

# Offset to center on A4 page
kicad_x += 148_500_000  # A4 landscape center X
kicad_y += 105_000_000  # A4 landscape center Y
```

**Always use:**
```python
kicad_x, kicad_y = CoordinateTransform.doom_to_kicad(doom_x, doom_y)
```

### Entity Type Extraction System

**Problem:** vissprite_t has no direct mobj pointer

**Solution:** Patch DOOM source to capture entity type during vissprite creation

**DOOM Source Patches:**
```c
// r_defs.h - Add field to vissprite_t
typedef struct vissprite_s {
    // ... existing fields ...
    lighttable_t* colormap;
    int mobjtype;     // ← NEW: MT_PLAYER, MT_SHOTGUY, etc.
    int mobjflags;
} vissprite_t;

// r_things.c - Capture during R_ProjectSprite()
void R_ProjectSprite(mobj_t* thing) {
    vis = R_NewVisSprite();
    vis->mobjflags = thing->flags;
    vis->mobjtype = thing->type;  // ← NEW: Capture entity type
    // ... rest of setup ...
}
```

**Vector Extraction:**
```c
// doomgeneric_kicad_dual_v2.c
for (int i = 0; i < sprite_count; i++) {
    vissprite_t* vis = &vissprites[i];
    int type = vis->mobjtype;  // Real MT_* enum value!

    snprintf(json_buf + offset, sizeof(json_buf) - offset,
        "{\"x\":%d,\"y_top\":%d,\"y_bottom\":%d,\"type\":%d,...}",
        x, y_top, y_bottom, type, ...);
}
```

**Python Categorization:**
```python
# entity_types.py
ENTITY_CATEGORIES = {
    MT_PLAYER: CATEGORY_ENEMY,      # QFP-64
    MT_SHOTGUY: CATEGORY_ENEMY,     # QFP-64
    MT_BARREL: CATEGORY_DECORATION, # SOIC-8
    MT_MISC11: CATEGORY_COLLECTIBLE,# SOT-23 (medikit)
    # ... 150+ entity mappings
}

def get_footprint_category(mobj_type):
    return ENTITY_CATEGORIES.get(mobj_type, CATEGORY_UNKNOWN)
```

### Footprint Pool by Category

```python
FOOTPRINT_SPECS = {
    CATEGORY_COLLECTIBLE: ("Package_TO_SOT_SMD", "SOT-23", "3-pin small"),
    CATEGORY_DECORATION: ("Package_SO", "SOIC-8_3.9x4.9mm_P1.27mm", "8-pin flat"),
    CATEGORY_ENEMY: ("Package_QFP", "LQFP-64_10x10mm_P0.5mm", "64-pin complex"),
}

# Pre-allocation by expected frequency
instances_per_category = {
    CATEGORY_COLLECTIBLE: max_size // 3,   # 33% - Items common
    CATEGORY_DECORATION: max_size // 6,    # 17% - Decorations occasional
    CATEGORY_ENEMY: max_size // 2,         # 50% - Enemies dominant
}
```

### Wireframe Wall Rendering

Each wall becomes 4 PCB_TRACK edges:
```python
edges = [
    (x_left, y_top, x_right, y_top),      # Top edge
    (x_left, y_bottom, x_right, y_bottom), # Bottom edge
    (x_left, y_top, x_left, y_bottom),    # Left edge
    (x_right, y_top, x_right, y_bottom)   # Right edge
]

for (sx, sy, ex, ey) in edges:
    trace = trace_pool.get(index)
    trace.SetStart(pcbnew.VECTOR2I(kicad_sx, kicad_sy))
    trace.SetEnd(pcbnew.VECTOR2I(kicad_ex, kicad_ey))
    trace.SetLayer(pcbnew.B_Cu)  # Always blue
    trace.SetWidth(width_based_on_distance)  # Thick = close, thin = far
```

## KiCad API Usage Patterns

### Essential API Calls

**Creating traces (wall edges):**
```python
track = pcbnew.PCB_TRACK(board)
track.SetStart(pcbnew.VECTOR2I(x1_nm, y1_nm))
track.SetEnd(pcbnew.VECTOR2I(x2_nm, y2_nm))
track.SetWidth(300000)  # 0.3mm for close walls
track.SetLayer(pcbnew.B_Cu)  # Blue layer
track.SetNet(doom_net)
board.Add(track)
```

**Placing footprints (entities):**
```python
# Load from KiCad library
lib_path = get_footprint_library_path()
fp = pcbnew.FootprintLoad(f"{lib_path}/Package_QFP.pretty", "LQFP-64_10x10mm_P0.5mm")

# Configure
fp.SetReference("ENEMY1")
fp.SetValue("Shotgun Guy")
fp.SetPosition(pcbnew.VECTOR2I(x_nm, y_nm))
board.Add(fp)
```

**Creating vias (projectiles):**
```python
via = pcbnew.PCB_VIA(board)
via.SetPosition(pcbnew.VECTOR2I(x_nm, y_nm))
via.SetDrill(400000)  # 0.4mm drill
via.SetWidth(600000)  # 0.6mm pad
via.SetNet(doom_net)
board.Add(via)
```

**Refreshing display:**
```python
pcbnew.Refresh()  # Blocks until frame rendered (main thread only!)
```

### Common API Gotchas

1. **Units are nanometers:** `track.SetWidth(200000)` not `0.2` (200,000nm = 0.2mm)
2. **Y-axis coordinate system:** Both DOOM and KiCad screen display have Y increasing downward
3. **Thread safety:** wx.Timer and PCB objects only from main thread on macOS
4. **Socket timing:** Create socket BEFORE launching DOOM process
5. **Object lifetime:** Keep Python references to prevent GC crashes
6. **Footprint paths:** OS-specific, use `get_footprint_library_path()` helper
7. **Refresh() blocks:** Synchronous call that freezes execution until rendering complete

## Object Pool Pattern (Critical for Performance)

**Why:** Creating/destroying PCB objects every frame is prohibitively slow (50-100ms overhead). Object pools provide 3-5x speedup.

**Pattern:**
```python
class TracePool:
    def __init__(self, board, max_size=500):
        self.traces = []
        # Pre-allocate all traces at initialization
        for i in range(max_size):
            track = pcbnew.PCB_TRACK(board)
            board.Add(track)
            self.traces.append(track)

    def get(self, index):
        return self.traces[index]  # Reuse existing object

    def hide_unused(self, used_count):
        # Set width to 0 or move off-screen instead of deleting
        for i in range(used_count, len(self.traces)):
            self.traces[i].SetWidth(0)
```

**Apply to:** Traces, footprints (by category), vias, text objects

## Performance Optimizations

### Manual KiCad Settings (REQUIRED)

1. **View → Show Grid:** OFF (saves 5-10% per frame)
2. **View → Ratsnest:** OFF (saves 20-30% per frame)
3. **Preferences → PCB Editor → Display Options:**
   - Clearance outlines: OFF
   - Pad/Via holes: Do not show
4. **Preferences → Common → Graphics:**
   - Antialiasing: Fast or Disabled (saves 5-15%)
   - Rendering engine: Accelerated

### Code-Level Optimizations (automatic)

- **Object pooling:** Pre-allocate all PCB objects at startup, reuse by updating positions
- **Single shared net:** All DOOM geometry on one net to eliminate ratsnest calculation
- **Minimal layers:** Only F.Cu and B.Cu enabled for walls
- **Object hiding:** Move unused objects off-screen rather than destroying them
- **No DRC:** Design rule checking disabled during gameplay
- **Footprint pre-loading:** All categories loaded at startup (10-50ms per footprint)

## File Structure Reference

```
kicad_doom_plugin/
├── doom_plugin_action.py     # Main ActionPlugin (enhanced with logging, two-phase socket)
├── pcb_renderer.py            # Wireframe walls + footprint entities
├── doom_bridge.py             # Unix socket server (two-phase: setup/accept)
├── entity_types.py            # NEW: 150+ entity categorization (MT_* → CATEGORY_*)
├── coordinate_transform.py    # DOOM ↔ KiCad conversion (A4 centered, no Y-flip)
├── object_pool.py             # Pre-allocated PCB objects by category
├── config.py                  # Constants (scale factors, pool sizes, footprints)
├── doom/
│   ├── doomgeneric_kicad     # Compiled DOOM binary (dual-mode, patched)
│   ├── doom1.wad             # Game data (shareware)
│   └── source/
│       ├── doomgeneric_kicad_dual_v2.c  # Main platform implementation
│       ├── doom_socket.c        # Socket client
│       └── patches/
│           └── vissprite_mobjtype.patch  # Reference patch for doomgeneric
└── logs/docs/
    ├── 23_*_KICAD_PLUGIN_INTEGRATION.md      # Triple-mode setup
    └── 24_*_FOOTPRINT_ENTITIES_COMPLETE.md   # Entity type extraction

src/
└── standalone_renderer.py    # Pygame wireframe renderer (testing/reference)

doom/source/
├── build.sh                  # Automated build script
├── doomgeneric_kicad.c       # Entity type extraction code
├── doomgeneric_kicad_dual_v2.c  # Active dual-mode implementation
├── doom_socket.c             # Socket communication
├── doom_socket.h
└── Makefile.kicad_dual       # Build configuration
```

## Entity Type Reference

### Sample Mappings (150+ total)

| Entity | MT_* Type | Category | Footprint | Purpose |
|--------|-----------|----------|-----------|---------|
| Player | 0 | ENEMY | QFP-64 | Player character |
| Shotgun Guy | 2 | ENEMY | QFP-64 | Common enemy |
| Imp | 11 | ENEMY | QFP-64 | Flying enemy |
| Cyberdemon | 21 | ENEMY | QFP-64 | Boss |
| Medikit | 38 | COLLECTIBLE | SOT-23 | +25 health |
| Ammo Clip | 52 | COLLECTIBLE | SOT-23 | Bullets |
| Blue Keycard | 46 | COLLECTIBLE | SOT-23 | Key item |
| Exploding Barrel | 68 | DECORATION | SOIC-8 | Interactive |
| Dead Player | 95 | DECORATION | SOIC-8 | Decoration |
| Torch | 88 | DECORATION | SOIC-8 | Lighting |

## Performance Expectations

**Target:** 10-25 FPS in KiCad depending on hardware
- M1 MacBook Pro: 15-25 FPS
- Dell XPS (i7 12th gen, RTX 3050 Ti): 18-28 FPS
- Older hardware (i5, integrated GPU): 8-15 FPS

**Standalone Renderer:** 60+ FPS (pygame is fast)

**Visual style:** Wireframe vector rendering with real PCB components

## Known Issues & Solutions

### Socket Timing (SOLVED)
**Problem:** DOOM connects before socket exists
**Solution:** Two-phase setup (setup_socket → launch → accept_connection)

### Thread Safety (SOLVED)
**Problem:** wx.Timer crashes from background thread
**Solution:** Only clean up processes/sockets from monitor thread, leave wx objects

### Y-Axis Coordinate (SOLVED)
**Problem:** Rendering appeared upside-down
**Solution:** No Y-flip needed - both DOOM and KiCad screen have Y downward

### Entity Type Extraction (SOLVED)
**Problem:** vissprite_t has no mobj pointer
**Solution:** Patch vissprite_t to add mobjtype field, capture in R_ProjectSprite()

### Color Confusion (SOLVED)
**Problem:** Close walls (red) looked like entities (red)
**Solution:** All walls blue (B.Cu), distance as width only

## Dependencies

**Python:**
- pygame (standalone renderer)
- pynput (OS-level keyboard capture, optional)

**C:**
- GCC/Clang
- SDL2 (for dual-mode output)
- Standard C library (socket, unistd)

**KiCad:**
- Version 7 or 8 (Python API support)
- Python scripting enabled
- Standard footprint libraries (Package_QFP, Package_SO, Package_TO_SOT_SMD)

## Testing & Validation

1. **Standalone renderer:** Verify vector extraction works
2. **KiCad plugin:** Test triple-mode rendering
3. **Entity categories:** Verify footprint types match entity classes
4. **Coordinate transform:** Check A4 centering and orientation
5. **Thread safety:** Ensure clean shutdown without KiCad crash

## Electrical Authenticity

This is a legitimate PCB design using real electrical elements:
- `PCB_TRACK` (copper traces, not drawings)
- `PCB_VIA` (drilled holes)
- `FOOTPRINT` (real components: SOT-23, SOIC-8, QFP-64)
- All elements connected to net `DOOM_WORLD`
- Could theoretically be fabricated (though non-functional)

Component selection has semantic meaning:
- Package complexity = Gameplay importance
- Pin count = Threat level / Value
- Industry-standard packages (recognizable to any PCB designer)
