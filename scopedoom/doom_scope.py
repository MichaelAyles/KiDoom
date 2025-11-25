#!/usr/bin/env python3
"""
ScopeDoom - DOOM on Oscilloscope

Renders DOOM wireframe graphics on a hardware oscilloscope via sound card.
Left channel = X, Right channel = Y (X-Y mode)

Usage:
    1. Run this script: python3 doom_scope.py
    2. In another terminal: ./run_doom.sh dual -w 1 1
    3. Connect sound card L/R to scope X/Y inputs
"""

import socket
import struct
import json
import threading
import numpy as np
import time
import sys
import os

try:
    import sounddevice as sd
except ImportError:
    print("ERROR: sounddevice not installed!")
    print("Install with: pip install sounddevice numpy")
    sys.exit(1)

# Socket configuration
SOCKET_PATH = "/tmp/kicad_doom.sock"

# Message types (must match DOOM)
MSG_FRAME_DATA = 0x01
MSG_KEY_EVENT = 0x02
MSG_INIT_COMPLETE = 0x03
MSG_SHUTDOWN = 0x04

# Audio configuration
SAMPLE_RATE = 44100  # Standard rate - most stable
AMPLITUDE = 1.0  # Full scale

# DOOM screen dimensions
DOOM_WIDTH = 320
DOOM_HEIGHT = 200

# Rendering config
SAMPLES_PER_LINE = 30  # Samples per wall edge (more = brighter but slower)
BLANK_SAMPLES = 3       # Samples to move between disconnected lines (retrace)


