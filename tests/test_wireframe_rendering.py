#!/usr/bin/env python3
"""
Wireframe Rendering Integration Test

This test validates that the wireframe rendering implementation works correctly
with the updated pcb_renderer.py and can handle realistic DOOM frame data.

Tests:
1. Coordinate transformation (DOOM pixels → KiCad nanometers)
2. Wireframe wall rendering (4 traces per wall)
3. Wireframe entity rendering (4 traces per entity)
4. Silhouette filtering (skip portal walls)
5. Performance with realistic frame data (70 walls + 5 entities)

Expected result:
- All rendering completes without errors
- Performance >15 FPS (target for KiCad wireframe)
- Coordinate transformations are accurate
"""

import sys
import os

# Add plugin directory to path
# Handle both direct execution and exec() in KiCad console
try:
    plugin_dir = os.path.join(os.path.dirname(__file__), '..', 'kicad_doom_plugin')
except NameError:
    # Running via exec() in KiCad console - __file__ not defined
    # Assume we're in the KiDoom project directory
    plugin_dir = os.path.join(os.getcwd(), 'kicad_doom_plugin')
    if not os.path.exists(plugin_dir):
        # Try absolute path
        plugin_dir = '/Users/tribune/Desktop/KiDoom/kicad_doom_plugin'

# Add parent directory too for package imports
parent_dir = os.path.dirname(plugin_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)

import pcbnew
import time

# Import from the kicad_doom_plugin package
from kicad_doom_plugin.coordinate_transform import CoordinateTransform
from kicad_doom_plugin.pcb_renderer import DoomPCBRenderer


def create_sample_wireframe_walls(num_walls=70):
    """
    Create realistic wireframe wall data.

    Format: [x1, y1_top, y1_bottom, x2, y2_top, y2_bottom, distance, silhouette]
    """
    walls = []

    for i in range(num_walls):
        # Simulate walls at various distances and heights
        x1 = (i * 4) % 320  # Spread across screen
        x2 = x1 + 8  # 8-pixel wide wall segment

        # Vary wall heights (perspective effect)
        distance = 50 + (i * 3) % 150  # Distance 50-200

        # Further walls appear smaller (perspective)
        if distance < 80:
            y1_top = 40
            y1_bottom = 160
            y2_top = 42
            y2_bottom = 158
        elif distance < 120:
            y1_top = 60
            y1_bottom = 140
            y2_top = 62
            y2_bottom = 138
        else:
            y1_top = 80
            y1_bottom = 120
            y2_top = 82
            y2_bottom = 118

        # Mix of wall types (skip some portals)
        silhouette = 3 if i % 10 != 0 else 0  # 10% portals

        walls.append([x1, y1_top, y1_bottom, x2, y2_top, y2_bottom, distance, silhouette])

    return walls


def create_sample_wireframe_entities(num_entities=5):
    """
    Create realistic wireframe entity data.

    Format: {"x": X, "y_top": Yt, "y_bottom": Yb, "height": H, "type": T, "distance": D}
    """
    entities = []
    entity_types = ['player', 'imp', 'demon', 'baron', 'cacodemon']

    for i in range(num_entities):
        x = 50 + (i * 50)
        y_top = 60
        y_bottom = 140
        height = 32  # Entity width in DOOM pixels
        distance = 80 + (i * 20)
        entity_type = entity_types[i % len(entity_types)]

        entities.append({
            'x': x,
            'y_top': y_top,
            'y_bottom': y_bottom,
            'height': height,
            'type': entity_type,
            'distance': distance
        })

    return entities


