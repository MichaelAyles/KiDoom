#!/usr/bin/env python3
"""
Standalone Python Vector Renderer for DOOM

This provides a pure Python frontend to test the DOOM engine without KiCad.
Uses pygame to render the same vector data that would be sent to KiCad,
allowing us to verify the DOOM engine and communication protocol work correctly.

Usage:
    python standalone_renderer.py

Then launch DOOM:
    cd doom && ./doomgeneric_kicad
"""

import socket
import struct
import json
import threading
import time
import sys

try:
    import pygame
except ImportError:
    print("ERROR: pygame not installed!")
    print("Install with: pip install pygame")
    sys.exit(1)

# Socket configuration (must match DOOM engine)
SOCKET_PATH = "/tmp/kicad_doom.sock"

# Message types (must match doomgeneric_kicad.c)
MSG_FRAME_DATA = 0x01
MSG_KEY_EVENT = 0x02
MSG_INIT_COMPLETE = 0x03
MSG_SHUTDOWN = 0x04

# Display configuration
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 800
DOOM_WIDTH = 320
DOOM_HEIGHT = 200

# Color scheme - High contrast for visibility
COLOR_BACKGROUND = (10, 10, 20)   # Very dark blue
COLOR_WALL_CLOSE = (255, 200, 100)  # Bright orange for close walls
COLOR_WALL_FAR = (80, 120, 180)     # Blue-gray for distant walls
COLOR_ENTITY = (255, 220, 100)      # Gold (components)
COLOR_PROJECTILE = (255, 50, 50)    # Red (vias/projectiles)
COLOR_HUD = (200, 200, 200)         # White (silkscreen text)


