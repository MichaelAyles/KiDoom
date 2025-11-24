# KiCad Wireframe Integration Plan (2025-11-24)

## Status: 🚧 PLANNING

Plan for integrating the wireframe renderer into KiCad PCBnew using real PCB traces.

---

## Ultra-Think: Challenges & Solutions

### Previous Issues We Faced

**Problem 1: KiCad `Refresh()` Performance**
- `pcbnew.Refresh()` is **blocking** and **slow** (20-50ms per call)
- Blocks Python execution until screen update completes
- With our target of 30-70 walls per frame, we'd need:
  - ~280 trace updates (70 walls × 4 edges)
  - Plus entities, plus refresh
  - Total: ~100ms per frame = **10 FPS max**

**Solution:** Already implemented in existing plugin:
- Thread-separated architecture:
  - Background thread: Updates PCB objects (non-blocking)
  - Main thread: Calls `Refresh()` via wx.Timer (at controlled rate)
- Object pooling: Reuse objects instead of create/destroy
- Result: Achieved **82 FPS** in benchmarks!

**Problem 2: Coordinate System Mismatch**
- DOOM: 320×200 pixels, origin top-left, Y increases down
- KiCad: Nanometers, origin at center, Y increases up

**Solution:** Already implemented `CoordinateTransform` class:
```python
SCALE = 500000  # 1 DOOM pixel = 0.5mm = 500,000 nm

def doom_to_kicad(doom_x, doom_y):
    # Center on KiCad origin (200mm × 200mm board)
    x_offset = -(DOOM_WIDTH / 2) * SCALE  # -80mm
    y_offset = -(DOOM_HEIGHT / 2) * SCALE  # -50mm

    kicad_x = doom_x * SCALE + x_offset
    kicad_y = -(doom_y * SCALE + y_offset)  # Flip Y

    return (kicad_x, kicad_y)
```

**Problem 3: Object Creation Overhead**
- Creating/destroying `PCB_TRACK` every frame is slow (50-100ms)
- With 280 traces, would kill performance

**Solution:** Already implemented object pools:
- Pre-allocate all objects at startup (one-time 1-2s cost)
- Reuse objects by updating positions
- Hide unused objects (set width to 0, move off-screen)
- Result: **3-5x speedup**

---

## New Challenge: Wireframe Wall Rendering

### Current Plugin Architecture (Raster-style)

**Old approach (rasterized walls):**
```
Wall in DOOM: (x1, y1, x2, y2, distance)
              ↓
   1 PCB_TRACK (single line)
```

**Limitations:**
- Only shows horizontal scan line (wall at floor level)
- No sense of wall height or structure
- Doesn't represent 3D geometry

### New Approach (Wireframe Boxes)

**Wireframe walls (like standalone renderer):**
```
Wall segment: (x1, y1_top, y1_bottom, x2, y2_top, y2_bottom, distance, silhouette)
              ↓
   4 PCB_TRACK objects (wireframe box):
   - Top edge:    (x1, y1_top) → (x2, y2_top)
   - Bottom edge: (x1, y1_bottom) → (x2, y2_bottom)
   - Left edge:   (x1, y1_top) → (x1, y1_bottom)
   - Right edge:  (x2, y2_top) → (x2, y2_bottom)
```

