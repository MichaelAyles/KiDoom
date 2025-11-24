# KiDoom Quick Start Guide

**Run DOOM inside KiCad PCB Editor using PCB traces as the display!**

---

## Current Status: Phase 3 - Ready for Integration Testing

All components are built, installed, and ready to test.

---

## Quick Test (5 minutes)

### 1. Open KiCad

```bash
# Open the test project
open ~/Desktop/KiDoom/kicad_source/blank_project/blank_project.kicad_pcb
```

Or create a new PCB in KiCad PCBnew.

### 2. Optimize Settings

In KiCad:
- View → Show Grid: **OFF**
- View → Ratsnest: **OFF**
- Preferences → Graphics → Antialiasing: **Fast**

### 3. Start the Plugin

- Tools → External Plugins → **KiDoom → Start DOOM**

If plugin doesn't appear:
- Restart KiCad completely
- Or manually run in Tools → Scripting Console:
  ```python
  import sys
  sys.path.append('/Users/tribune/Documents/KiCad/9.0/scripting/plugins')
  from kicad_doom_plugin import doom_plugin_action
  plugin = doom_plugin_action.KiDoomPlugin()
  plugin.Run()
  ```

### 4. Play!

**Controls:**
- **WASD** or **Arrow keys**: Move/turn
- **Space**: Fire weapon / Open doors
- **Ctrl**: Use switches
- **Esc**: Menu

**What you'll see:**
- PCB traces animate as walls
- Footprints/vias represent enemies
- Text elements show HUD (health, ammo)

**Expected Performance:** 40-60 FPS

---

## Installation Paths

```
Plugin:         ~/Documents/KiCad/9.0/scripting/plugins/kicad_doom_plugin/
DOOM Binary:    kicad_doom_plugin/doom/doomgeneric_kicad (537KB)
WAD File:       kicad_doom_plugin/doom/doom1.wad (4.0MB)
Socket:         /tmp/kidoom.sock (created automatically)
```

---

## Troubleshooting

### "No module named 'pynput'"
```bash
pip3 install pynput
```

### "Connection refused"
1. Ensure KiCad plugin is running (Start DOOM button clicked)
2. Remove stale socket: `rm /tmp/kidoom.sock`
3. Restart both KiCad and DOOM

### Plugin doesn't appear in menu
1. Check installation: `ls ~/Documents/KiCad/9.0/scripting/plugins/kicad_doom_plugin/`
2. Restart KiCad completely
3. Check KiCad console for errors (Tools → Scripting Console)

### Poor performance (< 20 FPS)
1. Disable grid and ratsnest (View menu)
2. Use Fast antialiasing (Preferences → Graphics)
3. Close other applications
4. Ensure running on AC power (not battery)

### Keyboard not working (macOS)
- System Settings → Privacy & Security → Accessibility
- Add Python to allowed apps
- Restart KiCad

---

## Architecture

```
┌──────────────────┐         Unix Socket         ┌─────────────────┐
│  DOOM Engine     │◄────────────────────────────►│  KiCad Python   │
│  (C Process)     │   /tmp/kidoom.sock          │  Plugin         │
│                  │                              │                 │
│  - Game Logic    │   Frame Data (JSON) ──►     │  - PCB Renderer │
│  - Vector        │   ◄── Keyboard Events       │  - Input Handler│
│    Extraction    │                              │  - Object Pools │
└──────────────────┘                              └─────────────────┘
        ↓                                                  ↓
   doom1.wad                                        KiCad PCBnew
  (Game Data)                                    (320x200 → Traces)
```

---

## Performance Benchmarks (M1 MacBook Pro)

| Component | Result | Status |
|-----------|--------|--------|
| PCB Refresh | 82.6 FPS | ✓ EXCELLENT |
| Socket IPC | 0.049ms | ✓ EXCELLENT |
| Object Pool | 1.08x speedup | ✓ GOOD |

**Expected gameplay:** 40-60 FPS with full game logic overhead.

---

## Files Overview

```
KiDoom/
├── PHASE3_INTEGRATION.md   ← Comprehensive testing guide
├── QUICK_START.md          ← This file
├── README.md               ← Project overview
├── CLAUDE.md               ← AI assistant documentation
├── tests/
│   ├── BENCHMARK_RESULTS.md
│   ├── benchmark_refresh_safe.py
│   ├── benchmark_socket.py
│   └── benchmark_object_pool_safe.py
├── doom/source/            ← C source files
│   ├── doomgeneric_kicad.c (338 lines)
│   ├── doom_socket.c/h
│   ├── Makefile.kicad
│   └── build.sh
└── kicad_doom_plugin/      ← Python plugin (installed to KiCad)
    ├── doom_plugin_action.py (main entry)
    ├── pcb_renderer.py (rendering engine)
    ├── doom_bridge.py (socket server)
    ├── object_pool.py (PCB object pools)
    ├── input_handler.py (keyboard)
    └── doom/
        ├── doomgeneric_kicad (executable)
        └── doom1.wad (shareware)
```

---

## What's Working

✅ **Phase 0:** Benchmarks complete and validated
✅ **Phase 1:** DOOM engine built with KiCad platform
✅ **Phase 2:** Python plugin with full renderer
✅ **Phase 3:** Integration setup complete
🔄 **Phase 3 Testing:** Ready for user verification

---

## Next Steps

1. **Run integration test** (see PHASE3_INTEGRATION.md)
2. **Verify rendering** - See walls as PCB traces
3. **Test gameplay** - Play for 5 minutes
4. **Report issues** - Document any problems found

---

## Documentation

- **PHASE3_INTEGRATION.md** - Detailed testing instructions
- **tests/BENCHMARK_RESULTS.md** - Performance analysis
- **CLAUDE.md** - Architecture and development guide
- **README.md** - Project overview and installation

---

## Support

If you encounter issues:

1. Check PHASE3_INTEGRATION.md troubleshooting section
2. Verify installation paths
3. Run benchmark suite to isolate problem
4. Check logs in terminal (DOOM) and KiCad console

---

**Built:** 2025-11-23
**Platform:** macOS (M1 MacBook Pro)
**KiCad:** 9.0.2
**Status:** Ready for testing

---

*Have fun playing DOOM on PCB traces!*
