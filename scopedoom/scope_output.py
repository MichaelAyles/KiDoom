#!/usr/bin/env python3
"""
ScopeDoom - Oscilloscope Audio Output

Draws vector graphics on a hardware oscilloscope using sound card output.
Left channel = X axis, Right channel = Y axis (X-Y mode)

Requirements:
    pip install sounddevice numpy
"""

import numpy as np
import time
import sys

try:
    import sounddevice as sd
except ImportError:
    print("ERROR: sounddevice not installed!")
    print("Install with: pip install sounddevice")
    sys.exit(1)


# Audio configuration
SAMPLE_RATE = 44100  # Hz
AMPLITUDE = 0.8      # Max amplitude (0.0 to 1.0) - don't clip!


class ScopeOutput:
    """Outputs vector graphics to oscilloscope via sound card."""

    def __init__(self, sample_rate=SAMPLE_RATE):
        self.sample_rate = sample_rate
        self.running = False
        self.stream = None
        self.points = []  # List of (x, y) points to draw
        self.current_index = 0

    def set_points(self, points):
        """
        Set the points to draw.

        Args:
            points: List of (x, y) tuples, values should be -1.0 to 1.0
        """
        self.points = points
        self.current_index = 0

    def make_square(self, size=0.8, samples_per_edge=500):
        """
        Generate points for a square.

        Args:
            size: Size of square (0.0 to 1.0)
            samples_per_edge: Number of audio samples per edge
        """
        points = []

        # Four corners
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

        self.points = points
        return points

    def _audio_callback(self, outdata, frames, time_info, status):
        """Called by sounddevice to fill the output buffer."""
        if status:
            print(f"Audio status: {status}")

        if not self.points:
            outdata.fill(0)
            return

        # Fill the buffer with our points
        for i in range(frames):
            idx = (self.current_index + i) % len(self.points)
            x, y = self.points[idx]
            outdata[i, 0] = x * AMPLITUDE  # Left channel = X
            outdata[i, 1] = y * AMPLITUDE  # Right channel = Y

        self.current_index = (self.current_index + frames) % len(self.points)

    def start(self):
        """Start audio output stream."""
        if self.running:
            return

        print(f"[OK] Starting audio output")
        print(f"     Sample rate: {self.sample_rate} Hz")
        print(f"     Points in shape: {len(self.points)}")
        print(f"     Shape frequency: {self.sample_rate / len(self.points):.1f} Hz")

        self.stream = sd.OutputStream(
            samplerate=self.sample_rate,
            channels=2,
            dtype='float32',
            callback=self._audio_callback,
            blocksize=1024
        )
        self.stream.start()
        self.running = True
        print("[OK] Audio stream started")

    def stop(self):
        """Stop audio output stream."""
        if not self.running:
            return

        self.running = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        print("[OK] Audio stream stopped")


def list_audio_devices():
    """List available audio output devices."""
    print("\nAvailable audio devices:")
    print("-" * 60)
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        if dev['max_output_channels'] >= 2:
            marker = " <-- " if i == sd.default.device[1] else ""
            print(f"  [{i}] {dev['name']}{marker}")
    print("-" * 60)
    print(f"Default output: {sd.default.device[1]}")
    print()


def main():
    print("=" * 60)
    print("ScopeDoom - Oscilloscope Square Test")
    print("=" * 60)
    print()
    print("This outputs a square wave pattern to your sound card.")
    print("Connect Left channel to X input, Right channel to Y input")
    print("on your oscilloscope in X-Y mode.")
    print()

    # List devices
    list_audio_devices()

    # Create output
    scope = ScopeOutput()

    # Generate a square
    print("Generating square pattern...")
    scope.make_square(size=0.8, samples_per_edge=500)

    print()
    print("Press Ctrl+C to stop")
    print("=" * 60)

    try:
        scope.start()

        # Keep running until interrupted
        while True:
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n\nStopping...")
    finally:
        scope.stop()

    print("Done.")


if __name__ == '__main__':
    main()
