#!/usr/bin/env python3
"""
Standalone Renderer V3 - MINIMAL WIREFRAME

Tests DOOM's new extraction (ceilingclip/floorclip).
Just draws the raw data as simple wireframe lines.
"""

import socket
import struct
import json
import threading
import time
import sys
import os
import subprocess
from PIL import Image

try:
    import pygame
except ImportError:
    print("ERROR: pygame not installed!")
    print("Install with: pip install pygame")
    sys.exit(1)

# Socket configuration
SOCKET_PATH = "/tmp/kicad_doom.sock"

# Message types
MSG_FRAME_DATA = 0x01
MSG_KEY_EVENT = 0x02
MSG_INIT_COMPLETE = 0x03
MSG_SHUTDOWN = 0x04

# Display
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 400
DOOM_WIDTH = 320
DOOM_HEIGHT = 200

# Colors
COLOR_BG = (0, 0, 0)
COLOR_WALL = (0, 255, 0)  # Green wireframe
COLOR_SPRITE = (255, 255, 0)  # Yellow
COLOR_TEXT = (255, 255, 255)


class MinimalRenderer:
    """Minimal wireframe renderer to test DOOM extraction."""

    def __init__(self):
        self.running = False
        self.socket = None
        self.client_socket = None
        self.current_frame = None
        self.frame_lock = threading.Lock()
        self.frame_count = 0
        self.fps = 0.0
        self.start_time = None
        self.last_fps_time = None
        self.last_screenshot_time = None

        # Create framebuffer directory and clear old screenshots
        self.framebuffer_dir = "framebuffer"
        self._clear_framebuffer()
        os.makedirs(self.framebuffer_dir, exist_ok=True)

    def _clear_framebuffer(self):
        """Clear all existing screenshots from framebuffer directory."""
        if os.path.exists(self.framebuffer_dir):
            import shutil
            shutil.rmtree(self.framebuffer_dir)
            print(f"✓ Cleared old screenshots from {self.framebuffer_dir}/")

    def _capture_sdl_window(self, output_path):
        """Capture SDL window screenshot using screencapture on macOS."""
        try:
            # Use screencapture with interactive window selection
            # We'll capture by finding the SDL window using AppleScript
            # Try multiple approaches

            # Approach 1: Look for window with "DOOM" in title
            script = '''
            tell application "System Events"
                set windowList to {}
                repeat with theProcess in (every process)
                    try
                        repeat with theWindow in (every window of theProcess)
                            if name of theWindow contains "DOOM" then
                                return id of theWindow
                            end if
                        end repeat
                    end try
                end repeat
            end tell
            '''

            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=3
            )

            if result.returncode == 0 and result.stdout.strip():
                window_id = result.stdout.strip()
                # Capture that window (remove -x to avoid beep)
                subprocess.run(
                    ['screencapture', '-l', window_id, '-o', output_path],
                    timeout=2,
                    capture_output=True
                )
                # Check if file was created
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    return True
        except Exception as e:
            print(f"Debug: SDL capture failed: {e}")

        return False

    def _combine_screenshots(self, python_path, sdl_path, combined_path):
        """Combine Python and SDL screenshots side-by-side."""
        try:
            # Load both images
            python_img = Image.open(python_path)
            sdl_img = Image.open(sdl_path)

            # Resize SDL to match Python height if needed
            if sdl_img.height != python_img.height:
                aspect = sdl_img.width / sdl_img.height
                new_width = int(python_img.height * aspect)
                sdl_img = sdl_img.resize((new_width, python_img.height), Image.LANCZOS)

            # Create combined image (side-by-side)
            total_width = python_img.width + sdl_img.width
            combined = Image.new('RGB', (total_width, python_img.height))

            # Paste images side-by-side
            combined.paste(python_img, (0, 0))
            combined.paste(sdl_img, (python_img.width, 0))

            # Save combined image
            combined.save(combined_path)
            return True
        except Exception as e:
            print(f"Warning: Could not combine screenshots: {e}")
            return False

    def init_pygame(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("DOOM V3 - Minimal Wireframe Test")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 24)
        print("✓ pygame initialized")

    def create_socket(self):
        import os
        try:
            os.unlink(SOCKET_PATH)
        except FileNotFoundError:
            pass

        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1048576)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1048576)
        self.socket.bind(SOCKET_PATH)
        self.socket.listen(1)
        print(f"✓ Socket created: {SOCKET_PATH}")
        print("  Waiting for DOOM V3...")

    def accept_connection(self):
        self.client_socket, _ = self.socket.accept()
        self.client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1048576)
        self.client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1048576)
        self.client_socket.settimeout(5.0)
        print("✓ DOOM V3 connected!")
        self._send_message(MSG_INIT_COMPLETE, {})

    def _send_message(self, msg_type, payload):
        payload_bytes = json.dumps(payload).encode('utf-8')
        header = struct.pack('II', msg_type, len(payload_bytes))
        try:
            self.client_socket.sendall(header + payload_bytes)
        except Exception as e:
            print(f"ERROR sending: {e}")

    def _receive_message(self):
        header = self._recv_exact(8)
        if not header:
            return None, None
        msg_type, payload_len = struct.unpack('II', header)
        payload_bytes = self._recv_exact(payload_len)
        if not payload_bytes:
            return None, None
        payload = json.loads(payload_bytes.decode('utf-8'))
        return msg_type, payload

    def _recv_exact(self, n):
        data = b''
        while len(data) < n:
            chunk = self.client_socket.recv(n - len(data))
            if not chunk:
                return None
            data += chunk
        return data

    def receive_loop(self):
        print("✓ Receive loop started")
        try:
            while self.running:
                try:
                    msg_type, payload = self._receive_message()
                    if msg_type is None:
                        print("Connection closed")
                        break
                    if msg_type == MSG_FRAME_DATA:
                        with self.frame_lock:
                            self.current_frame = payload
                    elif msg_type == MSG_SHUTDOWN:
                        print("Shutdown received")
                        self.running = False
                        break
                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"ERROR receiving: {e}")
                    continue
        except Exception as e:
            print(f"FATAL ERROR in receive loop: {e}")
        finally:
            print("Receive loop exiting")

    def doom_to_screen(self, x, y):
        """Convert DOOM 320x200 to screen coordinates with proper aspect ratio."""
        # DOOM renders at 320x200, but we want to fill 800x400 (same aspect)
        # Direct linear scaling
        scale_x = SCREEN_WIDTH / DOOM_WIDTH   # 800/320 = 2.5
        scale_y = SCREEN_HEIGHT / DOOM_HEIGHT # 400/200 = 2.0
        return int(x * scale_x), int(y * scale_y)

    def render_frame(self):
        """Render frame with proper occlusion using filled polygons."""
        self.screen.fill(COLOR_BG)

        with self.frame_lock:
            frame = self.current_frame

        if not frame:
            text = self.font.render("Waiting for DOOM V3...", True, COLOR_TEXT)
            text_rect = text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
            self.screen.blit(text, text_rect)
            pygame.display.flip()
            return

        # Collect all walls with distance
        walls = frame.get('walls', [])
        walls_list = []
        for wall in walls:
            if isinstance(wall, list) and len(wall) >= 7:
                distance = wall[6]
                walls_list.append(('wall', distance, wall))

        # Collect all entities with distance
        entities = frame.get('entities', [])
        for entity in entities:
            distance = entity.get('distance', 100)
            walls_list.append(('sprite', distance, entity))

        # Sort ALL objects by distance (far to near) for proper occlusion
        walls_list.sort(key=lambda x: x[1], reverse=True)

        # Draw all objects in order (back to front)
        for obj_type, distance, obj_data in walls_list:
            if obj_type == 'wall':
                # Draw wall
                wall = obj_data
                x1, y1_top, y1_bottom, x2, y2_top, y2_bottom, _ = wall[:7]

                # Debug: Print first wall data
                if self.frame_count % 60 == 0 and distance == walls_list[0][1]:
                    print(f"Wall sample: x[{x1}-{x2}] y_top[{y1_top},{y2_top}] y_bottom[{y1_bottom},{y2_bottom}] dist:{distance}")

                # Convert to screen coords
                x1_s, y1t_s = self.doom_to_screen(x1, y1_top)
                _, y1b_s = self.doom_to_screen(x1, y1_bottom)
                x2_s, y2t_s = self.doom_to_screen(x2, y2_top)
                _, y2b_s = self.doom_to_screen(x2, y2_bottom)

                # Also get screen bottom (for floor) and top (for ceiling)
                _, screen_bottom = self.doom_to_screen(0, DOOM_HEIGHT)
                _, screen_top = self.doom_to_screen(0, 0)

                # Color based on distance (depth cueing)
                t = min(1.0, distance / 500.0)
                brightness = int(255 * (1.0 - t * 0.7))

                # CEILING: from screen top down to wall top
                # Draw darker than walls
                ceiling_brightness = int(brightness * 0.3)
                ceiling_color = (0, ceiling_brightness, ceiling_brightness)  # Cyan tint
                ceiling_points = [
                    (x1_s, screen_top),     # Top left
                    (x1_s, y1t_s),          # Wall top left
                    (x2_s, y2t_s),          # Wall top right
                    (x2_s, screen_top)      # Top right
                ]
                pygame.draw.polygon(self.screen, ceiling_color, ceiling_points, 0)

                # FLOOR: from wall bottom down to screen bottom
                # Draw darker than walls
                floor_brightness = int(brightness * 0.4)
                floor_color = (floor_brightness, floor_brightness, 0)  # Brown/yellow tint
                floor_points = [
                    (x1_s, y1b_s),          # Wall bottom left
                    (x1_s, screen_bottom),  # Bottom left
                    (x2_s, screen_bottom),  # Bottom right
                    (x2_s, y2b_s)           # Wall bottom right
                ]
                pygame.draw.polygon(self.screen, floor_color, floor_points, 0)

                # WALL: main wall polygon (brightest)
                wall_color = (0, brightness, 0)
                wall_points = [
                    (x1_s, y1t_s),
                    (x1_s, y1b_s),
                    (x2_s, y2b_s),
                    (x2_s, y2t_s)
                ]
                pygame.draw.polygon(self.screen, wall_color, wall_points, 0)

                # Draw darker outline for wall definition
                outline_color = (0, max(0, brightness - 50), 0)
                pygame.draw.polygon(self.screen, outline_color, wall_points, 1)

            elif obj_type == 'sprite':
                # Draw sprite
                entity = obj_data
                x = entity['x']
                y_top = entity['y_top']
                y_bottom = entity['y_bottom']

                x_s, yt_s = self.doom_to_screen(x, y_top)
                _, yb_s = self.doom_to_screen(x, y_bottom)

                height_s = abs(yb_s - yt_s)
                width_s = max(5, int(height_s * 0.6))

                # Color based on distance
                t = min(1.0, distance / 500.0)
                brightness = int(255 * (1.0 - t * 0.5))
                color = (brightness, brightness, 0)  # Yellow

                # Draw wireframe rectangle only (no fill)
                pygame.draw.rect(self.screen, color,
                                (x_s - width_s // 2, yt_s, width_s, height_s), 2)

        # FPS
        fps_text = self.font.render(f"FPS: {self.fps:.1f} | Frame: {self.frame_count}", True, (0, 255, 0))
        self.screen.blit(fps_text, (10, 10))

        # Debug info
        wall_count = len(frame.get('walls', []))
        entity_count = len(frame.get('entities', []))
        info_text = self.font.render(f"Walls: {wall_count} | Entities: {entity_count}", True, (200, 200, 200))
        self.screen.blit(info_text, (10, 35))

        pygame.display.flip()

        # Update stats
        self.frame_count += 1
        current_time = time.time()
        if self.last_fps_time:
            elapsed = current_time - self.last_fps_time
            if elapsed >= 1.0:
                self.fps = self.frame_count / (current_time - self.start_time)
                self.last_fps_time = current_time
        else:
            self.last_fps_time = current_time
            self.start_time = current_time

        # Take combined screenshot every 10 seconds
        if self.last_screenshot_time is None:
            self.last_screenshot_time = current_time
        elif current_time - self.last_screenshot_time >= 10.0:
            timestamp = int(current_time)

            # Save Python renderer screenshot
            python_path = os.path.join(self.framebuffer_dir, f"python_{timestamp}.png")
            pygame.image.save(self.screen, python_path)

            # Capture SDL window screenshot
            sdl_path = os.path.join(self.framebuffer_dir, f"sdl_{timestamp}.png")
            sdl_captured = self._capture_sdl_window(sdl_path)

            if sdl_captured:
                # Combine screenshots side-by-side
                combined_path = os.path.join(self.framebuffer_dir, f"combined_{timestamp}.png")
                if self._combine_screenshots(python_path, sdl_path, combined_path):
                    print(f"✓ Combined screenshot saved: {combined_path}")
                    # Clean up individual screenshots
                    try:
                        os.remove(python_path)
                        os.remove(sdl_path)
                    except:
                        pass
                else:
                    print(f"✓ Python screenshot saved: {python_path}")
            else:
                print(f"✓ Python screenshot saved: {python_path}")

            self.last_screenshot_time = current_time

    def handle_input(self):
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
        key_map = {
            pygame.K_w: 'w', pygame.K_s: 's', pygame.K_a: 'a', pygame.K_d: 'd',
            pygame.K_LEFT: 'left', pygame.K_RIGHT: 'right',
            pygame.K_UP: 'up', pygame.K_DOWN: 'down',
            pygame.K_LCTRL: 'ctrl', pygame.K_RCTRL: 'ctrl',
            pygame.K_SPACE: 'space', pygame.K_e: 'e', pygame.K_ESCAPE: 'escape',
            pygame.K_1: '1', pygame.K_2: '2', pygame.K_3: '3', pygame.K_4: '4',
            pygame.K_5: '5', pygame.K_6: '6', pygame.K_7: '7',
        }
        return key_map.get(pygame_key)

    def _send_key_event(self, key, pressed):
        payload = {'key': key, 'pressed': pressed}
        self._send_message(MSG_KEY_EVENT, payload)

    def run(self):
        print("\n" + "=" * 70)
        print("DOOM V3 - Minimal Wireframe Renderer")
        print("=" * 70)

        try:
            self.init_pygame()
            self.create_socket()
            self.accept_connection()

            self.running = True
            receive_thread = threading.Thread(target=self.receive_loop, daemon=True)
            receive_thread.start()

            print("\n" + "=" * 70)
            print("Renderer Running!")
            print("=" * 70)
            print("\nControls: WASD (move), Arrows (turn), Ctrl (fire), ESC (quit)")
            print("=" * 70)

            while self.running:
                self.handle_input()
                self.render_frame()
                self.clock.tick(60)

        except KeyboardInterrupt:
            print("\n\nInterrupted")
        except Exception as e:
            print(f"\nERROR: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.cleanup()

    def cleanup(self):
        print("\nCleaning up...")
        self.running = False

        if self.client_socket:
            try:
                self._send_message(MSG_SHUTDOWN, {})
                self.client_socket.close()
            except:
                pass

        if self.socket:
            try:
                self.socket.close()
            except:
                pass

        try:
            import os
            os.unlink(SOCKET_PATH)
        except:
            pass

        pygame.quit()
        print("✓ Cleanup complete")


def main():
    renderer = MinimalRenderer()
    renderer.run()


if __name__ == '__main__':
    main()
