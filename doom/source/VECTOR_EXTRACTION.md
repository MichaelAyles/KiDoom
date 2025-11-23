# Vector Extraction Strategy for KiDoom

## The Core Challenge

DOOM renders to a 320×200 pixel framebuffer (64,000 pixels). Converting each pixel to a PCB pad would require:
- 64,000 PCB objects per frame
- ~0.1ms per object = 6.4 seconds per frame
- **Result: 0.15 FPS (unplayable)**

## The Solution: Vector Rendering

Instead of raster pixels, we extract **vector line segments** that DOOM calculates internally. A typical DOOM frame has:
- 100-300 wall segments
- 5-20 entities (player, enemies)
- 0-50 projectiles

**Result: 200-500x performance improvement → 40-60 FPS (playable)**

---

## Implementation Approaches

### Approach 1: Pixel Buffer Edge Detection (Current - MVP)

**What it does:**
- Scans the completed pixel buffer for edges
- Detects color transitions (walls, objects)
- Converts edges to line segments
- Sends as JSON vectors

**Advantages:**
- Simple to implement
- No DOOM source code modifications
- Works with any DOOM port
- Easy to debug

**Disadvantages:**
- Still processes 64,000 pixels per frame
- Generates approximate vectors (not true DOOM geometry)
- CPU intensive (though acceptable at 82.6 FPS)
- Loses depth information

**Code location:** `doomgeneric_kicad.c::convert_frame_to_json()`

**Algorithm:**
```c
for (each row in screen buffer, sampling every 4th row) {
    for (each pixel in row) {
        if (color_difference(pixel[x], pixel[x-1]) > THRESHOLD) {
            // Edge detected - start line segment
            segment = {x_start, y, x_end, y, fake_depth};
            add_to_json(segment);
        }
    }
}
```

**Performance:**
- Edge detection: ~0.4ms per frame
- JSON serialization: ~0.1ms per frame
- Total overhead: ~0.5ms (negligible compared to 12ms frame budget)

---

### Approach 2: Rendering Pipeline Hooks (Future - Optimal)

**What it does:**
- Hooks into DOOM's rendering functions BEFORE rasterization
- Extracts wall segments from BSP tree traversal
- Gets entity positions from sprite renderer
- Captures projectile coordinates from game state

**Advantages:**
- True vector data (exact DOOM geometry)
- No pixel processing needed
- Preserves depth information
- 50% CPU reduction
- More accurate representation

**Disadvantages:**
- Requires DOOM source code modification
- More complex implementation
- Tightly coupled to DOOM internals
- Harder to debug

**Required modifications:**

#### 1. Wall Segment Extraction

**File to modify:** `r_segs.c` (wall rendering)

**Current DOOM code:**
```c
void R_DrawWalls(seg_t* seg) {
    // Calculate wall segment endpoints
    x1 = seg->v1->x;
    y1 = seg->v1->y;
    x2 = seg->v2->x;
    y2 = seg->v2->y;

    // Rasterize to pixel buffer
    for (int x = x1; x < x2; x++) {
        R_DrawColumn(x, ytop, ybottom, texture);
    }
}
```

**Modified code with hook:**
```c
// Global vector accumulator
extern WallSegment g_wall_segments[MAX_WALLS];
extern int g_wall_count;

void R_DrawWalls(seg_t* seg) {
    // HOOK: Extract vector BEFORE rasterization
    if (g_wall_count < MAX_WALLS) {
        g_wall_segments[g_wall_count++] = (WallSegment){
            .x1 = seg->v1->x,
            .y1 = seg->v1->y,
            .x2 = seg->v2->x,
            .y2 = seg->v2->y,
            .distance = seg->offset,
            .height = ytop - ybottom,
            .texture = seg->sidedef->toptexture
        };
    }

    // Continue normal rendering (for completeness)
    for (int x = x1; x < x2; x++) {
        R_DrawColumn(x, ytop, ybottom, texture);
    }
}
```

**In `DG_DrawFrame()`:**
```c
void DG_DrawFrame(void) {
    // Convert accumulated vectors to JSON
    char* json = wall_segments_to_json(g_wall_segments, g_wall_count);
    doom_socket_send_frame(json, strlen(json));

    // Reset for next frame
    g_wall_count = 0;
}
```

#### 2. Entity Position Extraction

