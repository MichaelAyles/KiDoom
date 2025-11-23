#!/usr/bin/env python3
"""
Object Pool Performance Test (Safe Version)

This benchmark validates that object reuse is significantly faster than
create/destroy cycles. This is critical for achieving playable framerates.

Expected result: Object reuse should be 3-5x faster than create/destroy.

Safe version that avoids sys.exit() crashes on macOS.
"""

import pcbnew
import time


def benchmark_create_destroy_approach(board, num_traces=200, num_frames=50):
    """
    Approach A: Create traces, render, delete all, repeat.
    This is the naive approach we want to avoid.
    """
    print("Testing Approach A: Create/Destroy pattern")
    print(f"  (Create {num_traces} traces, render, delete all, repeat)")

    # Create net
    net = pcbnew.NETINFO_ITEM(board, "APPROACH_A_NET")
    board.Add(net)

    times = []
    trace_spacing = 100000  # 0.1mm

    for frame in range(num_frames):
        start = time.time()

        # Create all traces
        traces = []
        for i in range(num_traces):
            track = pcbnew.PCB_TRACK(board)
            offset = (frame * 10000) % 1000000
            track.SetStart(pcbnew.VECTOR2I(i * trace_spacing + offset, 0))
            track.SetEnd(pcbnew.VECTOR2I(i * trace_spacing + offset, 10000000))
            track.SetWidth(200000)
            track.SetLayer(pcbnew.F_Cu)
            track.SetNet(net)
            board.Add(track)
            traces.append(track)

        # Refresh display
        pcbnew.Refresh()

        # Delete all traces
        for track in traces:
            board.Remove(track)

        elapsed = time.time() - start
        times.append(elapsed)

        if (frame + 1) % 10 == 0:
            print(f"    Frame {frame + 1:2d}/{num_frames}: {elapsed*1000:.2f}ms")

    avg_time = sum(times) / len(times)
    print(f"  Average: {avg_time*1000:.2f}ms per frame ({1.0/avg_time:.1f} FPS)\n")

    return times


def benchmark_object_reuse_approach(board, num_traces=200, num_frames=50):
    """
    Approach B: Create traces once, update positions, repeat.
    This is the object pool approach we'll use in production.
    """
    print("Testing Approach B: Object Reuse pattern (object pool)")
    print(f"  (Create {num_traces} traces once, update positions each frame)")

    # Create net
    net = pcbnew.NETINFO_ITEM(board, "APPROACH_B_NET")
    board.Add(net)

    trace_spacing = 100000  # 0.1mm

    # Pre-allocate all traces (done once, before timing)
    print("  Pre-allocating traces...")
    traces = []
    for i in range(num_traces):
        track = pcbnew.PCB_TRACK(board)
        track.SetWidth(200000)
        track.SetLayer(pcbnew.F_Cu)
        track.SetNet(net)
        board.Add(track)
        traces.append(track)
    print(f"  ✓ {num_traces} traces pre-allocated\n")

    times = []

    for frame in range(num_frames):
        start = time.time()

        # Update positions (reuse existing traces)
        for i, track in enumerate(traces):
            offset = (frame * 10000) % 1000000
            track.SetStart(pcbnew.VECTOR2I(i * trace_spacing + offset, 0))
            track.SetEnd(pcbnew.VECTOR2I(i * trace_spacing + offset, 10000000))

        # Refresh display
        pcbnew.Refresh()

        elapsed = time.time() - start
        times.append(elapsed)

        if (frame + 1) % 10 == 0:
            print(f"    Frame {frame + 1:2d}/{num_frames}: {elapsed*1000:.2f}ms")

    avg_time = sum(times) / len(times)
    print(f"  Average: {avg_time*1000:.2f}ms per frame ({1.0/avg_time:.1f} FPS)\n")

    # Clean up
    for track in traces:
        board.Remove(track)

    return times


