# KiDoom Benchmarks

This directory contains performance benchmarks to validate the feasibility of running DOOM on KiCad PCB traces.

## Overview

These benchmarks should be run **before** implementing the full DOOM integration to validate core performance assumptions.

## Benchmarks

### 1. `benchmark_refresh.py` - Phase 0 Critical Test ⭐

**Purpose:** Measures KiCad's display refresh performance with ~200 PCB traces.

**What it tests:**
- Time to update 200 trace positions
- Time to refresh the KiCad display
- Overall frame time and FPS estimate

**Success criteria:**
- < 50ms per frame = **Excellent** (20+ FPS) - Proceed with confidence
- 50-100ms per frame = **Playable** (10-20 FPS) - Proceed with caution
- \> 100ms per frame = **Too slow** (< 10 FPS) - Reconsider approach

**How to run:**
```python
# In KiCad PCBnew:
# 1. Create a new PCB (200mm × 200mm recommended)
# 2. Apply performance settings (see README.md)
# 3. Tools → Scripting Console
# 4. Run:
exec(open('tests/benchmark_refresh.py').read())
```

**Expected output:**
```
BENCHMARK RESULTS
==================================================================
Frame time statistics:
  Minimum:   32.45ms (30.8 FPS)
  Average:   42.18ms (23.7 FPS)
  Maximum:   58.21ms (17.2 FPS)

✓ Assessment: EXCELLENT
  Target FPS: 23.7 FPS
  Proceed with full DOOM implementation with confidence!
```

---

### 2. `benchmark_object_pool.py` - Object Reuse Test

**Purpose:** Validates that object reuse is faster than create/destroy cycles.

**What it tests:**
- Approach A: Create traces → render → delete → repeat
- Approach B: Pre-allocate traces → update positions → repeat
- Speedup factor (A vs B)

**Success criteria:**
- 3-5x speedup = **Expected** - Confirms object pooling is critical
- 2-3x speedup = **Acceptable** - Still worthwhile
- < 2x speedup = **Unexpected** - May indicate other bottlenecks

**How to run:**
```python
# In KiCad PCBnew:
# 1. Open a PCB
# 2. Tools → Scripting Console
# 3. Run:
exec(open('tests/benchmark_object_pool.py').read())
```

**Expected output:**
```
PERFORMANCE GAIN
==================================================================
Speedup: 4.2x faster with object reuse
Time saved per frame: 38.5ms
FPS improvement: +12.3 FPS

✓ EXCELLENT: 4.2x speedup achieved!
```

---

### 3. `benchmark_socket.py` - IPC Latency Test

**Purpose:** Measures Unix socket communication overhead between C DOOM and Python.

**What it tests:**
- Time to send frame data (JSON) over Unix socket
- Round-trip latency
- Throughput (frames per second)

**Success criteria:**
- < 5ms latency = **Excellent** - Socket overhead negligible
- 5-10ms latency = **Acceptable** - Measurable but not critical
- \> 10ms latency = **Concerning** - May need optimization

**How to run:**
```bash
# Standalone (doesn't require KiCad)
python3 tests/benchmark_socket.py
```

**Expected output:**
```
PERFORMANCE ASSESSMENT
==================================================================
✓ Assessment: EXCELLENT
  Average latency: 1.234ms
  Socket communication overhead is negligible.
  Socket IPC will not be a bottleneck for DOOM rendering.
```

---

## Running All Benchmarks

### Automated Run (recommended)

```bash
# Run socket benchmark (standalone)
python3 tests/benchmark_socket.py

# Run KiCad benchmarks (in KiCad scripting console)
exec(open('tests/run_all_kicad_benchmarks.py').read())
```

### Manual Run

1. **Socket benchmark** (run first, no KiCad needed):
   ```bash
   python3 tests/benchmark_socket.py
   ```

2. **KiCad benchmarks** (requires KiCad PCBnew):
   - Open KiCad PCBnew
   - Create a new PCB (200mm × 200mm)
   - Apply performance settings (see below)
   - Tools → Scripting Console
   - Run refresh benchmark:
     ```python
     exec(open('tests/benchmark_refresh.py').read())
     ```
   - Run object pool benchmark:
     ```python
     exec(open('tests/benchmark_object_pool.py').read())
     ```

