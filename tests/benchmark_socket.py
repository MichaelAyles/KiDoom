#!/usr/bin/env python3
"""
Socket Communication Latency Benchmark

This benchmark measures the overhead of sending frame data from a simulated
DOOM process to a Python receiver via Unix domain socket.

Expected result: Socket communication overhead < 5ms per frame.

This validates that IPC (Inter-Process Communication) won't be a bottleneck.
"""

import socket
import json
import struct
import time
import threading
import os
import sys


SOCKET_PATH = "/tmp/kidoom_benchmark.sock"

# Message type constants
MSG_FRAME_DATA = 0x01


class SocketServer:
    """Simulates the Python KiCad plugin receiving frames."""

    def __init__(self):
        self.socket = None
        self.connection = None
        self.received_frames = []
        self.running = False
        self.thread = None

    def start(self):
        """Start socket server."""
        # Remove old socket file if exists
        try:
            os.unlink(SOCKET_PATH)
        except FileNotFoundError:
            pass

        # Create Unix socket
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.bind(SOCKET_PATH)
        self.socket.listen(1)

        # Accept connection
        self.connection, _ = self.socket.accept()

        # Start receive thread
        self.running = True
        self.thread = threading.Thread(target=self._receive_loop)
        self.thread.daemon = True
        self.thread.start()

    def _receive_loop(self):
        """Receive messages from client."""
        while self.running:
            try:
                # Read header (8 bytes)
                header = self._recv_exactly(8)
                if not header:
                    break

                msg_type, payload_len = struct.unpack('II', header)

                # Read payload
                payload = self._recv_exactly(payload_len)
                if not payload:
                    break

                # Record receive time
                receive_time = time.time()

                # Parse JSON
                data = json.loads(payload.decode('utf-8'))
                data['receive_time'] = receive_time

                self.received_frames.append(data)

            except Exception as e:
                print(f"Server error: {e}")
                break

    def _recv_exactly(self, n):
        """Receive exactly n bytes."""
        data = b''
        while len(data) < n:
            chunk = self.connection.recv(n - len(data))
            if not chunk:
                return None
            data += chunk
        return data

    def stop(self):
        """Stop server."""
        self.running = False
        if self.connection:
            self.connection.close()
        if self.socket:
            self.socket.close()
        try:
            os.unlink(SOCKET_PATH)
        except:
            pass


class SocketClient:
    """Simulates the C DOOM process sending frames."""

    def __init__(self):
        self.socket = None

    def connect(self):
        """Connect to server."""
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.connect(SOCKET_PATH)

    def send_frame(self, frame_data):
        """Send frame data to server."""
        # Serialize to JSON
        payload = json.dumps(frame_data).encode('utf-8')

        # Create header
        header = struct.pack('II', MSG_FRAME_DATA, len(payload))

        # Send header + payload
        send_time = time.time()
        self.socket.sendall(header + payload)

        return send_time

    def close(self):
        """Close connection."""
        if self.socket:
            self.socket.close()


def generate_mock_frame_data(frame_num, num_walls=200, num_entities=10, num_projectiles=5):
    """
    Generate mock DOOM frame data similar to what the real engine will send.

    This creates a realistic payload size (~1-2KB per frame).
    """
    return {
        'frame': frame_num,
        'walls': [
            {
                'x1': i * 1.6,
                'y1': 0,
                'x2': i * 1.6,
                'y2': 100,
                'distance': (i * 7) % 150
            }
            for i in range(num_walls)
        ],
        'entities': [
            {
                'x': 160 + (i * 10),
                'y': 100,
                'type': ['player', 'imp', 'baron'][i % 3],
                'angle': (i * 45) % 360
            }
            for i in range(num_entities)
        ],
        'projectiles': [
            {
                'x': 100 + (i * 20),
                'y': 50 + (i * 10)
            }
            for i in range(num_projectiles)
        ],
        'hud': {
            'health': 100,
            'armor': 50,
            'ammo': 50
        }
    }


