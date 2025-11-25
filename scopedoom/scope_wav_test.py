#!/usr/bin/env python3
"""
ScopeDoom - WAV File Test

Generates a WAV file with a square pattern for oscilloscope testing.
No additional dependencies required (uses built-in wave module).

Usage:
    python3 scope_wav_test.py
    # Play the generated scope_square.wav through your sound card
    # with Left -> X and Right -> Y on your scope in X-Y mode
"""

import wave
import struct
import math


# Audio configuration
SAMPLE_RATE = 44100  # Hz
DURATION = 5.0       # Seconds
AMPLITUDE = 0.8      # Max amplitude (0.0 to 1.0)


def generate_square_points(size=0.8, samples_per_edge=500):
    """
    Generate points for a square.

    Returns list of (x, y) tuples, values -1.0 to 1.0
    """
    points = []

    # Four corners (counter-clockwise)
    corners = [
        (-size, -size),  # Bottom-left
        (size, -size),   # Bottom-right
        (size, size),    # Top-right
        (-size, size),   # Top-left
    ]

    # Generate points along each edge
    for i in range(4):
        start = corners[i]
        end = corners[(i + 1) % 4]

        for t in range(samples_per_edge):
            progress = t / samples_per_edge
            x = start[0] + (end[0] - start[0]) * progress
            y = start[1] + (end[1] - start[1]) * progress
            points.append((x, y))

    return points


def generate_circle_points(radius=0.8, num_points=2000):
    """
    Generate points for a circle.

    Returns list of (x, y) tuples, values -1.0 to 1.0
    """
    points = []
    for i in range(num_points):
        angle = 2 * math.pi * i / num_points
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        points.append((x, y))
    return points


def write_wav(filename, points, sample_rate=SAMPLE_RATE, duration=DURATION, amplitude=AMPLITUDE):
    """
    Write points to a stereo WAV file.

    Left channel = X, Right channel = Y
    """
    total_samples = int(sample_rate * duration)
    num_points = len(points)

    print(f"Generating {filename}...")
    print(f"  Sample rate: {sample_rate} Hz")
    print(f"  Duration: {duration} seconds")
    print(f"  Total samples: {total_samples}")
    print(f"  Points in shape: {num_points}")
    print(f"  Shape frequency: {sample_rate / num_points:.1f} Hz")
    print(f"  Shape repetitions: {total_samples / num_points:.1f}")

    with wave.open(filename, 'w') as wav:
        wav.setnchannels(2)        # Stereo
        wav.setsampwidth(2)        # 16-bit
        wav.setframerate(sample_rate)

        for i in range(total_samples):
            # Get point (loop through shape)
            idx = i % num_points
            x, y = points[idx]

            # Scale to 16-bit signed integer range
            left = int(x * amplitude * 32767)
            right = int(y * amplitude * 32767)

            # Clamp
            left = max(-32767, min(32767, left))
            right = max(-32767, min(32767, right))

            # Pack as little-endian signed 16-bit
            wav.writeframes(struct.pack('<hh', left, right))

    print(f"[OK] Written: {filename}")


def main():
    print("=" * 60)
    print("ScopeDoom - WAV File Generator")
    print("=" * 60)
    print()
    print("This generates WAV files for oscilloscope X-Y mode testing.")
    print("Play the WAV file through your sound card with:")
    print("  Left channel  -> X input")
    print("  Right channel -> Y input")
    print()
    print("-" * 60)

    # Generate square
    print("\n[1] Generating SQUARE pattern...")
    square_points = generate_square_points(size=0.8, samples_per_edge=500)
    write_wav("scope_square.wav", square_points)

    # Generate circle
    print("\n[2] Generating CIRCLE pattern...")
    circle_points = generate_circle_points(radius=0.8, num_points=2000)
    write_wav("scope_circle.wav", circle_points)

    print()
    print("=" * 60)
    print("Done! Play these files to test your oscilloscope setup:")
    print("  - scope_square.wav  (square pattern)")
    print("  - scope_circle.wav  (circle pattern)")
    print()
    print("On macOS: afplay scope_square.wav")
    print("On Linux: aplay scope_square.wav")
    print("=" * 60)


if __name__ == '__main__':
    main()