**Benefits:**
- Shows wall structure and height
- Matches standalone wireframe renderer
- Proper 3D representation
- Can see through (PCB traces don't block view)

**Cost:**
- 4× more traces (280 instead of 70)
- But object pool handles this fine (pre-allocated)
- Still within performance budget

---

## Data Flow: DOOM → KiCad

### Message Format (from C code)

```json
{
  "frame": 1234,
  "walls": [
    [x1, y1_top, y1_bottom, x2, y2_top, y2_bottom, distance, silhouette],
    ...
  ],
  "entities": [
    {"x": X, "y_top": Yt, "y_bottom": Yb, "height": H, "type": T, "distance": D},
    ...
  ],
  "weapon": {"x": X, "y": Y, "visible": true/false}
}
```

### Processing Pipeline

```
1. DOOM C Engine
   ↓ (extract vectors with viewz correction, silhouette filtering)
   ↓
2. JSON over Unix Socket
   ↓ (MSG_FRAME_DATA)
   ↓
3. KiCad Plugin (doom_bridge.py)
   ↓ (receive on background thread)
   ↓
4. PCB Renderer (pcb_renderer.py)
   ↓ (update trace positions in object pool)
   ↓
5. Main Thread Timer (wx.Timer)
   ↓ (call Refresh() at controlled rate)
   ↓
6. KiCad Display Update
```

---

## Implementation Strategy

### Phase 1: Adapt Existing Socket Bridge ✅ (Already Works)

**File:** `kicad_doom_plugin/doom_bridge.py`

Current status:
- Unix socket client implemented
- Background thread for receiving
- Message parsing (JSON)
- **Works with existing standalone renderer!**

**Changes needed:**
- None! Already compatible with wireframe message format
- Just need to handle the additional fields (y_top, y_bottom, silhouette)

### Phase 2: Update PCB Renderer for Wireframe 🚧 (MAIN WORK)

**File:** `kicad_doom_plugin/pcb_renderer.py`

**Changes needed:**

1. **Update `_render_walls()` method:**
   ```python
   def _render_walls(self, walls):
       trace_pool = self.pools['traces']
       trace_index = 0

       for wall in walls:
           if len(wall) < 8:
               continue

           x1, y1_top, y1_bottom, x2, y2_top, y2_bottom, distance, silhouette = wall[:8]

           # Skip portal walls (silhouette=0)
           if silhouette == 0:
               continue

           # Render 4 edges as separate traces
           edges = [
               (x1, y1_top, x2, y2_top),      # Top edge
               (x1, y1_bottom, x2, y2_bottom), # Bottom edge
               (x1, y1_top, x1, y1_bottom),   # Left edge
               (x2, y2_top, x2, y2_bottom)    # Right edge
           ]

           for (sx, sy, ex, ey) in edges:
               if trace_index >= len(trace_pool.objects):
                   break  # Pool exhausted

               trace = trace_pool.get(trace_index)
               trace_index += 1

               # Convert coordinates
               kicad_sx, kicad_sy = CoordinateTransform.doom_to_kicad(sx, sy)
               kicad_ex, kicad_ey = CoordinateTransform.doom_to_kicad(ex, ey)

               # Update trace
               trace.SetStart(pcbnew.VECTOR2I(kicad_sx, kicad_sy))
               trace.SetEnd(pcbnew.VECTOR2I(kicad_ex, kicad_ey))

               # Distance-based styling
               if distance < DISTANCE_THRESHOLD:
                   trace.SetLayer(pcbnew.F_Cu)  # Close = Front copper (red)
                   trace.SetWidth(TRACE_WIDTH_CLOSE)  # Thick
               else:
                   trace.SetLayer(pcbnew.B_Cu)  # Far = Back copper (cyan)
                   trace.SetWidth(TRACE_WIDTH_FAR)  # Thin

               trace.SetNet(self.doom_net)

       trace_pool.hide_unused(trace_index)
   ```

2. **Update object pool sizes:**
   ```python
   # In config.py
   MAX_WALLS = 70  # Max walls per frame
   EDGES_PER_WALL = 4  # Wireframe box has 4 edges
   MAX_TRACES = MAX_WALLS * EDGES_PER_WALL + 50  # 330 traces total
   ```

3. **Entity rendering (sprites as rectangles):**
   ```python
   def _render_entities(self, entities):
       # Option A: Use footprints (existing approach)
       # Option B: Use 4 traces to draw rectangle (consistent with wireframe)

       # Recommendation: Use traces for consistency
       trace_pool = self.pools['traces']

       for entity in entities:
           x = entity['x']
           y_top = entity['y_top']
           y_bottom = entity['y_bottom']
           height = entity['height']
           width = height  # Square aspect

           # Calculate rectangle corners
           x1 = x - width // 2
           x2 = x + width // 2

           # 4 edges for rectangle
           edges = [
               (x1, y_top, x2, y_top),        # Top
               (x1, y_bottom, x2, y_bottom),  # Bottom
               (x1, y_top, x1, y_bottom),     # Left
               (x2, y_top, x2, y_bottom)      # Right
           ]

           # Render as traces (same as walls but different layer/width for distinction)
   ```

### Phase 3: Update Object Pools 🚧

**File:** `kicad_doom_plugin/object_pool.py`

**Changes needed:**

1. **Increase trace pool size:**
   ```python
   # Current: ~100 traces
   # Needed: ~330 traces (70 walls × 4 + 10 entities × 4 + margin)

   def create_trace_pool(board, max_size=350):
       # Increased from 100 to 350
   ```

2. **Consider separate pools for walls vs entities:**
   ```python
   pools = {
       'wall_traces': TracePool(board, 300),  # For walls
       'entity_traces': TracePool(board, 50), # For entities/sprites
       # Could use different default widths/layers
   }
   ```

### Phase 4: Update Main Plugin Entry Point 🚧

**File:** `kicad_doom_plugin/doom_plugin_action.py`

**Changes needed:** Minimal
- Most logic already exists
- Just verify it handles new message format
- Add any user-facing controls (FPS limit, wireframe toggle, etc.)

---

## Performance Analysis

### Trace Count Per Frame

**Walls:**
- Max walls: 70
- Edges per wall: 4
- Total: 280 traces

**Entities:**
- Max entities: 10
- Edges per entity: 4 (rectangle)
- Total: 40 traces

**Grand Total:** ~320 traces per frame

### Object Pool Allocation

**Startup (one-time cost):**
- Allocate 350 `PCB_TRACK` objects: ~1-2 seconds
- Create DOOM net: <100ms
- Total: ~2 seconds (acceptable!)

**Per-Frame Update:**
- Update 320 trace positions: ~10-20ms (object pool reuse)
- `Refresh()` call: ~20-50ms
- **Total: ~30-70ms = 14-33 FPS**

**Expected Performance:** 15-25 FPS (playable for tech demo!)

This is **better than original raster approach** because:
- Fewer scene complexity (wireframe vs filled polygons)
- No sprite scaling calculations
- No complex depth sorting (already sorted by DOOM)

---

## Coordinate Scaling Considerations

### Screen Space to Board Space

**DOOM rendering space:**
- 320×200 pixels
- Wall coordinates are screen-space (already projected)

**KiCad board space:**
- Want ~200mm × 200mm playable area
- 1 DOOM pixel = 0.5mm = 500,000 nm

**Example wall:**
```
DOOM coords: (x1=50, y1_top=40, y1_bottom=120, x2=80, y2_top=45, y2_bottom=118)

KiCad coords:
  x1 = (50 - 160) * 500000 = -55,000,000 nm = -55mm (left of center)
  y1_top = -(40 - 100) * 500000 = 30,000,000 nm = 30mm (above center)
  y1_bottom = -(120 - 100) * 500000 = -10,000,000 nm = -10mm (below center)
  ... same for x2, y2_top, y2_bottom
```

**Board setup:**
- 200mm × 200mm board (edge cuts)
- Origin at center
- DOOM view centered on origin
- Extends ±100mm horizontally, ±50mm vertically

---

## Layer Strategy

### Option A: Distance-Based Layers (Current Approach)
- **F.Cu (Front copper, red):** Close walls (<500 distance)
- **B.Cu (Back copper, cyan):** Far walls (≥500 distance)

**Pros:**
- Depth perception via color
- Simple implementation

**Cons:**
- Only 2 depth levels
- Limited color palette

### Option B: Gradient via Trace Width
- **All on F.Cu**
- Distance determines width:
  - Close: 0.5mm (brightest)
  - Medium: 0.3mm
  - Far: 0.1mm (dimmest)

**Pros:**
- Smoother depth cueing
- Matches standalone renderer gradient

**Cons:**
- Only one color (copper red)
- Width differences subtle in PCB view

### Option C: Hybrid (RECOMMENDED)
- **Walls:** Distance-based layers (F.Cu/B.Cu) + width
- **Entities:** Always F.Cu, fixed width
- **Floor/Ceiling:** Cannot render gradients in KiCad easily
  - Option: Skip floor/ceiling (wireframe walls only)
  - Option: Render horizon line only

**Decision:** Start with Option A (existing code), can enhance later.

---

## Floor/Ceiling Challenge

### Problem
Standalone renderer uses **full-screen gradients** (200 horizontal scan lines).

In KiCad, this would mean:
- 200 `PCB_TRACK` objects for floor gradient
- 200 `PCB_TRACK` objects for ceiling gradient
- Total: 400 extra traces!
- **Not practical** (would need 720 traces total, kills performance)

### Solutions

**Option 1: Skip Floor/Ceiling (RECOMMENDED)**
- Render walls and entities only
- Clean wireframe aesthetic
- Matches DOOM automap style
- Performance: Best

**Option 2: Horizon Line Only**
- Single horizontal trace at screen center (Y=100)
- Represents eye level
- Minimal cost (1 trace)
- Provides orientation reference

**Option 3: Simplified Gradient**
- 10 horizontal traces instead of 200
- Floor: 5 traces from horizon to bottom
- Ceiling: 5 traces from top to horizon
- Cost: 10 traces (acceptable)
- Still shows depth somewhat

**Decision:** Option 1 for initial implementation, Option 2 as enhancement.

---

## Testing Strategy

### Phase 1: Unit Tests
1. **Coordinate transformation:**
   ```python
   assert CoordinateTransform.doom_to_kicad(160, 100) == (0, 0)  # Center
   assert CoordinateTransform.doom_to_kicad(0, 0) == (-80mm, 50mm)  # Top-left
   ```

2. **Wall edge generation:**
   ```python
   wall = [50, 40, 120, 80, 45, 118, 500, 3]  # Full wireframe wall
   edges = generate_wall_edges(wall)
   assert len(edges) == 4  # Top, bottom, left, right
   ```

### Phase 2: Visual Tests
1. **Static frame test:**
   - Load single frame from JSON file
   - Render to PCB
   - Verify geometry looks correct

2. **Performance test:**
   - Render 100 consecutive frames
   - Measure FPS
   - Target: >15 FPS

3. **Live DOOM test:**
   - Run DOOM engine
   - Connect via socket
   - Play for 60 seconds
   - Verify stability

---

## Implementation Checklist

- [ ] Update `config.py` with new trace pool sizes
- [ ] Modify `pcb_renderer.py._render_walls()` for 4-edge wireframe
- [ ] Update `pcb_renderer.py._render_entities()` for rectangles
- [ ] Increase object pool allocation in `object_pool.py`
- [ ] Test coordinate transformation with sample walls
- [ ] Add silhouette filtering (skip silhouette=0)
- [ ] Performance test: 100 frames
- [ ] Live DOOM integration test
- [ ] Document frame rate and limitations
- [ ] Add user controls (start/stop, FPS display)

---

## Expected Outcome

**Visual Result:**
- Wireframe DOOM rendered on PCB with real copper traces
- Wall structures shown as rectangular boxes
- Entities shown as rectangles
- Distance-based depth cueing (layer + width)
- Clean, technical aesthetic

**Performance:**
- 15-25 FPS (playable)
- Stable over extended gameplay
- No memory leaks (object pooling)
- Smooth refresh (timer-based)

**Uniqueness:**
- First-ever wireframe DOOM on PCB traces
- Could be fabricated (electrically valid PCB)
- Real components for entities (footprints)
- Connected to single net (DOOM_WORLD)

---

## Future Enhancements

1. **Multiple depth layers:**
   - Use In1.Cu, In2.Cu for intermediate distances
   - 4-6 depth levels instead of 2

2. **Trace width gradient:**
   - Continuous width variation based on distance
   - Smoother depth cueing

3. **Horizon line:**
   - Add single horizontal trace at Y=0 (screen center)
   - Provides orientation reference

4. **Simplified floor gradient:**
   - 5-10 horizontal traces
   - Show floor/ceiling with minimal trace count

5. **Animation smoothing:**
   - Interpolate between frames
   - Smoother movement

6. **Export fabricatable PCB:**
   - Snapshot current frame
   - Save as PCB file
   - Could actually be manufactured!

---

## Risk Mitigation

**Risk 1: Performance < 15 FPS**
- Mitigation: Reduce trace pool size, skip entities, optimize Refresh() rate
- Fallback: Snapshot mode (update every 2-3 seconds instead of real-time)

**Risk 2: Object pool exhaustion**
- Mitigation: Pre-allocate generous pool (350 traces)
- Fallback: Graceful degradation (skip walls when pool full)

**Risk 3: KiCad threading crashes**
- Mitigation: Use existing wx.Timer architecture (proven stable)
- Fallback: Main-thread-only rendering (slower but stable)

**Risk 4: Coordinate overflow**
- Mitigation: Test edge cases (corners, extreme angles)
- Fallback: Clamp coordinates to board bounds

---

## Success Criteria

**Minimum Viable:**
- ✅ Wireframe walls render correctly
- ✅ Depth cueing visible (close vs far)
- ✅ >10 FPS sustained
- ✅ No crashes over 60 seconds

**Target:**
- ✅ 15-25 FPS
- ✅ Entities visible
- ✅ Clean wireframe aesthetic matching standalone
- ✅ Side-by-side with standalone for comparison

**Stretch:**
- ✅ >25 FPS
- ✅ Horizon line
- ✅ Simplified floor gradient
- ✅ Export fabricatable PCB

---

## Timeline Estimate

- Phase 1 (Config updates): 15 minutes
- Phase 2 (Wall rendering): 1 hour
- Phase 3 (Entity rendering): 30 minutes
- Phase 4 (Testing): 1 hour
- Phase 5 (Polish/debug): 30 minutes

**Total:** ~3-4 hours for fully working wireframe KiCad integration

---

## Conclusion

The KiCad wireframe integration is **highly feasible** because:

1. ✅ **Existing infrastructure works** - Socket bridge, threading, object pools all proven
2. ✅ **Performance is viable** - 320 traces = 15-25 FPS (acceptable for tech demo)
3. ✅ **Coordinate system solved** - CoordinateTransform already handles this
4. ✅ **Wireframe data available** - DOOM C code exports all needed fields

**Main work:** Adapt wall rendering from 1-trace-per-wall to 4-traces-per-wall.

**Biggest challenge:** Floor/ceiling gradients (solved by skipping them).

**Outcome:** First-ever wireframe DOOM rendered on fabricatable PCB traces! 🎮⚡

---

## References

- Standalone renderer: `src/standalone_renderer.py`
- Vector extraction: `doom/source/doomgeneric_kicad_dual_v2.c`
- Existing PCB renderer: `kicad_doom_plugin/pcb_renderer.py`
- Object pools: `kicad_doom_plugin/object_pool.py`
- Coordinate transform: `kicad_doom_plugin/coordinate_transform.py`
- Performance doc: `logs/docs/21_RENDERING_PERSPECTIVE_FIXES.md`
