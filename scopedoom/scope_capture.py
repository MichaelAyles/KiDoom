#!/usr/bin/env python3
"""
ScopeDoom - Oscilloscope Screenshot Capture

Captures screenshots from Siglent oscilloscope via VXI-11 and syncs with SDL window.
Press 'c' to capture, 'q' to quit, or run with --continuous for auto-capture.

Usage:
    python3 scope_capture.py                    # Manual capture (press 'c')
    python3 scope_capture.py --continuous 1.0   # Auto-capture every 1 second
"""

import vxi11
import time
import os
import sys
from datetime import datetime

# Configuration
SCOPE_IP = "192.168.2.199"
OUTPUT_DIR = "/Users/tribune/Desktop/KiDoom/screenshots/scope"

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)


def connect_scope(ip):
    """Connect to the oscilloscope via VXI-11."""
    print(f"Connecting to scope at {ip}...")
    try:
        scope = vxi11.Instrument(ip)
        scope.timeout = 30  # 30 second timeout for large transfers

        # Query identity
        idn = scope.ask("*IDN?")
        print(f"Connected: {idn.strip()}")
        return scope
    except Exception as e:
        print(f"ERROR: Could not connect to scope: {e}")
        return None


def capture_screenshot(scope, filename=None):
    """Capture a screenshot from the scope and save it."""
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        filename = os.path.join(OUTPUT_DIR, f"scope_{timestamp}.bmp")

    try:
        # Siglent SDS1000X-E uses SCDP command for screen capture
        # The command returns BMP data with IEEE header
        print("Requesting screenshot...")

        # Use SCDP command (Screen CaPture/Dump)
        scope.write("SCDP")
        time.sleep(1)  # Give scope time to prepare the image

        # Read the response - BMP is about 1.1MB
        data = scope.read_raw(num=2000000)  # Read up to 2MB

        # Find BMP header (starts with 'BM')
        bmp_start = data.find(b'BM')
        if bmp_start >= 0:
            bmp_data = data[bmp_start:]
        elif data[0:1] == b'#':
            # Parse IEEE 488.2 header: #NXXXX where N is digit count
            n_digits = int(chr(data[1]))
            data_len = int(data[2:2+n_digits])
            bmp_data = data[2+n_digits:2+n_digits+data_len]
        else:
            bmp_data = data

        # Save to file
        with open(filename, 'wb') as f:
            f.write(bmp_data)

        print(f"Saved: {filename} ({len(bmp_data)} bytes)")
        return filename

    except Exception as e:
        print(f"ERROR capturing screenshot: {e}")
        import traceback
        traceback.print_exc()
        return None


def continuous_capture(scope, interval=1.0):
    """Continuously capture screenshots at the given interval."""
    print(f"Continuous capture mode: every {interval}s")
    print("Press Ctrl+C to stop")

    count = 0
    try:
        while True:
            capture_screenshot(scope)
            count += 1
            time.sleep(interval)
    except KeyboardInterrupt:
        print(f"\nStopped. Captured {count} screenshots.")


def manual_capture(scope):
    """Manual capture mode - press 'c' to capture, 'q' to quit."""
    print("Manual capture mode")
    print("  Press 'c' + Enter to capture")
    print("  Press 'q' + Enter to quit")

    count = 0
    try:
        while True:
            cmd = input("> ").strip().lower()
            if cmd == 'c':
                capture_screenshot(scope)
                count += 1
            elif cmd == 'q':
                break
            else:
                print("Unknown command. Use 'c' to capture, 'q' to quit.")
    except (KeyboardInterrupt, EOFError):
        pass

    print(f"Captured {count} screenshots.")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Capture oscilloscope screenshots")
    parser.add_argument("--ip", default=SCOPE_IP, help="Scope IP address")
    parser.add_argument("--continuous", type=float, metavar="INTERVAL",
                        help="Continuous capture mode with interval in seconds")
    parser.add_argument("--single", action="store_true",
                        help="Capture single screenshot and exit")
    args = parser.parse_args()

    # Connect to scope
    scope = connect_scope(args.ip)
    if not scope:
        sys.exit(1)

    try:
        if args.single:
            capture_screenshot(scope)
        elif args.continuous:
            continuous_capture(scope, args.continuous)
        else:
            manual_capture(scope)
    finally:
        scope.close()
        print("Disconnected from scope.")


if __name__ == "__main__":
    main()
