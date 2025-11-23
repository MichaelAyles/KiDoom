# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

KiDoom is a technical demonstration that runs DOOM within KiCad's PCBnew using real PCB traces as the rendering medium. The project uses vector-based rendering where PCB traces represent wall segments, footprints represent entities (player/enemies), and vias represent projectiles.

**Key Innovation:** Instead of raster pixel rendering (64,000 pixels = unworkable), this uses vector rendering with PCB traces (100-300 line segments per frame), providing a 200-500x performance improvement.

**Expected Performance:** 10-25 FPS (playable for a tech demo)

## Architecture

### Core Components

**DOOM Engine (C):**
- Uses doomgeneric framework (designed for porting DOOM to new platforms)
- Runs as separate process communicating via Unix domain socket
- Located in `doom/source/doomgeneric_kicad.c`
- Compiled binary: `doom/doomgeneric_kicad`

**KiCad Plugin (Python):**
- Main entry point: `doom_plugin_action.py` (ActionPlugin)
- PCB renderer: `pcb_renderer.py` (converts DOOM vectors to PCB traces)
- Communication bridge: `doom_bridge.py` (socket server)
- Input handling: `input_handler.py` (OS-level keyboard capture via pynput)
- Object pools: `object_pool.py` (pre-allocated PCB objects for performance)

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

| DOOM Element | PCB Element | Layer | Electrical Property |
|-------------|-------------|-------|-------------------|
| Wall segments | `PCB_TRACK` | F.Cu/B.Cu | Real copper traces |
| Player | `FOOTPRINT` (QFP-64) | F.Cu | Component U1 |
| Enemies | `FOOTPRINT` (SOT-23, TO-220, DIP-8) | F.Cu | Various components |
| Projectiles | `PCB_VIA` | All layers | Drilled holes |
| HUD elements | `PCB_TEXT` | F.SilkS | Silkscreen text |

## Development Commands

### Building DOOM Engine

```bash
# Clone doomgeneric
git clone https://github.com/ozkl/doomgeneric.git
cd doomgeneric/doomgeneric

# Copy platform files
cp /path/to/KiDoom/doom/source/doomgeneric_kicad.c .
cp /path/to/KiDoom/doom/source/doom_socket.c .
cp /path/to/KiDoom/doom/source/Makefile.kicad .

# Build
make -f Makefile.kicad

# Copy binary and WAD back to plugin
cp doomgeneric_kicad /path/to/KiDoom/doom/
cp doom1.wad /path/to/KiDoom/doom/
```

### Running Benchmarks

**Phase 0 - Refresh benchmark (CRITICAL - run first):**
```python
# In KiCad Python console or as plugin
import pcbnew
exec(open('tests/benchmark_refresh.py').read())
```
Success criteria: < 50ms per frame (20+ FPS)

**Object pool performance test:**
```python
exec(open('tests/benchmark_object_pool.py').read())
```
Expected: 3-5x speedup vs create/destroy

**Socket communication latency:**
```bash
python tests/benchmark_socket.py
```
Expected: < 5ms overhead per frame

### Installing Plugin

```bash
# Find KiCad plugin directory
# In KiCad: Tools → External Plugins → Open Plugin Directory

# Create symlink or copy plugin
ln -s /path/to/KiDoom/kicad_doom_plugin ~/.kicad/scripting/plugins/
```

### Running DOOM in KiCad

1. Open KiCad PCBnew
2. Create/open a PCB (200mm × 200mm recommended)
3. Tools → External Plugins → DOOM on PCB
4. Wait for DOOM to launch and connect
5. Controls: WASD (move), Arrow keys (turn), Ctrl (shoot), ESC (quit)

## Critical Performance Optimizations

### Manual KiCad Settings (REQUIRED before running)

These must be configured manually in KiCad UI:

1. **View → Show Grid:** OFF (saves 5-10% per frame)
2. **View → Ratsnest:** OFF (saves 20-30% per frame)
3. **Preferences → PCB Editor → Display Options:**
   - Clearance outlines: OFF
   - Pad/Via holes: Do not show
4. **Preferences → Common → Graphics:**
   - Antialiasing: Fast or Disabled (saves 5-15%)
   - Rendering engine: Accelerated

### Code-Level Optimizations (automatic)

- **Object pooling:** Pre-allocate all PCB objects at startup, reuse by updating positions (3-5x speedup)
- **Single shared net:** All DOOM geometry on one net to eliminate ratsnest calculation
- **Minimal layers:** Only F.Cu and B.Cu enabled
- **Object hiding:** Move unused objects off-screen rather than destroying them
- **No DRC:** Design rule checking disabled during gameplay

### Coordinate System Transformations

**Units:**
- KiCad: nanometers (nm)
- DOOM: pixels (320×200 screen)
- Conversion: 1 DOOM pixel = 0.5mm = 500,000nm

**Coordinate systems:**
- DOOM: (0,0) top-left, Y increases downward
- KiCad: (0,0) at origin, Y increases upward
- Transformation handled by `CoordinateTransform` class in `coordinate_transform.py`

**Always use:**
```python
kicad_x, kicad_y = CoordinateTransform.doom_to_kicad(doom_x, doom_y)
```

## KiCad API Usage Patterns

### Essential API Calls