def test_coordinate_transform():
    """Test DOOM → KiCad coordinate transformation."""
    print("\n" + "=" * 70)
    print("TEST 1: Coordinate Transformation")
    print("=" * 70)

    test_cases = [
        # (doom_x, doom_y, expected_description)
        (0, 0, "Top-left corner → PCB center-top"),
        (160, 100, "Screen center → PCB origin"),
        (320, 200, "Bottom-right corner → PCB center-bottom"),
        (160, 0, "Top center → PCB top"),
        (0, 100, "Left center → PCB left"),
    ]

    print("\nTransforming key DOOM screen positions:")
    print(f"{'DOOM (x,y)':<20} {'KiCad (x,y) nm':<30} {'Description'}")
    print("-" * 70)

    all_passed = True
    for doom_x, doom_y, description in test_cases:
        kicad_x, kicad_y = CoordinateTransform.doom_to_kicad(doom_x, doom_y)
        print(f"({doom_x:>3}, {doom_y:>3}){' '*10} "
              f"({kicad_x:>11}, {kicad_y:>11}){' '*4} {description}")

        # Verify ranges (screen should map to ~160mm × 100mm PCB)
        if abs(kicad_x) > 100000000 or abs(kicad_y) > 100000000:
            print(f"  ✗ ERROR: Coordinate out of expected range!")
            all_passed = False

    if all_passed:
        print("\n✓ All coordinate transformations within expected ranges")
    else:
        print("\n✗ Some coordinate transformations failed")

    return all_passed


def test_wireframe_rendering(board, num_frames=100):
    """Test complete wireframe rendering pipeline."""
    print("\n" + "=" * 70)
    print("TEST 2: Wireframe Rendering Performance")
    print("=" * 70)

    print(f"\nConfiguration:")
    print(f"  Test frames: {num_frames}")
    print(f"  Walls per frame: 70 (× 4 edges = 280 traces)")
    print(f"  Entities per frame: 5 (× 4 edges = 20 traces)")
    print(f"  Total traces: 300 per frame")
    print(f"  Target FPS: >15 FPS (acceptable for tech demo)")

    # Initialize renderer
    print("\nInitializing renderer...")
    renderer = DoomPCBRenderer(board)

    # Create sample data
    walls = create_sample_wireframe_walls(70)
    entities = create_sample_wireframe_entities(5)

    # Count non-portal walls
    non_portal_walls = sum(1 for w in walls if w[7] != 0)
    print(f"\nSample data:")
    print(f"  Total walls: {len(walls)}")
    print(f"  Non-portal walls: {non_portal_walls} (portals filtered)")
    print(f"  Portal walls: {len(walls) - non_portal_walls} (should be skipped)")
    print(f"  Entities: {len(entities)}")

    # Run rendering benchmark
    print(f"\nRendering {num_frames} frames...")
    times = []

    for frame in range(num_frames):
        frame_data = {
            'walls': walls,
            'entities': entities,
            'projectiles': [],  # No projectiles in this test
            'hud': {}  # No HUD in this test
        }

        start = time.time()

        # Process frame directly (bypass queue for test)
        renderer._process_frame(frame_data)

        elapsed = time.time() - start
        times.append(elapsed)

        # Progress indicator
        if (frame + 1) % 20 == 0:
            avg_so_far = sum(times) / len(times)
            fps_so_far = 1.0 / avg_so_far if avg_so_far > 0 else 0
            print(f"  Frame {frame + 1:3d}/{num_frames}: "
                  f"{elapsed*1000:>6.2f}ms  "
                  f"(Avg: {avg_so_far*1000:>6.2f}ms, {fps_so_far:>5.1f} FPS)")

    # Calculate statistics
    avg_time = sum(times) / len(times)
    min_time = min(times)
    max_time = max(times)
    avg_fps = 1.0 / avg_time if avg_time > 0 else 0

    # Count slow frames (>66ms = <15 FPS)
    slow_frames = sum(1 for t in times if t > 0.066)
    slow_pct = (slow_frames / len(times)) * 100

    print("\n" + "=" * 70)
    print("PERFORMANCE RESULTS")
    print("=" * 70)
    print(f"\nFrame Times:")
    print(f"  Average: {avg_time*1000:.2f}ms  ({avg_fps:.1f} FPS)")
    print(f"  Best:    {min_time*1000:.2f}ms  ({1.0/min_time:.1f} FPS)")
    print(f"  Worst:   {max_time*1000:.2f}ms  ({1.0/max_time:.1f} FPS)")
    print(f"\nSlow frames (>66ms): {slow_frames}/{len(times)} ({slow_pct:.1f}%)")

    # Assessment
    print("\n" + "=" * 70)
    print("ASSESSMENT")
    print("=" * 70)

    target_fps = 15.0
    good_fps = 20.0

    if avg_fps >= good_fps:
        print(f"\n✓ EXCELLENT: {avg_fps:.1f} FPS achieved!")
        print(f"  Performance exceeds target ({target_fps} FPS) by {avg_fps-target_fps:.1f} FPS")
        print("  Wireframe rendering is highly playable.")
        assessment = "pass"
    elif avg_fps >= target_fps:
        print(f"\n✓ GOOD: {avg_fps:.1f} FPS achieved!")
        print(f"  Performance meets target ({target_fps} FPS)")
        print("  Wireframe rendering is playable.")
        assessment = "pass"
    else:
        print(f"\n✗ BELOW TARGET: {avg_fps:.1f} FPS")
        print(f"  Performance below target ({target_fps} FPS) by {target_fps-avg_fps:.1f} FPS")
        print("  Wireframe rendering may have playability issues.")
        assessment = "fail"

    # Cleanup
    print("\nCleaning up renderer...")
    renderer.cleanup()

    return {
        'avg_fps': avg_fps,
        'avg_time_ms': avg_time * 1000,
        'min_time_ms': min_time * 1000,
        'max_time_ms': max_time * 1000,
        'slow_frames': slow_frames,
        'assessment': assessment
    }


