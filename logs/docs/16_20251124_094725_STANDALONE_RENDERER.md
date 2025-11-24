# Standalone Python Vector Renderer

This provides a pure Python frontend to test the DOOM engine **without KiCad**.

## Why This Exists

Testing with KiCad is slow and crashes are hard to debug. This standalone renderer:

✅ **Tests the full pipeline** - DOOM engine → socket → frame processing → rendering
✅ **Isolates KiCad issues** - If this works but KiCad doesn't, problem is in KiCad
✅ **Faster iteration** - No KiCad startup time, easier debugging
✅ **Visual verification** - See what DOOM is actually sending
✅ **No threading complexity** - Simple single-threaded rendering

## Requirements

```bash
pip install pygame
```

## Quick Start

### Terminal 1: Start Renderer

```bash
cd /Users/tribune/Desktop/KiDoom
python3 standalone_renderer.py
```

Expected output:
```
======================================================================
DOOM Standalone Vector Renderer
======================================================================
✓ pygame initialized
  Display: 1280x800
✓ Socket created: /tmp/kicad_doom.sock
  Waiting for DOOM to connect...
```

### Terminal 2: Launch DOOM

```bash
cd /Users/tribune/Desktop/KiDoom/doom
./doomgeneric_kicad
```

Expected output:
```
[In Terminal 1]
✓ DOOM connected!

======================================================================
Renderer Running!
======================================================================

Controls:
  WASD          - Move
  Arrow keys    - Turn
  Ctrl          - Fire
  Space/E       - Use/Open doors
  1-7           - Select weapon
  ESC           - Menu/Quit

Close window or press ESC to quit
======================================================================
```

## What You Should See

- **Window**: 1280x800 pygame window
- **Rendering**: Vector graphics (lines, circles)
- **Colors**:
  - Copper/orange lines: Walls (front layer)
  - Blue lines: Walls (back layer)
  - Gold circles: Entities (player, enemies)
  - Red circles: Projectiles
  - White text: HUD
- **FPS counter**: Top right corner

## Controls

Same as DOOM plugin:

- **WASD** - Move forward/back/strafe
- **Arrow keys** - Turn left/right
- **Ctrl** - Fire weapon
- **Space / E** - Use / Open doors
- **1-7** - Select weapon
- **ESC** - Menu / Quit

## Architecture

```
┌────────────────────┐
│  DOOM Engine (C)   │
│  - Game logic      │
│  - Vector extract  │
│  - JSON serialize  │
└─────────┬──────────┘
          │ Unix socket
          │ /tmp/kicad_doom.sock
          ↓
┌────────────────────┐
│ standalone_        │
│   renderer.py      │
│  - Socket server   │
│  - Frame parser    │
│  - pygame render   │
└────────────────────┘
```

**Key difference from KiCad plugin**:
- **No background threads** - Receive in main thread
- **No queue** - Direct rendering
- **No timer** - Render as frames arrive
- **Simpler** - Just socket → parse → draw

## What This Tests

### If Standalone Renderer Works ✅

**Confirmed**:
- DOOM engine compiles and runs
- Socket communication works
- Frame data is valid JSON
- Vector extraction works
- Protocol is correct

**Conclusion**:
- DOOM side is healthy
- Problem is in KiCad plugin (threading, timer, or KiCad API)
- Next: Compare standalone vs KiCad rendering to find difference

### If Standalone Renderer Fails ❌

**Issue is in DOOM engine**:
- Socket connection fails → Check socket permissions
- Invalid JSON → Check DOOM's JSON generation
- No frames received → Check DOOM's render loop
- Malformed frame data → Check vector extraction

**Next steps**:
- Debug DOOM engine C code
- Check socket communication
- Verify JSON format

## Debugging

### Enable Detailed Logging

Edit `standalone_renderer.py` and add after line 1:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check Frame Data

Add to `receive_loop()` after receiving MSG_FRAME_DATA:

```python
print(f"Frame received: {len(payload)} bytes")
print(f"  Walls: {len(payload.get('walls', []))}")
print(f"  Entities: {len(payload.get('entities', []))}")
print(f"  Projectiles: {len(payload.get('projectiles', []))}")
```

