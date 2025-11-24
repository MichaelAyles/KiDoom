# KiDoom - Project Status

**Last Updated**: November 24, 2024

## Current State

✅ **Working**: Standalone renderer with direct vector extraction from DOOM internals
⚠️ **In Progress**: KiCad plugin has threading issues on macOS
🎯 **Next**: Refine vector extraction for better visual quality

## What Works

### Standalone Renderer (Fully Functional)
- ✅ pygame-based vector renderer
- ✅ Real-time rendering at 60+ FPS
- ✅ Direct extraction from DOOM's `drawsegs[]` and `vissprites[]` arrays
- ✅ Dual-output mode (SDL window + vectors side-by-side)
- ✅ Full keyboard controls
- ✅ Socket communication protocol

### DOOM Engine (Fully Functional)
- ✅ Compiled binaries for macOS (ARM64)
- ✅ Vector-only mode (`doomgeneric_kicad`)
- ✅ Dual-output mode (`doomgeneric_kicad_dual`)
- ✅ Direct memory access to rendering structures
- ✅ Socket client for frame transmission

## What Needs Work

### Vector Extraction Quality
- ⚠️ Walls rendered as vertical lines (works but not accurate)
- 🎯 Need to extract actual wall top/bottom coordinates
- 🎯 Floor/ceiling segments not yet extracted
- 🎯 Sprite rendering could be improved

### KiCad Plugin
- ❌ Crashes on macOS due to threading restrictions
- 📝 Queue-based solution implemented but not fully tested
- 📝 Timer-based refresh working in isolation (smiley test)
- 🎯 Need to integrate proven timer approach with DOOM bridge

## How to Use (Current)

### Recommended: Dual Mode
Shows both original DOOM and vector extraction side-by-side:

```bash
./run_doom.sh dual -w 1 1
```

### Testing: Standalone Renderer
Test vector pipeline without KiCad:

```bash
# Terminal 1
./run_standalone_renderer.py

# Terminal 2
./run_doom.sh vector -w 1 1
```

## Architecture Summary

```
DOOM Engine (C)
├─ Reads drawsegs[] array → Wall segments
├─ Reads vissprites[] array → Entities
├─ Sends JSON via socket
└─ (Optional) Shows SDL window

↓ Unix Socket (/tmp/kicad_doom.sock)

Renderer (Python)
├─ Standalone: pygame (WORKING ✅)
└─ KiCad: PCB objects (IN PROGRESS ⚠️)
```

## Performance

| Component | Current FPS | Target FPS | Status |
|-----------|-------------|------------|--------|
| DOOM Engine | ~35 FPS | 35 FPS | ✅ Optimal |
| Standalone Renderer | 60+ FPS | 30+ FPS | ✅ Excellent |
| KiCad Plugin | N/A (crashes) | 20 FPS | ❌ Needs fix |
| Socket Overhead | < 1ms | < 5ms | ✅ Negligible |

## Known Issues

### 1. macOS Threading (Critical)
**Problem**: KiCad crashes when PCB objects modified from background threads
**Attempted Fixes**:
- V1: `wx.CallAfter()` - Failed
- V2: Timer + flag - Failed
- V3: Queue-based - Implemented, not fully tested

**Documented**: `logs/docs/11_*_FINAL_FIX_V3.md`

### 2. Vector Quality (Medium Priority)
**Problem**: Walls rendered as simple vertical lines, not actual geometry
**Current**: Reading `drawsegs[].x1`, `drawsegs[].scale1`
**Needed**: Extract actual top/bottom Y coordinates from DOOM's rendering

### 3. Entity Rendering (Low Priority)
**Current**: Simple circles at sprite positions
**Future**: Could extract actual sprite graphics and convert to footprints

## Directory Structure

```
KiDoom/
├── README.md              # Main documentation
├── CLAUDE.md              # Claude Code instructions
├── STATUS.md              # This file
│
├── run_doom.sh            # DOOM launcher
├── run_standalone_renderer.py  # Renderer launcher
│
├── src/                   # Python source
│   └── standalone_renderer.py
│
├── kicad_doom_plugin/     # KiCad plugin (needs fixes)
├── doom/                  # DOOM binaries and source
├── tests/                 # Test scripts
├── scripts/               # Utilities
└── logs/docs/             # Development history (18 docs)
```

## Next Steps

### Immediate (Vector Quality)
1. Modify `doomgeneric_kicad.c` to extract actual wall Y coordinates
2. Use `drawsegs[].bsilheight` and `drawsegs[].tsilheight` for top/bottom
3. Test with standalone renderer
4. Iterate until visual quality matches DOOM

### Short Term (KiCad Integration)
1. Test smiley face plugin on macOS (verify timer works)
2. If smiley works, apply same architecture to DOOM plugin
3. If smiley fails, investigate alternative approaches

### Long Term (Polish)
1. Add floor/ceiling rendering
2. Improve sprite extraction
3. Optimize frame rate in KiCad
4. Add configuration options
5. Windows/Linux compatibility testing

## Testing

### Quick Validation
```bash
# Build
cd doom/source && ./build.sh

# Test dual mode
./run_doom.sh dual -w 1 1
```

Should see:
- SDL window with original DOOM graphics ✅
- pygame window with vector lines ✅
- Console showing frame stats ✅

### Full Test Suite
```bash
# Smiley test (KiCad)
export KIDOOM_TEST_MODE=true
open -a KiCad
# Tools → External Plugins → KiDoom

# Standalone renderer
./run_standalone_renderer.py
# (In another terminal)
./run_doom.sh vector
```

## Resources

- **Development Docs**: `logs/docs/` (18 files, chronological)
- **Original README**: `logs/docs/00_original_README.md`
- **Threading Fixes**: `logs/docs/07-11_*_threading_*.md`
- **Standalone Dev**: `logs/docs/16-18_*_standalone_*.md`

## Questions?

Check `logs/docs/README.md` for chronological development history.