class StandaloneRenderer:
    """
    Standalone vector renderer for DOOM.

    Receives frame data via Unix socket and renders using pygame.
    """

    def __init__(self):
        self.running = False
        self.socket = None
        self.client_socket = None

        # Frame statistics
        self.frame_count = 0
        self.start_time = None
        self.last_fps_time = None
        self.fps = 0.0

        # pygame state
        self.screen = None
        self.clock = None
        self.font = None

        # Current frame data
        self.current_frame = None
        self.frame_lock = threading.Lock()

    def init_pygame(self):
        """Initialize pygame display."""
        pygame.init()

        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("DOOM - Standalone Vector Renderer")

        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 24)

        print("✓ pygame initialized")
        print(f"  Display: {SCREEN_WIDTH}x{SCREEN_HEIGHT}")

    def create_socket(self):
        """Create Unix domain socket server."""
        import os

        # Remove existing socket file
        try:
            os.unlink(SOCKET_PATH)
        except FileNotFoundError:
            pass

        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

        # Increase socket buffer sizes to prevent blocking
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1048576)  # 1MB receive buffer
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1048576)  # 1MB send buffer

        self.socket.bind(SOCKET_PATH)
        self.socket.listen(1)

        print(f"✓ Socket created: {SOCKET_PATH}")
        print("  Waiting for DOOM to connect...")

    def accept_connection(self):
        """Accept connection from DOOM engine."""
        self.client_socket, _ = self.socket.accept()

        # Set socket options for client connection
        self.client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1048576)  # 1MB
        self.client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1048576)  # 1MB
        self.client_socket.settimeout(5.0)  # 5 second timeout to prevent infinite hangs

        print("✓ DOOM connected!")

        # Send INIT_COMPLETE
        self._send_message(MSG_INIT_COMPLETE, {})

    def _send_message(self, msg_type, payload):
        """Send message to DOOM engine."""
        payload_bytes = json.dumps(payload).encode('utf-8')
        header = struct.pack('II', msg_type, len(payload_bytes))

        try:
            self.client_socket.sendall(header + payload_bytes)
        except Exception as e:
            print(f"ERROR sending message: {e}")

    def _receive_message(self):
        """Receive one message from DOOM engine."""
        # Read header (8 bytes)
        header = self._recv_exact(8)
        if not header:
            return None, None

        msg_type, payload_len = struct.unpack('II', header)

        # Read payload
        payload_bytes = self._recv_exact(payload_len)
        if not payload_bytes:
            return None, None

        payload = json.loads(payload_bytes.decode('utf-8'))

        return msg_type, payload

    def _recv_exact(self, n):
        """Receive exactly n bytes from socket."""
        data = b''
        while len(data) < n:
            chunk = self.client_socket.recv(n - len(data))
            if not chunk:
                return None
            data += chunk
        return data

    def receive_loop(self):
        """Background thread that receives frames from DOOM."""
        print("✓ Receive loop started")

        try:
            while self.running:
                try:
                    msg_type, payload = self._receive_message()

                    if msg_type is None:
                        print("Connection closed by DOOM")
                        break

                    if msg_type == MSG_FRAME_DATA:
                        # Update current frame
                        with self.frame_lock:
                            self.current_frame = payload

                    elif msg_type == MSG_SHUTDOWN:
                        print("Received shutdown from DOOM")
                        self.running = False
                        break

                except socket.timeout:
                    # Timeout is OK - just means no data yet, continue waiting
                    continue
                except Exception as e:
                    print(f"ERROR receiving message: {e}")
                    # Don't break on error - try to recover
                    continue

        except Exception as e:
            print(f"FATAL ERROR in receive loop: {e}")
            import traceback
            traceback.print_exc()
        finally:
            print("Receive loop exiting")

    def doom_to_screen(self, x, y):
        """Convert DOOM coordinates to screen coordinates."""
        # DOOM uses 320x200, scale to fit screen
        scale_x = SCREEN_WIDTH / DOOM_WIDTH
        scale_y = SCREEN_HEIGHT / DOOM_HEIGHT

        screen_x = int(x * scale_x)
        screen_y = int(y * scale_y)

        return screen_x, screen_y

    def render_frame(self):
        """Render current frame to pygame display."""
        # Clear screen
        self.screen.fill(COLOR_BACKGROUND)

        # Get current frame
        with self.frame_lock:
            frame = self.current_frame

        if not frame:
            # No frame yet, show waiting message
            text = self.font.render("Waiting for DOOM...", True, COLOR_HUD)
            text_rect = text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
            self.screen.blit(text, text_rect)
            pygame.display.flip()
            return

        # Render walls
        if 'walls' in frame:
            for wall in frame['walls']:
                # Handle different array formats
                if isinstance(wall, list):
                    if len(wall) >= 7:
                        # V3 format: [x1, y1_top, y1_bottom, x2, y2_top, y2_bottom, distance]
                        x1, y1_top, y1_bottom, x2, y2_top, y2_bottom, distance = wall[:7]

                        # Convert to screen coordinates
                        x1_screen, y1_top_screen = self.doom_to_screen(x1, y1_top)
                        _, y1_bottom_screen = self.doom_to_screen(x1, y1_bottom)
                        x2_screen, y2_top_screen = self.doom_to_screen(x2, y2_top)
                        _, y2_bottom_screen = self.doom_to_screen(x2, y2_bottom)

                        # Color based on depth - interpolate between close and far colors
                        # Closer walls = brighter orange, distant walls = blue-gray
                        t = min(1.0, max(0.0, distance / 200.0))  # Normalize distance (0=close, 1=far)

                        # Interpolate base color
                        r = int(COLOR_WALL_CLOSE[0] * (1-t) + COLOR_WALL_FAR[0] * t)
                        g = int(COLOR_WALL_CLOSE[1] * (1-t) + COLOR_WALL_FAR[1] * t)
                        b = int(COLOR_WALL_CLOSE[2] * (1-t) + COLOR_WALL_FAR[2] * t)

                        # Apply brightness falloff (additional darkening with distance)
                        brightness_factor = 1.0 - (t * 0.5)  # Reduce brightness by up to 50% for distant walls
                        r = int(r * brightness_factor)
                        g = int(g * brightness_factor)
                        b = int(b * brightness_factor)
                        color = (r, g, b)

                        # Width based on distance - thicker lines for close walls
                        width = max(1, min(6, int(400 / max(distance, 20))))

                        # Draw wall as polygon (quadrilateral)
                        points = [
                            (x1_screen, y1_top_screen),
                            (x1_screen, y1_bottom_screen),
                            (x2_screen, y2_bottom_screen),
                            (x2_screen, y2_top_screen)
                        ]
                        pygame.draw.polygon(self.screen, color, points, width)

                    elif len(wall) >= 5:
                        # V2 format: [x1, y1, x2, y2, distance]
                        x1, y1, x2, y2, distance = wall[:5]
                        x1_screen, y1_screen = self.doom_to_screen(x1, y1)
                        x2_screen, y2_screen = self.doom_to_screen(x2, y2)

                        # Color based on depth - same interpolation
                        t = min(1.0, max(0.0, distance / 200.0))

                        # Interpolate base color
                        r = int(COLOR_WALL_CLOSE[0] * (1-t) + COLOR_WALL_FAR[0] * t)
                        g = int(COLOR_WALL_CLOSE[1] * (1-t) + COLOR_WALL_FAR[1] * t)
                        b = int(COLOR_WALL_CLOSE[2] * (1-t) + COLOR_WALL_FAR[2] * t)

                        # Apply brightness falloff
                        brightness_factor = 1.0 - (t * 0.5)
                        r = int(r * brightness_factor)
                        g = int(g * brightness_factor)
                        b = int(b * brightness_factor)
                        color = (r, g, b)

                        width = max(1, min(6, int(400 / max(distance, 20))))

                        pygame.draw.line(self.screen, color, (x1_screen, y1_screen),
                                       (x2_screen, y2_screen), width)
                else:
                    # Object format from V1
                    x1 = wall.get('x1', 0)
                    y1 = wall.get('y1', 0)
                    x2 = wall.get('x2', 0)
                    y2 = wall.get('y2', 0)
                    distance = wall.get('distance', 100)

                    x1_screen, y1_screen = self.doom_to_screen(x1, y1)
                    x2_screen, y2_screen = self.doom_to_screen(x2, y2)

                    # Color based on depth - same interpolation
                    t = min(1.0, max(0.0, distance / 200.0))

                    # Interpolate base color
                    r = int(COLOR_WALL_CLOSE[0] * (1-t) + COLOR_WALL_FAR[0] * t)
                    g = int(COLOR_WALL_CLOSE[1] * (1-t) + COLOR_WALL_FAR[1] * t)
                    b = int(COLOR_WALL_CLOSE[2] * (1-t) + COLOR_WALL_FAR[2] * t)

                    # Apply brightness falloff
                    brightness_factor = 1.0 - (t * 0.5)
                    r = int(r * brightness_factor)
                    g = int(g * brightness_factor)
                    b = int(b * brightness_factor)
                    color = (r, g, b)

                    width = max(1, min(6, int(400 / max(distance, 20))))

                    pygame.draw.line(self.screen, color, (x1_screen, y1_screen),
                                   (x2_screen, y2_screen), width)

        # Render entities (player, enemies, items)
        if 'entities' in frame:
            for entity in frame['entities']:
                x, y = self.doom_to_screen(entity['x'], entity['y'])

                # Draw as circle for simplicity
                radius = entity.get('size', 5)
                pygame.draw.circle(self.screen, COLOR_ENTITY, (x, y), radius)

                # Draw facing direction
                angle = entity.get('angle', 0)
                import math
                dir_x = x + int(radius * 2 * math.cos(math.radians(angle)))
                dir_y = y + int(radius * 2 * math.sin(math.radians(angle)))
                pygame.draw.line(self.screen, COLOR_ENTITY, (x, y), (dir_x, dir_y), 2)

        # Render projectiles
        if 'projectiles' in frame:
            for proj in frame['projectiles']:
                x, y = self.doom_to_screen(proj['x'], proj['y'])
                pygame.draw.circle(self.screen, COLOR_PROJECTILE, (x, y), 3)

        # Render HUD text
        if 'hud' in frame:
            y_offset = 10
            for text_item in frame['hud']:
                text = self.font.render(text_item['text'], True, COLOR_HUD)
                self.screen.blit(text, (10, y_offset))
                y_offset += 25

        # Render weapon sprite (HUD layer - always on top)
        if 'weapon' in frame and isinstance(frame['weapon'], dict):
            weapon = frame['weapon']
            if weapon.get('visible', False):
                wx, wy = self.doom_to_screen(weapon['x'], weapon['y'])
                # Draw weapon as a simple marker (could be improved with actual sprite)
                # Draw a simple gun shape
                pygame.draw.rect(self.screen, (150, 150, 150), (wx - 10, wy - 5, 20, 10))
                pygame.draw.rect(self.screen, (100, 100, 100), (wx + 5, wy - 3, 15, 6))
                pygame.draw.circle(self.screen, (200, 200, 0), (wx, wy), 3)

        # Render FPS counter
        fps_text = self.font.render(f"FPS: {self.fps:.1f} | Frame: {self.frame_count}", True, (100, 255, 100))
        self.screen.blit(fps_text, (SCREEN_WIDTH - 200, 10))

        # Update display
        pygame.display.flip()

        # Update statistics
        self.frame_count += 1
        current_time = time.time()

        if self.last_fps_time:
            elapsed = current_time - self.last_fps_time
            if elapsed >= 1.0:  # Update FPS every second
                self.fps = self.frame_count / (current_time - self.start_time)
                self.last_fps_time = current_time
        else:
            self.last_fps_time = current_time
            self.start_time = current_time

    def handle_input(self):
        """Handle pygame events and send to DOOM."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return

            elif event.type == pygame.KEYDOWN:
                key_name = self._pygame_to_doom_key(event.key)
                if key_name:
                    self._send_key_event(key_name, True)

            elif event.type == pygame.KEYUP:
                key_name = self._pygame_to_doom_key(event.key)
                if key_name:
                    self._send_key_event(key_name, False)

    def _pygame_to_doom_key(self, pygame_key):
        """Convert pygame key to DOOM key name."""
        key_map = {
            pygame.K_w: 'w',
            pygame.K_s: 's',
            pygame.K_a: 'a',
            pygame.K_d: 'd',
            pygame.K_LEFT: 'left',
            pygame.K_RIGHT: 'right',
            pygame.K_UP: 'up',
            pygame.K_DOWN: 'down',
            pygame.K_LCTRL: 'ctrl',
            pygame.K_RCTRL: 'ctrl',
            pygame.K_SPACE: 'space',
            pygame.K_e: 'e',
            pygame.K_ESCAPE: 'escape',
            pygame.K_1: '1',
            pygame.K_2: '2',
            pygame.K_3: '3',
            pygame.K_4: '4',
            pygame.K_5: '5',
            pygame.K_6: '6',
            pygame.K_7: '7',
        }
        return key_map.get(pygame_key)

    def _send_key_event(self, key, pressed):
        """Send key event to DOOM."""
        payload = {
            'key': key,
            'pressed': pressed
        }
        self._send_message(MSG_KEY_EVENT, payload)

    def run(self):
        """Main loop."""
        print("\n" + "=" * 70)
        print("DOOM Standalone Vector Renderer")
        print("=" * 70)

        try:
            # Initialize
            self.init_pygame()
            self.create_socket()

            # Wait for DOOM to connect
            self.accept_connection()

            # Start receive thread
            self.running = True
            receive_thread = threading.Thread(target=self.receive_loop, daemon=True)
            receive_thread.start()

            print("\n" + "=" * 70)
            print("Renderer Running!")
            print("=" * 70)
            print("\nControls:")
            print("  WASD          - Move")
            print("  Arrow keys    - Turn")
            print("  Ctrl          - Fire")
            print("  Space/E       - Use/Open doors")
            print("  1-7           - Select weapon")
            print("  ESC           - Menu/Quit")
            print("\nClose window or press ESC to quit")
            print("=" * 70)

            # Main render loop
            while self.running:
                self.handle_input()
                self.render_frame()
                self.clock.tick(60)  # 60 FPS max

        except KeyboardInterrupt:
            print("\n\nInterrupted by user")

        except Exception as e:
            print(f"\nERROR: {e}")
            import traceback
            traceback.print_exc()

        finally:
            self.cleanup()

    def cleanup(self):
        """Cleanup resources."""
        print("\n" + "=" * 70)
        print("Cleaning Up")
        print("=" * 70)

        self.running = False

        # Send shutdown to DOOM
        if self.client_socket:
            try:
                self._send_message(MSG_SHUTDOWN, {})
            except:
                pass

        # Close sockets
        if self.client_socket:
            try:
                self.client_socket.close()
                print("✓ Client socket closed")
            except:
                pass

        if self.socket:
            try:
                self.socket.close()
                print("✓ Server socket closed")
            except:
                pass

        # Remove socket file
        try:
            import os
            os.unlink(SOCKET_PATH)
            print("✓ Socket file removed")
        except:
            pass

        # Quit pygame
        pygame.quit()
        print("✓ pygame quit")

        # Print statistics
        if self.frame_count > 0:
            print("\n" + "=" * 70)
            print("Session Statistics")
            print("=" * 70)
            print(f"Frames rendered: {self.frame_count}")
            if self.start_time:
                elapsed = time.time() - self.start_time
                print(f"Total time: {elapsed:.1f}s")
                print(f"Average FPS: {self.frame_count / elapsed:.1f}")
            print("=" * 70)


def main():
    """Entry point."""
    renderer = StandaloneRenderer()
    renderer.run()


if __name__ == '__main__':
    main()