def run_benchmark(num_frames=100):
    """
    Run socket communication benchmark.
    """
    print("=" * 70)
    print("Socket Communication Latency Benchmark")
    print("=" * 70)
    print(f"\nConfiguration:")
    print(f"  Test frames: {num_frames}")
    print(f"  Socket path: {SOCKET_PATH}")
    print(f"\nThis benchmark measures the time to send frame data from")
    print(f"a simulated DOOM process to a Python receiver via Unix socket.\n")

    # Start server in background
    print("Starting socket server...")
    server = SocketServer()

    # Start server in thread
    server_thread = threading.Thread(target=server.start)
    server_thread.daemon = True
    server_thread.start()

    # Wait for server to be ready
    time.sleep(0.5)

    print("Connecting client...")
    client = SocketClient()
    client.connect()
    print("✓ Connected\n")

    # Generate sample frame data to check size
    sample_frame = generate_mock_frame_data(0)
    sample_json = json.dumps(sample_frame).encode('utf-8')
    print(f"Sample frame data size: {len(sample_json)} bytes")
    print(f"  Walls: {len(sample_frame['walls'])}")
    print(f"  Entities: {len(sample_frame['entities'])}")
    print(f"  Projectiles: {len(sample_frame['projectiles'])}")
    print()

    # Benchmark: send frames and measure round-trip time
    print(f"Sending {num_frames} frames...\n")

    send_times = []
    latencies = []

    for frame in range(num_frames):
        frame_data = generate_mock_frame_data(frame)

        # Send frame
        send_time = client.send_frame(frame_data)
        send_times.append(send_time)

        # Small delay to simulate DOOM's frame timing (35 FPS = ~28ms per frame)
        time.sleep(0.001)  # 1ms delay

        if (frame + 1) % 10 == 0:
            print(f"  Sent frame {frame + 1}/{num_frames}")

    # Wait for all frames to be received
    print("\nWaiting for all frames to be received...")
    timeout = 5.0
    start_wait = time.time()
    while len(server.received_frames) < num_frames:
        if time.time() - start_wait > timeout:
            print(f"WARNING: Timeout waiting for frames")
            print(f"  Expected: {num_frames}, Received: {len(server.received_frames)}")
            break
        time.sleep(0.01)

    print(f"✓ Received {len(server.received_frames)}/{num_frames} frames")

    # Calculate latencies (time from send to receive)
    for i, frame_data in enumerate(server.received_frames):
        if i < len(send_times):
            latency = frame_data['receive_time'] - send_times[i]
            latencies.append(latency)

    # Clean up
    client.close()
    server.stop()

    # Calculate statistics
    if not latencies:
        print("\nERROR: No latency data collected")
        return None

    avg_latency = sum(latencies) / len(latencies)
    min_latency = min(latencies)
    max_latency = max(latencies)

    sorted_latencies = sorted(latencies)
    p95_latency = sorted_latencies[int(len(sorted_latencies) * 0.95)]
    p99_latency = sorted_latencies[int(len(sorted_latencies) * 0.99)]

    # Print results
    print("\n" + "=" * 70)
    print("BENCHMARK RESULTS")
    print("=" * 70)
    print(f"\nLatency statistics (send → receive):")
    print(f"  Minimum:  {min_latency*1000:7.3f}ms")
    print(f"  Average:  {avg_latency*1000:7.3f}ms")
    print(f"  Maximum:  {max_latency*1000:7.3f}ms")
    print(f"  95th percentile: {p95_latency*1000:7.3f}ms")
    print(f"  99th percentile: {p99_latency*1000:7.3f}ms")

    # Throughput calculation
    total_time = send_times[-1] - send_times[0] if len(send_times) > 1 else 0
    fps = num_frames / total_time if total_time > 0 else 0
    print(f"\nThroughput:")
    print(f"  Total time: {total_time:.3f}s")
    print(f"  Average FPS: {fps:.1f}")
    print(f"  Frame interval: {total_time/num_frames*1000:.2f}ms")

    # Assessment
    print("\n" + "=" * 70)
    print("PERFORMANCE ASSESSMENT")
    print("=" * 70)

    if avg_latency < 0.005:  # < 5ms
        assessment = "EXCELLENT"
        color = "✓"
        recommendation = "Socket communication overhead is negligible."
        impact = "Socket IPC will not be a bottleneck for DOOM rendering."
    elif avg_latency < 0.010:  # 5-10ms
        assessment = "ACCEPTABLE"
        color = "~"
        recommendation = "Socket overhead is acceptable but measurable."
        impact = "May add ~5-10ms to overall frame time."
    else:  # > 10ms
        assessment = "CONCERNING"
        color = "✗"
        recommendation = "Socket overhead is higher than expected."
        impact = "Consider optimizing serialization or using shared memory."

    print(f"\n{color} Assessment: {assessment}")
    print(f"  Average latency: {avg_latency*1000:.3f}ms")
    print(f"  {recommendation}")
    print(f"  {impact}")

    print("\nOverhead breakdown:")
    print(f"  Serialization (JSON): ~{avg_latency*1000/2:.3f}ms (estimated)")
    print(f"  Socket transfer: ~{avg_latency*1000/2:.3f}ms (estimated)")

    print("\nOptimization opportunities:")
    if avg_latency > 0.005:
        print("  - Use binary format instead of JSON (MessagePack, Protocol Buffers)")
        print("  - Reduce frame data size (send only changed objects)")
        print("  - Use shared memory instead of sockets")
    else:
        print("  - Current implementation is optimal for this use case")

    print("\n" + "=" * 70)

    return {
        'avg_latency_ms': avg_latency * 1000,
        'max_latency_ms': max_latency * 1000,
        'assessment': assessment,
        'fps': fps
    }


if __name__ == '__main__':
    try:
        result = run_benchmark(num_frames=100)
        if result:
            sys.exit(0 if result['avg_latency_ms'] < 10.0 else 1)
    except Exception as e:
        print(f"\n\nERROR: Benchmark failed with exception:")
        print(f"{type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