def run_benchmark(num_traces=200, num_frames=50):
    """
    Run both benchmarks and compare results.
    """
    print("=" * 70)
    print("Object Pool Performance Benchmark")
    print("=" * 70)
    print(f"\nConfiguration:")
    print(f"  Traces per frame: {num_traces}")
    print(f"  Test frames: {num_frames}")
    print(f"\nThis benchmark compares two approaches:")
    print(f"  A) Create/Destroy: Create traces, render, delete all")
    print(f"  B) Object Reuse: Pre-allocate traces, update positions")
    print()

    board = pcbnew.GetBoard()

    if not board:
        print("ERROR: No board loaded!")
        print("\nTo run this benchmark:")
        print("1. Open KiCad PCBnew")
        print("2. Create or open a PCB")
        print("3. Tools → Scripting Console")
        print("4. Run: exec(open('/Users/tribune/Desktop/KiDoom/tests/benchmark_object_pool_safe.py').read())")
        return None

    print("Board loaded successfully\n")
    print("=" * 70)
    print("APPROACH A: Create/Destroy (Naive Approach)")
    print("=" * 70)
    print()

    times_a = benchmark_create_destroy_approach(board, num_traces, num_frames)

    print("=" * 70)
    print("APPROACH B: Object Reuse (Object Pool Pattern)")
    print("=" * 70)
    print()

    times_b = benchmark_object_reuse_approach(board, num_traces, num_frames)

    # Calculate statistics
    avg_a = sum(times_a) / len(times_a)
    avg_b = sum(times_b) / len(times_b)
    min_a = min(times_a)
    min_b = min(times_b)
    max_a = max(times_a)
    max_b = max(times_b)

    speedup = avg_a / avg_b if avg_b > 0 else 0
    fps_a = 1.0 / avg_a if avg_a > 0 else 0
    fps_b = 1.0 / avg_b if avg_b > 0 else 0

    # Print comparison
    print("=" * 70)
    print("RESULTS COMPARISON")
    print("=" * 70)
    print()
    print(f"{'Metric':<30} {'Approach A':<20} {'Approach B':<20}")
    print("-" * 70)
    print(f"{'Average frame time':<30} {avg_a*1000:>7.2f}ms           {avg_b*1000:>7.2f}ms")
    print(f"{'Min frame time':<30} {min_a*1000:>7.2f}ms           {min_b*1000:>7.2f}ms")
    print(f"{'Max frame time':<30} {max_a*1000:>7.2f}ms           {max_b*1000:>7.2f}ms")
    print(f"{'Average FPS':<30} {fps_a:>7.1f} FPS          {fps_b:>7.1f} FPS")
    print()
    print("=" * 70)
    print("PERFORMANCE GAIN")
    print("=" * 70)
    print(f"\nSpeedup: {speedup:.2f}x faster with object reuse")
    print(f"Time saved per frame: {(avg_a - avg_b)*1000:.2f}ms")
    print(f"FPS improvement: +{fps_b - fps_a:.1f} FPS")

    # Assessment
    print("\n" + "=" * 70)
    print("ASSESSMENT")
    print("=" * 70)

    if speedup >= 3.0:
        print(f"\n✓ EXCELLENT: {speedup:.1f}x speedup achieved!")
        print("  Object pooling provides significant performance benefit.")
        print("  This validates the design decision to use pre-allocated objects.")
    elif speedup >= 2.0:
        print(f"\n~ GOOD: {speedup:.1f}x speedup achieved.")
        print("  Object pooling helps, though less than expected.")
        print("  Still worthwhile for production implementation.")
    else:
        print(f"\n✗ UNEXPECTED: Only {speedup:.1f}x speedup.")
        print("  Object pooling benefit is less than anticipated.")
        print("  May indicate other bottlenecks (refresh time, board complexity).")

    print("\nWhy object pooling matters:")
    print("  - Eliminates Python/C++ allocation overhead")
    print("  - Avoids board object tree modification")
    print("  - Reduces memory fragmentation")
    print("  - Prevents garbage collection pauses")

    print("\nConclusion:")
    if speedup >= 2.0:
        print("  → Use object pool pattern in production DOOM renderer")
        print(f"  → Expected production FPS with pooling: ~{fps_b:.1f} FPS")
    else:
        print("  → Object pooling still recommended despite modest gains")
        print("  → Focus optimization efforts on other areas (display refresh)")

    print("\n" + "=" * 70)
    print("\nBenchmark complete! KiCad should remain stable.")
    print("=" * 70)

    return {
        'avg_time_create_destroy': avg_a * 1000,
        'avg_time_reuse': avg_b * 1000,
        'speedup': speedup,
        'fps_improvement': fps_b - fps_a,
        'fps_a': fps_a,
        'fps_b': fps_b
    }


# Run benchmark
print("Starting object pool benchmark...")
print("NOTE: This may take 2-3 minutes to complete.\n")
result = run_benchmark(num_traces=200, num_frames=50)

if result:
    print(f"\n✓ Benchmark completed successfully!")
    print(f"Final result: {result['speedup']:.2f}x speedup with object pooling")
    print(f"FPS: {result['fps_a']:.1f} (create/destroy) → {result['fps_b']:.1f} (pooling)")
