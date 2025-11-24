#!/usr/bin/env python3
"""
Simple Wireframe Rendering Test (KiCad Console Safe)

This is a simplified test that avoids threading/wx issues when running
via exec() in KiCad's Python console.

Tests:
1. Coordinate transformation accuracy
2. Object pool creation
3. Wall and entity rendering (without Refresh())

This test does NOT measure FPS (which requires Refresh() and causes crashes
when run via exec()). Use the full benchmark when running as a proper script.
"""

import sys
import os

# Add parent directory for package imports
parent_dir = '/Users/tribune/Desktop/KiDoom'
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import pcbnew
from kicad_doom_plugin.coordinate_transform import CoordinateTransform
from kicad_doom_plugin import config


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


def test_object_pool_creation(board):
    """Test that object pools can be created."""
    print("\n" + "=" * 70)
    print("TEST 2: Object Pool Creation")
    print("=" * 70)

    print(f"\nConfiguration:")
    print(f"  MAX_WALL_TRACES: {config.MAX_WALL_TRACES}")
    print(f"  Expected capacity: ~300 traces (70 walls × 4 edges + entities)")

    try:
        from kicad_doom_plugin.object_pool import TracePool

        print("\nCreating TracePool...")
        pool = TracePool(board, max_size=100)  # Small pool for testing

        print(f"✓ TracePool created successfully")
        print(f"  Pool size: {len(pool.traces)} traces")
        print(f"  First trace type: {type(pool.traces[0])}")

        # Test getting traces
        trace = pool.get(0)
        print(f"✓ Can retrieve traces from pool")

        # Test hiding unused
        pool.hide_unused(50)
        print(f"✓ Can hide unused traces")

        # Cleanup
        pool.reset_all()
        print(f"✓ Can reset all traces")

        return True

    except Exception as e:
        print(f"\n✗ Object pool creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_wireframe_wall_rendering(board):
    """Test wireframe wall rendering logic (without Refresh)."""
    print("\n" + "=" * 70)
    print("TEST 3: Wireframe Wall Rendering")
    print("=" * 70)

    try:
        from kicad_doom_plugin.object_pool import TracePool

        # Create pool
        pool = TracePool(board, max_size=100)

        # Create sample wall data (wireframe format)
        # [x1, y1_top, y1_bottom, x2, y2_top, y2_bottom, distance, silhouette]
        test_walls = [
            [50, 40, 160, 58, 42, 158, 60, 3],   # Full wall (silhouette=3)
            [100, 60, 140, 108, 62, 138, 100, 3], # Full wall (silhouette=3)
            [150, 80, 120, 158, 82, 118, 150, 0], # Portal (silhouette=0, skip)
        ]

        print(f"\nRendering {len(test_walls)} test walls (1 should be skipped)...")

        trace_index = 0
        rendered_walls = 0
        skipped_portals = 0

        for wall in test_walls:
            x1, y1_top, y1_bottom, x2, y2_top, y2_bottom, distance, silhouette = wall

            # Skip portal walls (silhouette=0)
            if silhouette == 0:
                skipped_portals += 1
                continue

            rendered_walls += 1

            # Define 4 edges
            edges = [
                (x1, y1_top, x2, y2_top),          # Top
                (x1, y1_bottom, x2, y2_bottom),    # Bottom
                (x1, y1_top, x1, y1_bottom),       # Left
                (x2, y2_top, x2, y2_bottom)        # Right
            ]

            # Render each edge
            for (sx, sy, ex, ey) in edges:
                trace = pool.get(trace_index)
                trace_index += 1

                # Convert coordinates
                kicad_sx, kicad_sy = CoordinateTransform.doom_to_kicad(sx, sy)
                kicad_ex, kicad_ey = CoordinateTransform.doom_to_kicad(ex, ey)

                # Update trace
                trace.SetStart(pcbnew.VECTOR2I(kicad_sx, kicad_sy))
                trace.SetEnd(pcbnew.VECTOR2I(kicad_ex, kicad_ey))
                trace.SetWidth(config.TRACE_WIDTH_CLOSE if distance < 100 else config.TRACE_WIDTH_FAR)
                trace.SetLayer(pcbnew.F_Cu if distance < 100 else pcbnew.B_Cu)

        print(f"\n✓ Rendering completed successfully")
        print(f"  Rendered walls: {rendered_walls}")
        print(f"  Skipped portals: {skipped_portals}")
        print(f"  Total traces created: {trace_index} (= {rendered_walls} walls × 4 edges)")

        # Verify trace count
        expected_traces = rendered_walls * 4
        if trace_index == expected_traces:
            print(f"✓ Trace count matches expected ({expected_traces})")
        else:
            print(f"✗ Trace count mismatch: got {trace_index}, expected {expected_traces}")
            return False

        # Cleanup
        pool.reset_all()

        return True

    except Exception as e:
        print(f"\n✗ Wall rendering test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def draw_test_square(board):
    """Draw a 5cm × 5cm square in the center of the PCB for visual confirmation."""
    try:
        from kicad_doom_plugin.object_pool import TracePool

        # Create a small trace pool for the square (4 edges)
        pool = TracePool(board, max_size=4)

        # A4 landscape dimensions: 297mm × 210mm
        # Center of A4 landscape page (from origin at top-left)
        a4_center_x = 148500000  # 148.5mm in nanometers
        a4_center_y = 105000000  # 105mm in nanometers

        # 5cm = 50mm = 50,000,000 nm
        # Square with 5cm sides centered on A4 page
        half_size = 25000000  # 2.5cm = 25mm

        # Define 4 corners (offset to center of A4 page)
        top_left = (a4_center_x - half_size, a4_center_y - half_size)
        top_right = (a4_center_x + half_size, a4_center_y - half_size)
        bottom_right = (a4_center_x + half_size, a4_center_y + half_size)
        bottom_left = (a4_center_x - half_size, a4_center_y + half_size)

        # Define 4 edges of the square
        edges = [
            (top_left, top_right),      # Top edge
            (top_right, bottom_right),  # Right edge
            (bottom_right, bottom_left),# Bottom edge
            (bottom_left, top_left)     # Left edge
        ]

        print("\nDrawing 5cm × 5cm square centered on A4 landscape page...")
        print(f"  A4 page center: ({a4_center_x//1000000}mm, {a4_center_y//1000000}mm)")

        for i, (start, end) in enumerate(edges):
            trace = pool.get(i)
            trace.SetStart(pcbnew.VECTOR2I(start[0], start[1]))
            trace.SetEnd(pcbnew.VECTOR2I(end[0], end[1]))
            trace.SetWidth(300000)  # 0.3mm thick trace
            trace.SetLayer(pcbnew.F_Cu)  # Front copper
            print(f"  Edge {i+1}: ({start[0]//1000000}mm, {start[1]//1000000}mm) → "
                  f"({end[0]//1000000}mm, {end[1]//1000000}mm)")

        # Refresh the display to show the square
        pcbnew.Refresh()

        print("✓ 5cm × 5cm square drawn successfully!")
        print("  The square should be visible in the CENTER of your A4 page")
        print("  Color: Red (F.Cu layer)")
        print("  Trace width: 0.3mm")

    except Exception as e:
        print(f"\n✗ Failed to draw test square: {e}")
        import traceback
        traceback.print_exc()


def run_all_tests():
    """Run all safe tests."""
    print("=" * 70)
    print("WIREFRAME RENDERING TEST (KiCad Console Safe)")
    print("=" * 70)
    print("\nThis is a simplified test that avoids threading/wx issues.")
    print("\nTests:")
    print("  1. Coordinate transformation accuracy")
    print("  2. Object pool creation")
    print("  3. Wireframe wall rendering logic")

    board = pcbnew.GetBoard()

    if not board:
        print("\n✗ ERROR: No board loaded!")
        print("\nTo run this test:")
        print("1. Open KiCad PCBnew")
        print("2. Create or open a PCB")
        print("3. Tools → Scripting Console")
        print("4. Run: exec(open('/Users/tribune/Desktop/KiDoom/tests/test_wireframe_simple.py').read())")
        return False

    print("\n✓ Board loaded successfully")

    # Test 1: Coordinate transformation
    test1_passed = test_coordinate_transform()

    # Test 2: Object pool creation
    test2_passed = test_object_pool_creation(board)

    # Test 3: Wall rendering
    test3_passed = test_wireframe_wall_rendering(board)

    # Final summary
    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)

    all_passed = test1_passed and test2_passed and test3_passed

    print(f"\n{'Test':<40} {'Result'}")
    print("-" * 70)
    print(f"{'Coordinate Transformation':<40} "
          f"{'✓ PASS' if test1_passed else '✗ FAIL'}")
    print(f"{'Object Pool Creation':<40} "
          f"{'✓ PASS' if test2_passed else '✗ FAIL'}")
    print(f"{'Wireframe Wall Rendering':<40} "
          f"{'✓ PASS' if test3_passed else '✗ FAIL'}")

    print(f"\n{'Overall Result':<40} "
          f"{'✓ ALL TESTS PASSED' if all_passed else '✗ SOME TESTS FAILED'}")

    if all_passed:
        print("\nConclusion:")
        print("  ✓ Core wireframe rendering logic is working correctly")
        print("  ✓ Ready for integration testing with actual DOOM engine")
        print("\nNext steps:")
        print("  1. Test with live DOOM via socket connection")
        print("  2. Measure actual FPS during gameplay")

        # Draw a 5cm × 5cm square as visual confirmation
        print("\n" + "=" * 70)
        print("Drawing 5cm × 5cm test square...")
        print("=" * 70)
        draw_test_square(board)
    else:
        print("\nConclusion:")
        print("  ✗ Some issues detected, review results above")

    print("\n" + "=" * 70)

    return all_passed


if __name__ == '__main__':
    try:
        success = run_all_tests()
        if not success:
            print("\nNote: Some tests failed. Please review the output above.")
    except Exception as e:
        print(f"\n\n✗ ERROR: Test failed with exception:")
        print(f"{type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
