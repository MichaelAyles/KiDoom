#!/usr/bin/env python3
"""
Phase 0 Benchmark: KiCad Refresh Performance Test (Safe Version)

This version avoids sys.exit() which can crash KiCad on macOS.
Run this in KiCad's scripting console after creating a blank PCB.
"""

import pcbnew
import time


def benchmark_trace_creation_and_refresh(num_traces=200, num_frames=100):
    """
    Creates N traces, modifies them, and measures refresh time.
    This tells us if our 20 FPS target is realistic.
    """
    print("=" * 70)
    print("KiDoom Phase 0 Benchmark: PCB Refresh Performance")
    print("=" * 70)
    print(f"\nConfiguration:")
    print(f"  Traces per frame: {num_traces}")
    print(f"  Test frames: {num_frames}")
    print(f"\nThis benchmark measures the time to update {num_traces} traces and")
    print(f"refresh the display, repeated {num_frames} times.\n")

    board = pcbnew.GetBoard()

    if not board:
        print("ERROR: No board loaded!")
        print("\nTo run this benchmark:")
        print("1. Open KiCad PCBnew")
        print("2. Create a new PCB (File → New → Project)")
        print("3. Set board size to 200mm × 200mm (recommended)")
        print("4. Tools → Scripting Console")
        print("5. Run: exec(open('tests/benchmark_refresh_safe.py').read())")
        return None

    print("Board loaded successfully")
    print(f"Board: {board.GetFileName() or 'Untitled'}")
    print(f"\nStep 1/3: Creating {num_traces} pre-allocated traces...")

    # Create single net for all traces (eliminates ratsnest calculation)
    doom_net = pcbnew.NETINFO_ITEM(board, "BENCHMARK_NET")
    board.Add(doom_net)

    # Pre-allocate all traces (object pool pattern)
    traces = []
    trace_spacing = 100000  # 0.1mm spacing between traces

    creation_start = time.time()
    for i in range(num_traces):
        track = pcbnew.PCB_TRACK(board)
        track.SetStart(pcbnew.VECTOR2I(i * trace_spacing, 0))
        track.SetEnd(pcbnew.VECTOR2I(i * trace_spacing, 10000000))  # 10mm long
        track.SetWidth(200000)  # 0.2mm width
        track.SetLayer(pcbnew.F_Cu)
        track.SetNet(doom_net)
        board.Add(track)
        traces.append(track)

    creation_time = time.time() - creation_start
    print(f"✓ Created {num_traces} traces in {creation_time*1000:.2f}ms")
    print(f"  Average: {creation_time/num_traces*1000:.3f}ms per trace")

    # Initial refresh to ensure everything is rendered
    print(f"\nStep 2/3: Initial refresh...")
    initial_refresh_start = time.time()
    pcbnew.Refresh()
    initial_refresh_time = time.time() - initial_refresh_start
    print(f"✓ Initial refresh: {initial_refresh_time*1000:.2f}ms")

    print(f"\nStep 3/3: Benchmarking {num_frames} frames with trace updates...")
    print("(This simulates animated DOOM gameplay)\n")

    # Benchmark: modify and refresh multiple times
    refresh_times = []
    update_times = []
    total_times = []

    for frame in range(num_frames):
        frame_start = time.time()

        # Modify traces (simulate animation)
        update_start = time.time()
        for i, track in enumerate(traces):
            # Move traces slightly each frame (simulates wall movement)
            offset = (frame * 10000) % 1000000
            track.SetStart(pcbnew.VECTOR2I(i * trace_spacing + offset, 0))
            track.SetEnd(pcbnew.VECTOR2I(i * trace_spacing + offset, 10000000))

            # Alternate layer to test layer switching
            if frame % 2 == 0:
                track.SetLayer(pcbnew.F_Cu)
            else:
                track.SetLayer(pcbnew.B_Cu)

        update_time = time.time() - update_start
        update_times.append(update_time)

        # Refresh display (this is the critical bottleneck)
        refresh_start = time.time()
        pcbnew.Refresh()
        refresh_time = time.time() - refresh_start
        refresh_times.append(refresh_time)

        total_time = time.time() - frame_start
        total_times.append(total_time)

        # Progress indicator every 10 frames
        if (frame + 1) % 10 == 0:
            avg_so_far = sum(total_times) / len(total_times)
            fps_so_far = 1.0 / avg_so_far if avg_so_far > 0 else 0
            print(f"  Frame {frame + 1:3d}/{num_frames}: {total_time*1000:6.2f}ms "
                  f"(avg: {avg_so_far*1000:6.2f}ms, {fps_so_far:5.1f} FPS)")

    # Calculate statistics
    avg_update = sum(update_times) / len(update_times)
    avg_refresh = sum(refresh_times) / len(refresh_times)
    avg_total = sum(total_times) / len(total_times)
    min_total = min(total_times)
    max_total = max(total_times)

    # Calculate percentiles
    sorted_times = sorted(total_times)
    p95_total = sorted_times[int(len(sorted_times) * 0.95)]
    p99_total = sorted_times[int(len(sorted_times) * 0.99)]

    avg_fps = 1.0 / avg_total if avg_total > 0 else 0
    min_fps = 1.0 / max_total if max_total > 0 else 0
    max_fps = 1.0 / min_total if min_total > 0 else 0

    # Print results
    print("\n" + "=" * 70)
    print("BENCHMARK RESULTS")
    print("=" * 70)
    print(f"\nTiming breakdown:")
    print(f"  Trace updates:    {avg_update*1000:7.2f}ms average")
    print(f"  Display refresh:  {avg_refresh*1000:7.2f}ms average")
    print(f"  Total frame time: {avg_total*1000:7.2f}ms average")
    print(f"\nFrame time statistics:")
    print(f"  Minimum:  {min_total*1000:7.2f}ms ({max_fps:5.1f} FPS)")
    print(f"  Average:  {avg_total*1000:7.2f}ms ({avg_fps:5.1f} FPS)")
    print(f"  Maximum:  {max_total*1000:7.2f}ms ({min_fps:5.1f} FPS)")
    print(f"  95th percentile: {p95_total*1000:7.2f}ms")
    print(f"  99th percentile: {p99_total*1000:7.2f}ms")

    # Performance assessment
    print("\n" + "=" * 70)
    print("PERFORMANCE ASSESSMENT")
    print("=" * 70)

    if avg_total < 0.050:  # < 50ms
        assessment = "EXCELLENT"
        color = "✓"
        recommendation = "Proceed with full DOOM implementation with confidence!"
        expected_gameplay = "Smooth gameplay (20+ FPS) is very likely."
    elif avg_total < 0.100:  # 50-100ms
        assessment = "PLAYABLE"
        color = "~"
        recommendation = "Proceed with caution. Gameplay will be playable but not smooth."
        expected_gameplay = "Expect 10-20 FPS during actual gameplay."
    else:  # > 100ms
        assessment = "TOO SLOW"
        color = "✗"
        recommendation = "Consider optimizations or alternative approaches."
        expected_gameplay = "Gameplay may be too slow (< 10 FPS) to be enjoyable."

    print(f"\n{color} Assessment: {assessment}")
    print(f"  Target FPS: {avg_fps:.1f} FPS")
    print(f"  {recommendation}")
    print(f"  {expected_gameplay}")

    # Additional insights
    print("\nBottleneck analysis:")
    refresh_pct = (avg_refresh / avg_total) * 100
    update_pct = (avg_update / avg_total) * 100
    print(f"  Display refresh: {refresh_pct:5.1f}% of frame time")
    print(f"  Trace updates:   {update_pct:5.1f}% of frame time")

    if refresh_pct > 80:
        print("\n  → Display refresh is the primary bottleneck (expected)")
        print("     Optimization: Ensure grid, ratsnest, and antialiasing are disabled")

    if update_pct > 50:
        print("\n  → Trace updates are taking significant time")
        print("     This may indicate slow Python/C++ interface or excessive GC")

    # Recommendations
    print("\n" + "=" * 70)
    print("OPTIMIZATION CHECKLIST")
    print("=" * 70)
    print("\nEnsure the following are configured for best performance:")
    print("  [ ] View → Show Grid: OFF")
    print("  [ ] View → Ratsnest: OFF")
    print("  [ ] Preferences → Display Options → Clearance outlines: OFF")
    print("  [ ] Preferences → Display Options → Pad/Via holes: Do not show")
    print("  [ ] Preferences → Graphics → Antialiasing: Fast or Disabled")
    print("  [ ] Preferences → Graphics → Rendering engine: Accelerated")
    print("  [ ] Board layers: Only F.Cu and B.Cu enabled (2-layer board)")
    print("\nIf these are already configured and performance is poor, try:")
    print("  - Reducing trace count (test with 100 instead of 200)")
    print("  - Closing other applications to free RAM")
    print("  - Updating GPU drivers")
    print("  - Running on AC power (not battery)")

    print("\n" + "=" * 70)
    print("\nBenchmark complete! KiCad should remain stable.")
    print("Results saved above. You can now close the scripting console.")
    print("=" * 70)

    return {
        'avg_total_ms': avg_total * 1000,
        'avg_fps': avg_fps,
        'min_fps': min_fps,
        'max_fps': max_fps,
        'assessment': assessment
    }


# Run benchmark when script is executed
print("Starting benchmark...")
print("NOTE: This may take 30-60 seconds to complete.\n")
result = benchmark_trace_creation_and_refresh()

if result:
    print(f"\n✓ Benchmark completed successfully!")
    print(f"Final result: {result['avg_fps']:.1f} FPS ({result['assessment']})")
