# 🎮 Test Standalone Renderer NOW

## One-Command Test

```bash
cd /Users/tribune/Desktop/KiDoom
./test_standalone.sh
```

This checks dependencies and starts the renderer.

## Manual Steps (if script doesn't work)

### Terminal 1: Start Renderer

```bash
cd /Users/tribune/Desktop/KiDoom
python3 standalone_renderer.py
```

### Terminal 2: Launch DOOM

```bash
cd /Users/tribune/Desktop/KiDoom/doom
./doomgeneric_kicad
```

## What You'll See

1. **pygame window opens** (1280x800)
2. **Console shows**: "✓ DOOM connected!"
3. **Rendering appears**: Lines (walls), circles (entities)
4. **FPS counter**: Top-right corner
5. **You can play**: Use WASD, arrows, Ctrl to shoot

## Expected Result

✅ **SUCCESS**:
- Window shows vector graphics
- Can move and shoot
- FPS: 30-60
- **Means**: DOOM engine works! Problem is in KiCad plugin.

❌ **FAILURE**:
- Window blank or no rendering
- **Means**: DOOM engine has issues, fix that first.

## Quick Troubleshooting

**"pygame not installed"**:
```bash
pip3 install pygame
```

**"DOOM binary not found"**:
```bash
cd doom
make -f Makefile.kicad
```

**"Socket already in use"**:
```bash
rm /tmp/kicad_doom.sock
```

## Why This Matters

If standalone works but KiCad crashes:
- ✅ DOOM engine is fine
- ✅ Socket protocol is fine
- ✅ Frame data is fine
- ❌ **Problem is in KiCad plugin threading/timer**

This narrows down the debugging to just the KiCad side!

---

**Ready?** Run `./test_standalone.sh` now! 🚀