class DoomScope:
    """Renders DOOM on oscilloscope via sound card."""

    def __init__(self):
        self.running = False
        self.socket = None
        self.client_socket = None

        # Current frame data
        self.current_frame = None
        self.frame_lock = threading.Lock()

        # Audio output
        self.audio_points = []
        self.audio_lock = threading.Lock()
        self.stream = None
        self.audio_index = 0

        # Stats
        self.frame_count = 0
        self.last_frame_time = time.time()

    def doom_to_scope(self, doom_x, doom_y):
        """
        Convert DOOM coordinates to oscilloscope coordinates.

        DOOM: (0,0) top-left, (320,200) bottom-right
        Scope: (-1,-1) to (1,1), with Y inverted (scope Y+ is up)
        """
        # Normalize to -1 to 1
        x = (doom_x / DOOM_WIDTH) * 2 - 1
        y = (doom_y / DOOM_HEIGHT) * 2 - 1

        # Invert Y (DOOM Y+ is down, scope Y+ is up)
        y = -y

        # Clamp
        x = max(-1, min(1, x))
        y = max(-1, min(1, y))

        return x * AMPLITUDE, y * AMPLITUDE

    def line_to_points(self, x1, y1, x2, y2, num_samples):
        """Generate points along a line."""
        points = []
        for i in range(num_samples):
            t = i / max(1, num_samples - 1)
            x = x1 + (x2 - x1) * t
            y = y1 + (y2 - y1) * t
            points.append((x, y))
        return points

    def frame_to_points(self, frame):
        """Convert a DOOM frame to oscilloscope points."""
        points = []

        walls = frame.get('walls', [])
        entities = frame.get('entities', [])

        # Sort by distance (far to near) so closer walls are drawn last (brighter)
        all_objects = []

        for wall in walls:
            if isinstance(wall, list) and len(wall) >= 7:
                distance = wall[6]
                silhouette = wall[7] if len(wall) >= 8 else 3
                if silhouette == 0:  # Skip portals
                    continue
                all_objects.append(('wall', distance, wall))

        for entity in entities:
            distance = entity.get('distance', 100)
            all_objects.append(('entity', distance, entity))

        # Sort far to near
        all_objects.sort(key=lambda x: x[1], reverse=True)

        last_x, last_y = 0, 0

        for obj_type, distance, obj_data in all_objects:
            if obj_type == 'wall':
                wall = obj_data
                x1, y1_top, y1_bottom, x2, y2_top, y2_bottom = wall[:6]

                # Convert to scope coordinates
                sx1, sy1_top = self.doom_to_scope(x1, y1_top)
                sx1, sy1_bottom = self.doom_to_scope(x1, y1_bottom)
                sx2, sy2_top = self.doom_to_scope(x2, y2_top)
                sx2, sy2_bottom = self.doom_to_scope(x2, y2_bottom)

                # Draw 4 edges of the wall as wireframe
                edges = [
                    (sx1, sy1_top, sx2, sy2_top),      # Top
                    (sx1, sy1_bottom, sx2, sy2_bottom), # Bottom
                    (sx1, sy1_top, sx1, sy1_bottom),   # Left
                    (sx2, sy2_top, sx2, sy2_bottom),   # Right
                ]

                for ex1, ey1, ex2, ey2 in edges:
                    # Blank move to start of line
                    if points:
                        points.extend(self.line_to_points(last_x, last_y, ex1, ey1, BLANK_SAMPLES))

                    # Draw the line
                    points.extend(self.line_to_points(ex1, ey1, ex2, ey2, SAMPLES_PER_LINE))
                    last_x, last_y = ex2, ey2

            elif obj_type == 'entity':
                entity = obj_data
                x = entity['x']
                y_top = entity['y_top']
                y_bottom = entity['y_bottom']

                # Calculate width based on height
                height = y_bottom - y_top
                width = max(5, height * 0.6)

                x_left = x - width / 2
                x_right = x + width / 2

                # Convert to scope coordinates
                sx_left, sy_top = self.doom_to_scope(x_left, y_top)
                sx_right, sy_bottom = self.doom_to_scope(x_right, y_bottom)
                sx_left, sy_bottom_left = self.doom_to_scope(x_left, y_bottom)
                sx_right, sy_top_right = self.doom_to_scope(x_right, y_top)

                # Draw rectangle for entity
                edges = [
                    (sx_left, sy_top, sx_right, sy_top_right),       # Top
                    (sx_right, sy_top_right, sx_right, sy_bottom),   # Right
                    (sx_right, sy_bottom, sx_left, sy_bottom_left),  # Bottom
                    (sx_left, sy_bottom_left, sx_left, sy_top),      # Left
                ]

                for ex1, ey1, ex2, ey2 in edges:
                    if points:
                        points.extend(self.line_to_points(last_x, last_y, ex1, ey1, BLANK_SAMPLES))
                    points.extend(self.line_to_points(ex1, ey1, ex2, ey2, SAMPLES_PER_LINE // 2))
                    last_x, last_y = ex2, ey2

        # If no points, draw a small dot at center
        if not points:
            points = [(0, 0)] * 1000

        return points

    def audio_callback(self, outdata, frames, time_info, status):
        """Called by sounddevice to fill audio buffer."""
        if status:
            print(f"Audio status: {status}")

        with self.audio_lock:
            points = self.audio_points

        if not points:
            outdata.fill(0)
            return

        for i in range(frames):
            idx = (self.audio_index + i) % len(points)
            x, y = points[idx]
            outdata[i, 0] = x  # Left = X
            outdata[i, 1] = y  # Right = Y

        self.audio_index = (self.audio_index + frames) % len(points)

    def start_audio(self):
        """Start audio output stream."""
        # Start with a simple square while waiting for DOOM
        self.audio_points = []
        size = 0.5
        for corner in [(-size, -size), (size, -size), (size, size), (-size, size), (-size, -size)]:
            self.audio_points.extend([corner] * 200)

        self.stream = sd.OutputStream(
            samplerate=SAMPLE_RATE,
            channels=2,
            dtype='float32',
            callback=self.audio_callback,
            blocksize=2048
        )
        self.stream.start()
        print("[OK] Audio stream started")

    def stop_audio(self):
        """Stop audio output."""
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

    def create_socket(self):
        """Create and bind the Unix socket."""
        try:
            os.unlink(SOCKET_PATH)
        except FileNotFoundError:
            pass

        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1048576)
        self.socket.bind(SOCKET_PATH)
        self.socket.listen(1)
        print(f"[OK] Socket created: {SOCKET_PATH}")

    def accept_connection(self):
        """Wait for DOOM to connect."""
        print("Waiting for DOOM to connect...")
        self.client_socket, _ = self.socket.accept()
        self.client_socket.settimeout(5.0)
        print("[OK] DOOM connected!")

        # Send init complete
        self._send_message(MSG_INIT_COMPLETE, {})

    def _send_message(self, msg_type, payload):
        """Send a message to DOOM."""
        payload_bytes = json.dumps(payload).encode('utf-8')
        header = struct.pack('II', msg_type, len(payload_bytes))
        try:
            self.client_socket.sendall(header + payload_bytes)
        except Exception as e:
            print(f"Send error: {e}")

    def _recv_exact(self, n):
        """Receive exactly n bytes."""
        data = b''
        while len(data) < n:
            chunk = self.client_socket.recv(n - len(data))
            if not chunk:
                return None
            data += chunk
        return data

    def _receive_message(self):
        """Receive a message from DOOM."""
        header = self._recv_exact(8)
        if not header:
            return None, None

        msg_type, payload_len = struct.unpack('II', header)

        # Sanity check payload length (max 1MB)
        if payload_len > 1048576:
            print(f"Invalid payload length: {payload_len}, resyncing...")
            # Flush socket buffer to try to resync
            self.client_socket.setblocking(False)
            try:
                while True:
                    self.client_socket.recv(4096)
            except:
                pass
            self.client_socket.setblocking(True)
            self.client_socket.settimeout(5.0)
            return None, None

        payload_bytes = self._recv_exact(payload_len)
        if not payload_bytes:
            return None, None

        try:
            payload = json.loads(payload_bytes.decode('utf-8'))
            return msg_type, payload
        except json.JSONDecodeError as e:
            # Don't print every error, just skip bad frames
            return msg_type, None

    def receive_loop(self):
        """Background thread to receive frames from DOOM."""
        print("[OK] Receive loop started")

        while self.running:
            try:
                msg_type, payload = self._receive_message()

                if msg_type is None:
                    print("Connection closed")
                    break

                if msg_type == MSG_FRAME_DATA:
                    # Skip bad frames
                    if payload is None:
                        continue

                    # Convert frame to scope points
                    points = self.frame_to_points(payload)

                    # Update audio buffer
                    with self.audio_lock:
                        self.audio_points = points

                    self.frame_count += 1
                    now = time.time()
                    if now - self.last_frame_time >= 1.0:
                        fps = self.frame_count / (now - self.last_frame_time)
                        walls = len(payload.get('walls', []))
                        entities = len(payload.get('entities', []))
                        print(f"FPS: {fps:.1f} | Walls: {walls} | Entities: {entities} | Points: {len(points)}")
                        self.frame_count = 0
                        self.last_frame_time = now

                elif msg_type == MSG_SHUTDOWN:
                    print("Shutdown received")
                    break

            except socket.timeout:
                continue
            except Exception as e:
                print(f"Receive error: {e}")
                continue

        print("Receive loop exiting")

    def run(self):
        """Main run loop."""
        print("=" * 60)
        print("ScopeDoom - DOOM on Oscilloscope")
        print("=" * 60)
        print()
        print("Connect your sound card to the oscilloscope:")
        print("  Left channel  -> X input")
        print("  Right channel -> Y input")
        print("  Set scope to X-Y mode")
        print()
        print("Then run DOOM:")
        print("  ./run_doom.sh dual -w 1 1")
        print()
        print("=" * 60)

        try:
            self.start_audio()
            self.create_socket()
            self.accept_connection()

            self.running = True
            receive_thread = threading.Thread(target=self.receive_loop, daemon=True)
            receive_thread.start()

            print("\n[OK] Running! Press Ctrl+C to stop\n")

            while self.running:
                time.sleep(0.1)

        except KeyboardInterrupt:
            print("\n\nStopping...")
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up resources."""
        self.running = False
        self.stop_audio()

        if self.client_socket:
            try:
                self._send_message(MSG_SHUTDOWN, {})
                self.client_socket.close()
            except:
                pass

        if self.socket:
            try:
                self.socket.close()
                os.unlink(SOCKET_PATH)
            except:
                pass

        print("[OK] Cleanup complete")


def main():
    scope = DoomScope()
    scope.run()


if __name__ == '__main__':
    main()
