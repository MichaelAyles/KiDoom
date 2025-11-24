# KiDoom Screenshot Archive

This directory contains reference screenshots showing the final working state of the DOOM wireframe renderer after all perspective and occlusion fixes.

## Screenshots

### final_wireframe_renderer_example_1.png
- **Date:** 2025-11-24
- **Frame:** 3067609
- **Shows:** Complete wireframe rendering with:
  - Correct perspective projection (walls extending to bottom of screen)
  - Wireframe edge rendering (transparent, can see through)
  - Floor/ceiling gradients with depth cueing
  - Proper visibility through multi-height environments
  - Side-by-side comparison: Wireframe (left) vs SDL (right)

### final_wireframe_renderer_example_2.png
- **Date:** 2025-11-24
- **Frame:** 3067599
- **Shows:** Alternative view demonstrating:
  - Partial walls rendered (stairs, ledges)
  - Silhouette filtering (portals skipped)
  - Distance-based brightness (far = dark, near = bright)
  - Entity rendering with type-based colors
  - Performance: ~59 FPS with 30-70 walls per frame

## Technical Details

### Rendering Features Demonstrated

**Perspective Projection:**
- Uses `viewz` (player eye level) for relative height calculation
- Formula: `screen_y = centeryfrac - FixedMul(world_z - viewz, scale)`
- Results in correct ground-level perspective

**Wireframe Rendering:**
- Walls drawn as 4 edge lines (top, bottom, left, right)
- 2px wide lines with distance-based brightness
- Allows transparency to see multi-height environments

**Floor/Ceiling Gradients:**
- Full-screen horizontal gradients (not per-wall)
- Floor: horizon (dark) → bottom (bright), yellow/brown tint
- Ceiling: top (bright) → horizon (dark), cyan tint
- Depth cueing effect for distance perception

**Silhouette Filtering:**
- Portal walls (silhouette=0) skipped
- Partial walls (silhouette=1,2) rendered for stairs/windows
- Full walls (silhouette=3) rendered for solid barriers

### Screenshot Capture System

These screenshots were captured using the socket-based system where:
1. DOOM C code saves SDL surface to BMP (direct surface access)
2. C sends MSG_SCREENSHOT message with filename to Python
3. Python saves pygame surface and combines with SDL image
4. Combined image saved as PNG with both views side-by-side

**Performance:** <50ms total overhead per screenshot

## File Naming Convention

Format: `final_wireframe_renderer_example_N.png`

- `final`: Indicates production-ready renderer (all fixes applied)
- `wireframe_renderer`: Rendering mode
- `example_N`: Sequential number

Original filenames: `combined_<timestamp>.png`

## Reference Documentation

For complete technical details, see:
- `../docs/20_20251124_154000_VECTOR_EXTRACTION_GUIDE.md` - Vector extraction
- `../docs/21_20251124_170000_RENDERING_PERSPECTIVE_FIXES.md` - All rendering fixes

## Issues Fixed (visible in these screenshots)

✅ Wall perspective extends to bottom of screen (not compressed to top half)
✅ Gaps between pillars show through correctly (no green fill)
✅ Pools and lower floors visible through wall edges
✅ Stairs show individual step detail
✅ Floor/ceiling gradients provide depth perception
✅ 59 FPS performance maintained

## Historical Note

The framebuffer directory is cleared on each renderer restart, so earlier problem screenshots showing the various issues we fixed are not available. These screenshots represent the **final working state** after all 6 major rendering challenges were resolved.

For visual references of the problems we solved, refer to the diagrams in the documentation files.
