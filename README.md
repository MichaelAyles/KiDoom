# KiDoom

**DOOM running on KiCad PCB traces**

A technical demonstration that renders the classic DOOM game using real PCB design elements in KiCad's PCBnew. Wall segments become copper traces, enemies become footprints, and projectiles become vias.

![KiDoom Demo](docs/demo.gif)
*Vector-based DOOM rendered entirely with PCB copper traces*

## What is this?

KiDoom ports the original DOOM to run inside KiCad's PCB editor, using authentic electrical components as the display medium:

- **Walls:** `PCB_TRACK` objects (copper traces on F.Cu/B.Cu layers)
- **Player:** QFP-64 footprint (reference designator: U1)
- **Enemies:** Various SMD/THT footprints (SOT-23, TO-220, DIP-8)
- **Projectiles:** `PCB_VIA` objects (drilled holes)
- **HUD:** Silkscreen text (`PCB_TEXT` on F.SilkS layer)

This creates a legitimate PCB design that could theoretically be fabricated (though it wouldn't do anything useful).

## Why does this work?

**The key insight:** DOOM's engine already calculates visible geometry as vectors (wall segments). Instead of converting these to 64,000 pixels, we render them directly as ~200 PCB traces per frame.

**Performance math:**
- Raster approach: 320×200 = 64,000 pads @ 0.1ms each = 6.4s per frame = **0.15 FPS** ❌
- Vector approach: ~200 traces @ 0.1ms each + reuse = 20-50ms per frame = **10-25 FPS** ✅

## Performance Expectations

**Expected FPS by hardware:**
- M1 MacBook Pro / similar: **15-25 FPS**
- Modern desktop (i7, discrete GPU): **18-28 FPS**
- Older hardware (i5, integrated GPU): **8-15 FPS**

This is playable, but not smooth. Think "tech demo" rather than "competitive gaming."

## Prerequisites

- **KiCad 6.0 or newer** (7.0+ recommended)
- **Python 3.7+** with KiCad scripting support
- **GCC or Clang** (for compiling DOOM)
- **macOS or Linux** (Windows untested but should work)

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/kidoom.git
cd kidoom
```

### 2. Install Python dependencies

```bash
pip install pynput psutil
```

### 3. Build the DOOM engine

```bash
# Clone doomgeneric
git clone https://github.com/ozkl/doomgeneric.git
cd doomgeneric/doomgeneric

# Copy KiCad platform implementation
cp ../../doom/source/* .

# Build
make -f Makefile.kicad

# Copy binary and WAD back
cp doomgeneric_kicad ../../doom/
cd ../..

# Download shareware DOOM WAD (if not included)
# wget https://distro.ibiblio.org/slitaz/sources/packages/d/doom1.wad
# mv doom1.wad doom/
```

### 4. Install the KiCad plugin

```bash
# Find your KiCad plugin directory
# Linux: ~/.kicad/scripting/plugins/
# macOS: ~/Library/Application Support/kicad/scripting/plugins/
# Windows: %APPDATA%\kicad\scripting\plugins\

# Create symlink or copy
ln -s "$(pwd)/kicad_doom_plugin" ~/.kicad/scripting/plugins/kidoom
```

### 5. Configure KiCad for performance (CRITICAL)

Open KiCad PCBnew and apply these settings:

1. **View → Show Grid:** Uncheck ❌
2. **View → Ratsnest:** Uncheck ❌
3. **Preferences → PCB Editor → Display Options:**
   - Clearance outlines: **OFF**
   - Pad/Via holes: **Do not show**
4. **Preferences → Common → Graphics:**
   - Antialiasing: **Fast** or **Disabled**
   - Rendering engine: **Accelerated**

**Without these settings, performance will be 2-5x slower!**

## Usage

### Running the benchmark (recommended first step)

Before running the full game, validate your system can achieve playable framerates:

1. Open KiCad PCBnew
2. Create a new PCB (200mm × 200mm recommended)
3. Tools → Scripting Console
4. Run:
   ```python
   exec(open('/path/to/kidoom/tests/benchmark_refresh.py').read())
   ```

**Success criteria:**
- < 50ms per frame = Excellent (20+ FPS)
- 50-100ms = Playable (10-20 FPS)
- \> 100ms = May be too slow

### Playing DOOM

1. Open KiCad PCBnew
2. Create or open a PCB
3. **Tools → External Plugins → DOOM on PCB**
4. Wait ~5 seconds for DOOM to launch and connect
5. Play!

**Controls:**
- **WASD** - Move forward/backward/strafe
- **Arrow Keys** - Turn left/right
- **Ctrl** - Shoot
- **Space / E** - Use (open doors)
- **ESC** - Quit

**Note:** Input is captured at the OS level, so you may need to grant accessibility permissions (macOS) or run KiCad from terminal to see debug output.

## How it works

### Architecture

```
┌─────────────────┐         Unix Socket          ┌──────────────────┐
│   DOOM Engine   │◄──────────────────────────►│  KiCad Plugin    │
│   (C Process)   │  /tmp/kicad_doom.sock       │  (Python)        │
└─────────────────┘                              └──────────────────┘
        │                                                 │
        │ Renders vectors                                │ Converts to PCB
        │ (wall segments)                                │ traces/footprints
        │                                                 │
        ▼                                                 ▼
  JSON Frame Data                               pcbnew.PCB_TRACK
  {"walls": [...],                              pcbnew.PCB_VIA
   "entities": [...]}                           pcbnew.FOOTPRINT
```

### Key optimizations

1. **Object pooling:** Pre-allocate 500 traces, 50 vias, 20 footprints at startup. Reuse by updating positions instead of creating/destroying each frame (3-5x speedup)

2. **Single shared net:** All geometry connected to one net (`DOOM_WORLD`) to eliminate ratsnest calculation overhead

3. **Minimal layers:** Only F.Cu and B.Cu enabled (depth encoding: red=close, cyan=far)

4. **Vector rendering:** Render DOOM's internal wall segments directly as traces instead of converting to pixels

5. **Off-screen hiding:** Move unused objects to (-1000, -1000)mm instead of deleting them

## Project Structure

```
kidoom/
├── kicad_doom_plugin/        # KiCad Python plugin
│   ├── doom_plugin_action.py # Main entry point
│   ├── pcb_renderer.py       # DOOM → PCB conversion
│   ├── doom_bridge.py        # Socket communication
│   ├── input_handler.py      # Keyboard capture
│   └── object_pool.py        # Pre-allocated objects
├── doom/
│   ├── source/               # C source for DOOM port
│   │   ├── doomgeneric_kicad.c
│   │   ├── doom_socket.c
│   │   └── Makefile.kicad
│   ├── doomgeneric_kicad    # Compiled binary
│   └── doom1.wad            # Game data
├── tests/                    # Performance benchmarks
└── docs/                     # Screenshots/videos
```

## Troubleshooting

### Plugin doesn't appear in KiCad

- Check plugin is in correct directory: Tools → External Plugins → Open Plugin Directory
- Look for Python errors in Tools → Scripting Console
- Verify KiCad version is 6.0+ with Python support

### Performance is poor (< 5 FPS)

- **Double-check manual settings** (grid off, ratsnest off, antialiasing off)
- Run benchmark to measure actual frame time
- Check CPU/GPU usage (should be high during gameplay)
- Try reducing resolution in `config.py`

### Socket connection fails

- Ensure `/tmp/kicad_doom.sock` isn't left over from crashed session: `rm /tmp/kicad_doom.sock`
- Check DOOM binary has execute permissions: `chmod +x doom/doomgeneric_kicad`
- Verify DOOM binary exists and can run: `./doom/doomgeneric_kicad`

### Input doesn't work

- Install pynput: `pip install pynput`
- Grant accessibility permissions (macOS: System Preferences → Security → Accessibility)
- Check keyboard events in terminal output when running KiCad from command line

### Crashes / Segfaults

- Ensure you're keeping Python references to all PCB objects
- Don't call `board.Remove()` during rendering
- Check KiCad version compatibility (target 7.0+)

## Technical Details

### Coordinate transformation

- **DOOM:** 320×200 pixels, (0,0) at top-left, Y increases downward
- **KiCad:** nanometers, (0,0) at origin, Y increases upward
- **Scale:** 1 DOOM pixel = 0.5mm = 500,000nm

### Communication protocol

Binary protocol over Unix socket:
```
[4 bytes: msg_type][4 bytes: payload_len][N bytes: JSON payload]
```

Message types: `FRAME_DATA (0x01)`, `KEY_EVENT (0x02)`, `INIT_COMPLETE (0x03)`, `SHUTDOWN (0x04)`

### Depth encoding

Since PCBs have limited "color", depth is encoded using:
- **Layer:** F.Cu (red) = close (0-100 units), B.Cu (cyan) = far (100+ units)
- **Trace width:** Thick (0.3mm) = bright/near, thin (0.15mm) = dim/far

## Known Limitations

- **Framerate:** 10-25 FPS, not smooth but playable
- **Visual fidelity:** Wireframe only, no textures or sprites
- **Input capture:** Global keyboard hooks may conflict with other apps
- **Platform:** Primarily tested on macOS/Linux, Windows support uncertain
- **Performance degradation:** May slow down after extended play (>5 minutes)

## Contributing

Contributions welcome! Areas for improvement:

- Windows compatibility testing
- Performance optimizations (shader-based rendering?)
- 3D viewer real-time updates
- More depth layers (4-layer boards)
- Sound support via Python audio libraries

## License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file.

**DOOM engine:** Original DOOM source code by id Software, released under GPL
**doomgeneric:** By ozkl, GPL license

## Credits

- **id Software** - Original DOOM (1993)
- **ozkl** - doomgeneric framework
- **KiCad** - Open source PCB design software
- Inspired by various "DOOM on everything" projects

## FAQ

**Q: Can this PCB actually be fabricated?**
A: Technically yes - it uses real copper traces, vias, and footprints. But it wouldn't do anything useful. It's electrically valid but functionally meaningless.

**Q: Why does this exist?**
A: Because DOOM runs on everything, and PCB editors are Turing-complete if you're creative enough.

**Q: Will this work in the 3D viewer?**
A: Not currently - the 3D viewer doesn't update in real-time. You'd need to manually refresh, making it unusable for gameplay. 2D editor only.

**Q: Can I use my own DOOM WAD?**
A: Yes! Replace `doom1.wad` with `doom2.wad`, `plutonia.wad`, etc. Full DOOM should work (untested).

**Q: What about multiplayer?**
A: Not implemented, but theoretically possible - each player could have their own PCB board, synchronized via network.

## See Also

- [DOOM on oscilloscope](https://www.youtube.com/watch?v=3vwHR7GIcPQ)
- [DOOM on pregnancy test](https://www.youtube.com/watch?v=6OzIH3xG39I)
- [doomgeneric](https://github.com/ozkl/doomgeneric) - Framework used for porting
- [KiCad Python API](https://docs.kicad.org/doxygen-python/namespacepcbnew.html)

---

**Can it run DOOM?** Yes. Even PCB editors. 🎮⚡