### Monitor Socket

```bash
# In another terminal
watch -n 1 'ls -l /tmp/kicad_doom.sock'
```

### Check Process

```bash
# Make sure DOOM is running
ps aux | grep doomgeneric_kicad

# Make sure renderer is running
ps aux | grep standalone_renderer
```

## Comparison to KiCad Plugin

| Feature | Standalone | KiCad Plugin |
|---------|-----------|--------------|
| **Rendering** | pygame (fast) | PCB traces (slow) |
| **Threading** | Single thread | 2 threads + queue |
| **Refresh** | Immediate | Timer-based (30 FPS) |
| **Complexity** | ~400 lines | ~2000 lines |
| **Startup** | < 1 second | 5-10 seconds |
| **Debugging** | Easy (print logs) | Hard (KiCad console) |
| **Crashes** | Python traceback | KiCad crash report |

## Common Issues

### "pygame not installed"

```bash
pip3 install pygame
```

### "Socket already in use"

```bash
# Remove old socket
rm /tmp/kicad_doom.sock

# Or kill old process
killall standalone_renderer.py
```

### "DOOM won't connect"

1. Check DOOM is using same socket path
2. Check socket permissions: `ls -l /tmp/kicad_doom.sock`
3. Try creating socket manually: `nc -U /tmp/kicad_doom.sock`

### "Window appears but nothing renders"

1. Check console for frame data
2. Verify DOOM is sending frames: Add debug logging
3. Check coordinate conversion (DOOM 320x200 → screen 1280x800)

### "Rendering is choppy"

Normal! DOOM sends ~35 FPS, this just renders as-is.
To smooth: Reduce pygame tick rate in `run()`:

```python
self.clock.tick(30)  # Cap at 30 FPS instead of 60
```

## Performance Expectations

| Metric | Expected | Notes |
|--------|----------|-------|
| **FPS** | 30-60 | Limited by DOOM engine, not renderer |
| **CPU** | 10-20% | pygame is efficient |
| **Memory** | 50-100 MB | Python + pygame + DOOM |
| **Latency** | < 5ms | Socket + JSON parsing |

## Next Steps After Testing

### Test Result: WORKS ✅

1. **Verify frame data**:
   - All wall segments present?
   - Entities positioned correctly?
   - HUD displaying?

2. **Compare to KiCad plugin**:
   - Same socket, same protocol
   - Why does this work but KiCad crashes?
   - **Hypothesis**: threading/timer issue in KiCad plugin

3. **Debug KiCad plugin**:
   - Focus on queue processing (`pcb_renderer.py:_on_refresh_timer`)
   - Check thread safety
   - Try removing queue (direct render like standalone)

### Test Result: FAILS ❌

1. **Check DOOM engine**:
   - Does it compile? `cd doom && make -f Makefile.kicad`
   - Does it run? `./doomgeneric_kicad` should show window
   - Check socket code in `doom_socket.c`

2. **Check protocol**:
   - Is MSG_FRAME_DATA (0x01) being sent?
   - Is JSON valid?
   - Add debug prints in DOOM C code

3. **Fix DOOM first**, then retry standalone renderer

## Files

- **Renderer**: `standalone_renderer.py` (main file)
- **DOOM engine**: `doom/doomgeneric_kicad` (binary)
- **Socket protocol**: `doom/source/doom_socket.c` (C implementation)
- **This doc**: `STANDALONE_RENDERER.md`

## Tips

1. **Always start renderer first** (creates socket)
2. **Then launch DOOM** (connects to socket)
3. **Close DOOM with ESC** (clean shutdown)
4. **Or close renderer window** (sends shutdown to DOOM)

## Success Criteria

✅ Window opens
✅ DOOM connects (console shows "✓ DOOM connected!")
✅ Lines appear representing walls
✅ Circles represent player/enemies
✅ FPS counter updates
✅ Keyboard controls work
✅ No crashes for 60+ seconds

**If all pass**: DOOM engine is good, problem is in KiCad plugin!