---

## KiCad Performance Settings

**CRITICAL:** These settings must be applied before running benchmarks for accurate results.

### Required Settings

1. **View Menu:**
   - [ ] View → Show Grid: **OFF**
   - [ ] View → Ratsnest: **OFF**

2. **Preferences → PCB Editor → Display Options:**
   - [ ] Clearance outlines: **OFF**
   - [ ] Pad/Via holes: **Do not show**

3. **Preferences → Common → Graphics:**
   - [ ] Antialiasing: **Fast** or **Disabled**
   - [ ] Rendering engine: **Accelerated**

4. **Board Configuration:**
   - [ ] 2-layer board (F.Cu + B.Cu only)
   - [ ] Board size: 200mm × 200mm

### Why These Settings Matter

| Setting | Performance Impact | Why |
|---------|-------------------|-----|
| Grid display | 5-10% per frame | Grid recalculated every frame |
| Ratsnest | 20-30% per frame | Airwire calculation for all nets |
| Antialiasing | 5-15% per frame | MSAA adds GPU overhead |
| Clearance outlines | 10-20% per frame | DRC visualization |
| Minimal layers | 30-40% speedup | Each layer adds rendering cost |

**Without these settings, benchmarks will show 2-5x slower performance!**

---

## Interpreting Results

### Refresh Benchmark

| Result | Interpretation | Action |
|--------|---------------|--------|
| 20-30 FPS | Excellent | Proceed with full implementation |
| 10-20 FPS | Playable | Proceed, expect slightly choppy gameplay |
| 5-10 FPS | Marginal | Consider optimizations or accept poor performance |
| < 5 FPS | Too slow | Check settings, hardware, or reconsider approach |

### Object Pool Benchmark

| Result | Interpretation | Action |
|--------|---------------|--------|
| 3-5x speedup | Expected | Use object pooling in production |
| 2-3x speedup | Acceptable | Still use object pooling |
| < 2x speedup | Unexpected | May indicate refresh is the primary bottleneck |

### Socket Benchmark

| Result | Interpretation | Action |
|--------|---------------|--------|
| < 5ms | Negligible | No IPC optimization needed |
| 5-10ms | Measurable | Acceptable, monitor in production |
| > 10ms | Significant | Consider binary format or shared memory |

---

## Troubleshooting

### Benchmark shows poor performance

1. **Verify settings:** Double-check all performance settings listed above
2. **Check hardware:** Close other applications, ensure AC power
3. **Update drivers:** Ensure GPU drivers are current
4. **Test with fewer objects:** Try `num_traces=100` instead of 200

### "No board loaded" error

```python
# Create a new board first:
# File → New → Project
# Then run benchmark
```

### Socket benchmark fails to connect

```bash
# Remove stale socket file
rm /tmp/kidoom_benchmark.sock

# Run again
python3 tests/benchmark_socket.py
```

### Python import errors

```bash
# Install dependencies
pip install pynput psutil
```

---

## Benchmark Data

After running benchmarks, save results for reference:

```bash
# Create results file
cat > tests/benchmark_results.txt << EOF
Date: $(date)
Hardware: [Your hardware here]
KiCad Version: [Version]

Refresh Benchmark:
  Average FPS: [X.X] FPS
  Frame time: [XX.XX]ms

Object Pool Benchmark:
  Speedup: [X.X]x
  FPS improvement: [+X.X] FPS

Socket Benchmark:
  Latency: [X.XX]ms
  Assessment: [EXCELLENT/ACCEPTABLE/CONCERNING]
EOF
```

This helps track performance across different machines and KiCad versions.

---

## Next Steps

After running benchmarks:

1. **If all benchmarks pass:** Proceed to Phase 1 (DOOM engine integration)
2. **If refresh benchmark fails:** Optimize settings or adjust expectations
3. **If object pool shows low speedup:** Focus on refresh optimization instead
4. **If socket benchmark fails:** Consider alternative IPC methods

See `../CLAUDE.md` for full implementation plan.