**Creating traces (walls):**
```python
track = pcbnew.PCB_TRACK(board)
track.SetStart(pcbnew.VECTOR2I(x1_nm, y1_nm))
track.SetEnd(pcbnew.VECTOR2I(x2_nm, y2_nm))
track.SetWidth(200000)  # 0.2mm in nanometers
track.SetLayer(pcbnew.F_Cu)
track.SetNet(doom_net)
board.Add(track)
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

**Loading footprints (entities):**
```python
lib_path = get_footprint_library_path()  # OS-specific
fp = pcbnew.FootprintLoad(f"{lib_path}/Package_QFP.pretty", "QFP-64_10x10mm_P0.5mm")
fp.SetReference("U1")
fp.SetPosition(pcbnew.VECTOR2I(x_nm, y_nm))
fp.SetOrientation(pcbnew.EDA_ANGLE(angle_deg, pcbnew.DEGREES_T))
board.Add(fp)
```

**Refreshing display:**
```python
pcbnew.Refresh()  # Blocks until frame rendered
```

### Common API Gotchas

1. **Units are nanometers:** `track.SetWidth(200000)` not `0.2` (200,000nm = 0.2mm)
2. **Y-axis inversion:** KiCad Y increases upward, DOOM Y increases downward
3. **Version differences:** KiCad 6+ uses `VECTOR2I`, KiCad 5 uses `wxPoint` (use `kicad_compat.py`)
4. **Angles:** KiCad 6+ uses `EDA_ANGLE(degrees, DEGREES_T)`, KiCad 5 uses decidegrees
5. **Object lifetime:** Keep Python references to all created PCB objects to prevent garbage collection crashes
6. **Footprint paths:** OS-specific, use `KISYSMOD` environment variable or platform detection
7. **Refresh() blocks:** Synchronous call that freezes Python execution until rendering complete

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

**Apply to:** Traces, vias, footprints, text objects

## KiCad Version Compatibility

Target: KiCad 7 or 8 (latest stable)

**Compatibility layer:** `kicad_compat.py` provides version-agnostic API:
```python
KICAD_VERSION = pcbnew.Version()

def create_point(x, y):
    if KICAD_VERSION.startswith('5'):
        return pcbnew.wxPoint(x, y)
    else:
        return pcbnew.VECTOR2I(x, y)
```

## Implementation Phases

**Phase 0:** Environment setup and benchmarking (validate assumptions)
**Phase 1:** DOOM engine integration (doomgeneric platform implementation)
**Phase 2:** Python PCB renderer (vector → trace conversion)
**Phase 3:** DOOM ↔ Python bridge (socket communication)
**Phase 4:** Input handling (OS-level keyboard capture)
**Phase 5:** Main plugin integration (tie everything together)

## Testing Strategy

1. **Refresh benchmark:** Measure actual frame time with 200 traces
2. **Object pool test:** Verify reuse is 3-5x faster than create/destroy
3. **Socket latency:** Ensure IPC overhead < 5ms
4. **End-to-end:** Run DOOM for 60s, track FPS/memory/stability

## Known Pitfalls

1. **`Refresh()` blocks execution:** Expected behavior, DOOM runs in separate process
2. **Object lifetime:** Keep Python references to prevent GC crashes
3. **Socket reliability:** Add timeouts and robust error handling
4. **Performance degradation:** Force GC every 500 frames, monitor memory
5. **Footprint loading:** Pre-load at startup (10-50ms each), paths are OS-specific
6. **Coordinate confusion:** Always use `CoordinateTransform` class

## Electrical Authenticity Requirements

This is a legitimate PCB design using real electrical elements:
- Must use `PCB_TRACK` (copper traces, not `PCB_SHAPE` drawings)
- Must use `PCB_VIA` (drilled holes)
- Must use `FOOTPRINT` (real components)
- All elements connected to a net (`DOOM_WORLD`)
- Could theoretically be fabricated (though non-functional)

## Performance Expectations

**Target:** 10-25 FPS depending on hardware
- M1 MacBook Pro: 15-25 FPS
- Dell XPS (i7 12th gen, RTX 3050 Ti): 18-28 FPS
- Older hardware (i5, integrated GPU): 8-15 FPS

**Visual style:** Wireframe vector rendering (think Asteroids/Battlezone), not pixel-perfect DOOM

## Dependencies

**Python:**
- pynput (OS-level keyboard capture)
- psutil (memory monitoring, optional)

**C:**
- GCC/Clang
- Standard C library (socket, unistd)
- SDL2 (optional, sound only)

**KiCad:**
- Version 6+ (Python API support)
- Python scripting enabled

## File Structure Reference

```
kicad_doom_plugin/
├── doom_plugin_action.py     # Main ActionPlugin entry point
├── pcb_renderer.py            # DOOM vectors → PCB traces
├── doom_bridge.py             # Unix socket server
├── input_handler.py           # Keyboard capture (pynput)
├── object_pool.py             # Pre-allocated PCB objects
├── coordinate_transform.py    # DOOM ↔ KiCad coordinate conversion
├── kicad_compat.py            # Version compatibility layer
├── config.py                  # Constants (scale factors, pool sizes)
├── doom/
│   ├── doomgeneric_kicad     # Compiled DOOM binary
│   ├── doom1.wad             # Game data (shareware)
│   └── source/
│       ├── doomgeneric_kicad.c  # Platform implementation
│       ├── doom_socket.c        # Socket client
│       └── Makefile.kicad       # Build config
└── tests/
    ├── benchmark_refresh.py
    ├── benchmark_object_pool.py
    └── benchmark_socket.py
```