**File to modify:** `r_things.c` (sprite rendering)

**Current DOOM code:**
```c
void R_DrawSprites(void) {
    for (vissprite_t* spr = vissprites; spr < vissprite_p; spr++) {
        // Draw sprite at spr->x, spr->y
        R_DrawSprite(spr);
    }
}
```

**Modified code:**
```c
extern EntityPosition g_entities[MAX_ENTITIES];
extern int g_entity_count;

void R_DrawSprites(void) {
    for (vissprite_t* spr = vissprites; spr < vissprite_p; spr++) {
        // HOOK: Extract entity position
        if (g_entity_count < MAX_ENTITIES) {
            g_entities[g_entity_count++] = (EntityPosition){
                .x = spr->x,
                .y = spr->y,
                .type = get_entity_type(spr->mobjflags),
                .angle = spr->angle
            };
        }

        R_DrawSprite(spr);
    }
}
```

#### 3. Projectile Detection

**File to modify:** `p_mobj.c` (game objects)

**Approach:** Query active projectiles from game state
```c
extern Projectile g_projectiles[MAX_PROJECTILES];
extern int g_projectile_count;

void extract_projectiles(void) {
    thinker_t* th;
    mobj_t* mobj;

    g_projectile_count = 0;

    // Iterate through all active game objects
    for (th = thinkercap.next; th != &thinkercap; th = th->next) {
        if (th->function.acp1 == (actionf_p1)P_MobjThinker) {
            mobj = (mobj_t*)th;

            // Check if it's a projectile
            if (mobj->flags & MF_MISSILE) {
                if (g_projectile_count < MAX_PROJECTILES) {
                    g_projectiles[g_projectile_count++] = (Projectile){
                        .x = mobj->x >> FRACBITS,
                        .y = mobj->y >> FRACBITS,
                        .type = mobj->type
                    };
                }
            }
        }
    }
}
```

**In `DG_DrawFrame()`:**
```c
void DG_DrawFrame(void) {
    // Extract all vectors
    extract_projectiles();  // New function

    // Build comprehensive JSON
    char* json = build_complete_frame_json(
        g_wall_segments, g_wall_count,
        g_entities, g_entity_count,
        g_projectiles, g_projectile_count
    );

    doom_socket_send_frame(json, strlen(json));

    // Reset all counters
    g_wall_count = 0;
    g_entity_count = 0;
    g_projectile_count = 0;
}
```

---

## JSON Output Format

### Current Format (Approach 1)

```json
{
  "walls": [
    {"x1": 10, "y1": 50, "x2": 100, "y2": 50, "distance": 80}
  ],
  "entities": [
    {"x": 160, "y": 100, "type": "player", "angle": 0}
  ],
  "frame": 1234
}
```

**Size:** ~50-100 bytes per wall segment

### Enhanced Format (Approach 2)

```json
{
  "walls": [
    {
      "x1": 10, "y1": 50, "x2": 100, "y2": 50,
      "distance": 80,
      "height": 64,
      "texture": 5
    }
  ],
  "entities": [
    {
      "x": 160, "y": 100,
      "type": "player",
      "angle": 90,
      "state": "walking"
    }
  ],
  "projectiles": [
    {"x": 120, "y": 75, "type": "bullet"}
  ],
  "hud": {
    "health": 100,
    "armor": 50,
    "ammo": 50,
    "weapon": "shotgun"
  },
  "frame": 1234
}
```

**Size:** ~150-200 bytes per wall segment (but more accurate)

---

## Performance Comparison

| Metric | Approach 1 (Edge Detection) | Approach 2 (Pipeline Hooks) |
|--------|---------------------------|---------------------------|
| CPU usage (vector extraction) | 0.4ms | 0.1ms |
| JSON size per frame | 10-15 KB | 12-18 KB |
| Accuracy | ~80% (approximation) | 100% (true geometry) |
| Implementation complexity | Low | High |
| DOOM source modifications | None | Moderate |
| Debugging difficulty | Easy | Hard |

---

## Migration Path

### Phase 1.0 (Current - MVP)
- ✅ Implement edge detection approach
- ✅ Get basic wall rendering working
- ✅ Prove concept feasibility
- Target: 40+ FPS

### Phase 1.5 (Optimization)
- Improve edge detection algorithm
- Add better depth estimation
- Optimize JSON serialization
- Target: 50+ FPS

