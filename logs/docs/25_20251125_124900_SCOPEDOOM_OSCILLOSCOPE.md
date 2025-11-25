# ScopeDoom - DOOM on Oscilloscope via Sound Card

**Date:** November 25, 2025
**Status:** WORKING (crunchy but functional!)

---

## Executive Summary

Successfully rendered DOOM wireframe graphics on a hardware oscilloscope using the MacBook Pro's sound card as a dual-channel DAC. Left channel drives X-axis, right channel drives Y-axis in X-Y mode.

---

## Hardware Setup

### Audio Output
- **Source:** MacBook Pro built-in sound card (3.5mm headphone jack)
- **DAC:** Internal audio codec
- **Output impedance:** ~50 ohms typical
- **DC offset:** Significant (Mac audio has capacitor-coupled output with DC bias)

### Signal Conditioning
- **Load resistors:** 1k ohm per channel (L and R)
- **Purpose:** Provide load for headphone output, some level reduction
- **Connection:** Resistor from signal to ground, scope probe across resistor

### Oscilloscope
- **Model:** Siglent SDS1202X-E
- **Mode:** X-Y
- **Channel 1 (X):** Left audio channel
- **Channel 2 (Y):** Right audio channel
- **Vertical scale:** 500mV/div and 20mV/div (adjusted for signal level)
- **Probes:** 10x passive probes
- **Memory depth:** 7k points
- **Timebase:** 20ms (though less relevant in X-Y mode)

### Wiring Diagram
```
MacBook Pro 3.5mm Jack
        |
        +--- Left (Tip) ----[1k]----+---- CH1 (X)
        |                           |
        +--- Right (Ring) --[1k]----+---- CH2 (Y)
        |                           |
        +--- Ground (Sleeve) -------+---- GND
```

---

## Software Architecture

### Signal Flow
```
DOOM Engine (C)
    |
    | drawsegs[] + vissprites[]
    v
Vector Extraction
    |
    | JSON over Unix socket
    v
doom_scope.py
    |
    | Convert to X-Y points
    v
sounddevice (PortAudio)
    |
    | 44.1kHz stereo float32
    v
macOS CoreAudio
    |
    | Analog output
    v
Sound Card DAC
    |
    | L=X, R=Y
    v
Oscilloscope X-Y Mode
```

### Key Files
```
scopedoom/
├── doom_scope.py      # Main DOOM-to-scope renderer
├── scope_output.py    # Standalone audio output test
├── scope_wav_test.py  # WAV file generator (no dependencies)
├── scope_renderer.py  # Pygame wireframe (reference)
└── run_scope.py       # Launcher
```

### Configuration
```python
# Audio
SAMPLE_RATE = 44100    # Hz
AMPLITUDE = 1.0        # Full scale (-1.0 to +1.0)

# Rendering
SAMPLES_PER_LINE = 50  # Samples per wall edge
BLANK_SAMPLES = 5      # Retrace between segments

# Coordinate mapping
DOOM: (0,0) top-left, (320,200) bottom-right
Scope: (-1,-1) to (+1,+1), Y inverted
```

---

## Performance Metrics

### From Test Session
```
FPS: 70.0 | Walls: 34 | Entities: 7 | Points: 6995
```

### Calculated Refresh Rate
- Sample rate: 44,100 Hz
- Points per frame: ~7,000
- **Scope refresh: 44100 / 7000 = 6.3 Hz**

### Brightness vs Complexity Trade-off
- More samples per line = brighter lines but slower refresh
- Fewer samples = faster refresh but dimmer/flickery
- Current setting (50 samples/line) is a compromise

---

## Visual Quality

### Observations
- **"Crunchy"** - Visible stepping/aliasing on diagonal lines
- **DC offset** - Image not centered (Mac audio has DC bias)
- **Retrace visible** - Can see beam moving between segments
- **Recognizable** - DOOM level geometry is clearly visible

### Potential Improvements
1. **DC blocking capacitors** - Remove Mac's DC offset
2. **Reduce points** - Fewer samples for faster refresh
3. **Blanking** - Z-axis control to hide retrace (requires hardware mod)
4. **Higher sample rate** - 96kHz audio interface for more points/second

---

## Code Highlights

### Coordinate Transformation
```python
def doom_to_scope(self, doom_x, doom_y):
    # Normalize to -1 to 1
    x = (doom_x / DOOM_WIDTH) * 2 - 1
    y = (doom_y / DOOM_HEIGHT) * 2 - 1

    # Invert Y (DOOM Y+ is down, scope Y+ is up)
    y = -y

    return x * AMPLITUDE, y * AMPLITUDE
```