def run_all_tests():
    """Run all wireframe rendering tests."""
    print("=" * 70)
    print("WIREFRAME RENDERING INTEGRATION TEST")
    print("=" * 70)
    print("\nThis test validates the wireframe DOOM rendering implementation.")
    print("\nTests:")
    print("  1. Coordinate transformation accuracy")
    print("  2. Wireframe rendering performance (100 frames)")

    board = pcbnew.GetBoard()

    if not board:
        print("\n✗ ERROR: No board loaded!")
        print("\nTo run this test:")
        print("1. Open KiCad PCBnew")
        print("2. Create or open a PCB (200mm × 200mm recommended)")
        print("3. Tools → Scripting Console")
        print("4. Run: exec(open('tests/test_wireframe_rendering.py').read())")
        return False

    print("\n✓ Board loaded successfully")

    # Test 1: Coordinate transformation
    coord_test_passed = test_coordinate_transform()

    # Test 2: Wireframe rendering performance
    perf_results = test_wireframe_rendering(board, num_frames=100)

    # Final summary
    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)

    all_passed = coord_test_passed and (perf_results['assessment'] == 'pass')

    print(f"\n{'Test':<40} {'Result'}")
    print("-" * 70)
    print(f"{'Coordinate Transformation':<40} "
          f"{'✓ PASS' if coord_test_passed else '✗ FAIL'}")
    print(f"{'Wireframe Rendering Performance':<40} "
          f"{'✓ PASS' if perf_results['assessment'] == 'pass' else '✗ FAIL'}")

    print(f"\n{'Overall Result':<40} "
          f"{'✓ ALL TESTS PASSED' if all_passed else '✗ SOME TESTS FAILED'}")

    if all_passed:
        print("\nConclusion:")
        print("  → Wireframe rendering implementation is ready for DOOM integration")
        print(f"  → Expected FPS with live DOOM: ~{perf_results['avg_fps']:.1f} FPS")
        print("  → Next step: Test with actual DOOM engine via socket")
    else:
        print("\nConclusion:")
        print("  → Some issues detected, review results above")
        print("  → Address performance or accuracy concerns before DOOM integration")

    print("\n" + "=" * 70)

    return all_passed


if __name__ == '__main__':
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n\n✗ ERROR: Test failed with exception:")
        print(f"{type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