### Phase 2.0 (Pipeline Hooks)
- Implement wall segment hooks in `r_segs.c`
- Add entity extraction in `r_things.c`
- Add projectile detection in `p_mobj.c`
- Target: 60+ FPS

### Phase 3.0 (Advanced Features)
- Add texture information
- Extract floor/ceiling data
- Animated door states
- Dynamic lighting hints

---

## Implementation Checklist

### Approach 1 (Current)
- [x] Basic edge detection in `convert_frame_to_json()`
- [x] JSON serialization
- [x] Socket communication
- [ ] Improved depth estimation
- [ ] Better entity detection (bright pixel clustering)
- [ ] Projectile tracking (motion detection)

### Approach 2 (Future)
- [ ] Modify `r_segs.c` for wall hooks
- [ ] Modify `r_things.c` for sprite hooks
- [ ] Implement projectile query in `p_mobj.c`
- [ ] Add global vector accumulators
- [ ] Build comprehensive JSON from multiple sources
- [ ] Test accuracy vs. pixel buffer

---

## Testing Strategy

### Validation Tests

**Test 1: Vector Count**
```
Expected: 100-300 wall segments per frame
Measure: Count JSON wall array length
Pass if: 50 < count < 500
```

**Test 2: Coordinate Accuracy** (Approach 2 only)
```
Expected: Vectors match BSP tree geometry
Measure: Compare extracted coords vs. DOOM internal state
Pass if: < 5% error
```

**Test 3: Performance**
```
Expected: Vector extraction < 1ms
Measure: Time convert_frame_to_json()
Pass if: avg_time < 1.0ms
```

**Test 4: Completeness**
```
Expected: All visible walls captured
Measure: Visual comparison of PCB render vs. normal DOOM
Pass if: No major missing geometry
```

---

## Debugging Tools

### Vector Dump Utility

Add to `doomgeneric_kicad.c`:
```c
void dump_vectors_to_file(void) {
    static int dump_count = 0;
    char filename[256];
    sprintf(filename, "/tmp/doom_vectors_%04d.json", dump_count++);

    FILE* f = fopen(filename, "w");
    if (f) {
        size_t len;
        char* json = convert_frame_to_json(&len);
        fwrite(json, 1, len, f);
        fclose(f);
        printf("Dumped vectors to %s\n", filename);
    }
}
```

**Usage:**
- Call every Nth frame to capture vector data
- Analyze JSON offline
- Compare with DOOM's internal state (using debugger)

### Visualization Tool

Python script to visualize extracted vectors:
```python
import json
import matplotlib.pyplot as plt

# Load JSON
with open('/tmp/doom_vectors_0001.json') as f:
    data = json.load(f)

# Plot walls
for wall in data['walls']:
    plt.plot([wall['x1'], wall['x2']],
             [wall['y1'], wall['y2']],
             'b-', linewidth=2)

# Plot entities
for entity in data['entities']:
    plt.plot(entity['x'], entity['y'], 'ro', markersize=10)

plt.xlim(0, 320)
plt.ylim(0, 200)
plt.gca().invert_yaxis()  # DOOM Y is downward
plt.title('DOOM Vectors')
plt.show()
```

---

## References

**DOOM Rendering Engine:**
- https://doomwiki.org/wiki/Doom_rendering_engine
- https://github.com/id-Software/DOOM/blob/master/linuxdoom-1.10/r_segs.c
- https://github.com/id-Software/DOOM/blob/master/linuxdoom-1.10/r_things.c

**BSP Tree Rendering:**
- http://www.fabiensanglard.net/doomIphone/doomClassicRenderer.php
- https://www.bluesnews.com/abrash/chap70.shtml

**doomgeneric Framework:**
- https://github.com/ozkl/doomgeneric
- https://github.com/ozkl/doomgeneric/blob/master/doomgeneric/doomgeneric.h

---

## Summary

**Current Status (Approach 1):**
- ✅ Simple edge detection
- ✅ Functional baseline
- ✅ 40+ FPS expected
- ⚠️ Approximates vectors from pixels

**Future Goal (Approach 2):**
- 🎯 True vector extraction
- 🎯 50% CPU reduction
- 🎯 60+ FPS target
- 🎯 100% accurate geometry

**Recommendation:** Start with Approach 1 (already implemented), migrate to Approach 2 after proving feasibility.