### Wall to Points
```python
# Each wall becomes 4 edges (wireframe box)
edges = [
    (sx1, sy1_top, sx2, sy2_top),      # Top
    (sx1, sy1_bottom, sx2, sy2_bottom), # Bottom
    (sx1, sy1_top, sx1, sy1_bottom),   # Left
    (sx2, sy2_top, sx2, sy2_bottom),   # Right
]

for ex1, ey1, ex2, ey2 in edges:
    # Blank move to start
    points.extend(line_to_points(last_x, last_y, ex1, ey1, BLANK_SAMPLES))
    # Draw the line
    points.extend(line_to_points(ex1, ey1, ex2, ey2, SAMPLES_PER_LINE))
```

### Audio Callback
```python
def audio_callback(self, outdata, frames, time_info, status):
    for i in range(frames):
        idx = (self.audio_index + i) % len(points)
        x, y = points[idx]
        outdata[i, 0] = x  # Left = X
        outdata[i, 1] = y  # Right = Y
```

---

## Test Patterns

### Square Test (scope_output.py)
```python
corners = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
# Trace edges between corners
# 400 samples per edge = 1600 total
# Refresh: 44100 / 1600 = 27.6 Hz
```

### Circle Test (scope_wav_test.py)
```python
# Parametric circle
x = cos(t)
y = sin(t)
# 2000 points = 22 Hz refresh
```

---

## Running Instructions

### Quick Test (No DOOM)
```bash
cd scopedoom
python3 scope_wav_test.py      # Generate WAV files
afplay scope_square.wav        # Play square pattern
```

### Full DOOM Setup
```bash
# Terminal 1: Start scope renderer
cd scopedoom
python3 doom_scope.py

# Terminal 2: Launch DOOM
cd /path/to/KiDoom
./run_doom.sh -w 1 1
```

### Controls
- Play DOOM in the SDL window
- Scope displays wireframe in real-time
- WASD to move, arrows to turn, Ctrl to fire

---

## Historical Context

### Inspiration
- **Vectrex DOOM** by Sprite_tm - Vector display DOOM on 1982 hardware
- **Quake on oscilloscope** - YouTube demonstrations
- **Oscilloscope music** - Jerobeam Fenderson, etc.

### Why Sound Card?
- Ubiquitous - every computer has audio output
- Dual channel - stereo = X and Y
- High sample rate - 44.1kHz is plenty for basic graphics
- No special hardware - works with any scope in X-Y mode

---

## Known Issues

1. **DC Offset** - Mac audio has significant DC bias, image off-center
2. **Retrace Lines** - No Z-axis blanking, beam visible between segments
3. **Aliasing** - Limited sample rate causes stepping on diagonals
4. **Brightness Variation** - Lines drawn with more samples appear brighter

---

## Future Enhancements

### Software
- [ ] Optimize point count (reduce samples for faster refresh)
- [ ] Add blanking gaps (longer pause between segments)
- [ ] Sort walls by position to minimize retrace distance
- [ ] Add simple HUD elements (health bar as horizontal line)

### Hardware
- [ ] DC blocking capacitors for centering
- [ ] Proper audio interface (balanced outputs, no DC offset)
- [ ] Z-axis blanking circuit (audio channel 3 via USB interface)
- [ ] Higher sample rate audio interface (96kHz or 192kHz)

---

## Conclusion

Successfully demonstrated DOOM running on a standard oscilloscope using only a MacBook's headphone jack and some resistors. While the image quality is "crunchy" (limited resolution, visible retrace, DC offset), the core concept works and the level geometry is clearly recognizable.

This proves the viability of sound card vector graphics for oscilloscope display, opening possibilities for more sophisticated implementations with proper audio hardware and blanking control.

**Status:** Working proof of concept, ready for refinement.

---

## Equipment List

| Item | Model/Spec | Purpose |
|------|------------|---------|
| Computer | MacBook Pro | DOOM + audio output |
| Oscilloscope | Siglent SDS1202X-E | X-Y display |
| Probes | 10x passive | Signal pickup |
| Resistors | 2x 1k ohm | Load/attenuation |
| Cable | 3.5mm to bare wire | Audio connection |

---

**Document Version:** 1.0
**Author:** Claude + Tribune
**Project:** ScopeDoom (part of KiDoom)
