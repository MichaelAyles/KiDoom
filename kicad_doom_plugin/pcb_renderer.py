"""
Core PCB renderer for DOOM frames.

Converts DOOM frame data (walls, entities, projectiles, HUD) into PCB elements:
- Wall segments → PCB_TRACK (copper traces)
- Entities → FOOTPRINT (real components)
- Projectiles → PCB_VIA (drilled holes)
- HUD → PCB_TEXT (silkscreen text)

Performance: Benchmarked at 82.6 FPS on M1 MacBook Pro
Expected gameplay: 40-60 FPS with full DOOM engine
"""

import pcbnew
import time
import gc
import wx
import threading
import queue

from .config import (
    DISTANCE_THRESHOLD, TRACE_WIDTH_CLOSE, TRACE_WIDTH_FAR,
    HUD_UPDATE_INTERVAL, CLEANUP_INTERVAL, STATS_LOG_INTERVAL,
    SLOW_FRAME_THRESHOLD, DEBUG_MODE, LOG_FRAME_TIMES
)
from .coordinate_transform import CoordinateTransform
from .object_pool import create_all_pools


class DoomPCBRenderer:
    """
    Manages PCB rendering of DOOM frames.

    This is the performance-critical component - called 20-60 times per second.

    THREAD SAFETY:
    - render_frame() can be called from any thread (updates PCB objects)
    - Refresh() is called ONLY from main thread via wx.Timer
    - This prevents macOS threading crashes

    Usage:
        renderer = DoomPCBRenderer(board)
        renderer.start_refresh_timer()  # Start automatic refresh on main thread
        renderer.render_frame(frame_data)  # Can be called from background thread
        # ... repeat for each frame ...
        renderer.stop_refresh_timer()
        renderer.cleanup()
    """

    def __init__(self, board):
        """
        Initialize renderer with pre-allocated object pools.

        Args:
            board: KiCad BOARD object
        """
        self.board = board
        self.scale = CoordinateTransform.SCALE

        print("\n" + "=" * 70)
        print("Initializing DOOM PCB Renderer")
        print("=" * 70)

        # Create shared net for all DOOM geometry
        # This eliminates ratsnest (airwire) calculation overhead
        print("Creating shared DOOM net...")
        self.doom_net = self._create_doom_net()
        print(f"✓ Created net: {self.doom_net.GetNetname()}")

        # Create object pools (pre-allocate all PCB objects)
        print("\nCreating object pools...")
        self.pools = create_all_pools(board)

        # Statistics tracking
        self.frame_count = 0
        self.total_render_time = 0.0
        self.total_update_time = 0.0
        self.total_refresh_time = 0.0
        self.slow_frame_count = 0

        # Last HUD update frame (for throttling)
        self.last_hud_update = 0

        # Thread safety: Queue for frame data from background thread
        # Background thread pushes frame data, main thread pops and renders
        self.frame_queue = queue.Queue(maxsize=2)  # Small queue to avoid lag

        # Refresh timer (runs on main thread)
        self.refresh_timer = None

        print("\n✓ Renderer initialized")
        print("=" * 70 + "\n")

    def _create_doom_net(self):
        """
        Create a single shared net for all DOOM geometry.

        This is critical for performance:
        - Eliminates ratsnest calculation (20-30% speedup)
        - All traces/vias connected to same net
        - Electrically authentic (could be fabricated)

        Returns:
            NETINFO_ITEM: The DOOM net
        """
        net = pcbnew.NETINFO_ITEM(self.board, "DOOM_WORLD")
        self.board.Add(net)
        return net

    def render_frame(self, frame_data):
        """
        Queue frame data for rendering on main thread.

        CRITICAL: This is called from a BACKGROUND THREAD (doom_bridge receive loop).
        On macOS, we CANNOT modify PCB objects from background threads - it crashes!

        Instead, we queue the frame data and let the main thread timer process it.

        Args:
            frame_data: Dictionary containing:
                walls: List of wall segments [(x1, y1, x2, y2, distance), ...]
                entities: List of entities [(x, y, type, angle), ...]
                projectiles: List of projectiles [(x, y), ...]
                hud: Dictionary with HUD elements
        """
        try:
            # Try to add frame to queue (non-blocking)
            # If queue is full, drop oldest frame (keep most recent)
            try:
                self.frame_queue.put_nowait(frame_data)
            except queue.Full:
                # Queue full - drop old frame, add new one
                try:
                    self.frame_queue.get_nowait()  # Remove oldest
                    self.frame_queue.put_nowait(frame_data)  # Add newest
                except:
                    pass  # Queue operations failed, skip this frame

        except Exception as e:
            if DEBUG_MODE:
                print(f"ERROR: Failed to queue frame: {e}")

    def _process_frame(self, frame_data):
        """
        Actually process and render frame data to PCB.

        CRITICAL: This MUST be called from MAIN THREAD only!
        Called by timer callback (_on_refresh_timer).

        Args:
            frame_data: Dictionary with walls, entities, projectiles, hud
        """
        frame_start = time.time()
        update_start = time.time()

        try:
            # 1. Render walls (most objects, highest priority)
            walls = frame_data.get('walls', [])
            wall_trace_count = self._render_walls(walls)

            # 2. Render entities (player, enemies)
            entities = frame_data.get('entities', [])
            entity_trace_count = self._render_entities(entities, wall_trace_count)

            # Hide all unused traces (both walls and entities share the pool)
            trace_pool = self.pools['traces']
            total_traces = wall_trace_count + entity_trace_count
            trace_pool.hide_unused(total_traces)

            # 3. Render projectiles (bullets, fireballs)
            projectiles = frame_data.get('projectiles', [])
            self._render_projectiles(projectiles)

            # 4. Render HUD (throttled to every N frames)
            if self.frame_count - self.last_hud_update >= HUD_UPDATE_INTERVAL:
                hud = frame_data.get('hud', {})
                self._render_hud(hud)
                self.last_hud_update = self.frame_count

        except Exception as e:
            print(f"ERROR: Frame rendering failed: {e}")
            if DEBUG_MODE:
                import traceback
                traceback.print_exc()
            return

        update_time = time.time() - update_start
        self.total_update_time += update_time

        # Update statistics
        total_time = time.time() - frame_start
        self.total_render_time += total_time
        self.frame_count += 1

        # Track slow frames
        if total_time > SLOW_FRAME_THRESHOLD:
            self.slow_frame_count += 1
            if LOG_FRAME_TIMES:
                print(f"WARNING: Slow frame {self.frame_count}: "
                      f"{total_time*1000:.2f}ms")

        # Periodic logging
        if LOG_FRAME_TIMES and self.frame_count % STATS_LOG_INTERVAL == 0:
            self._log_statistics()

        # Periodic cleanup
        if self.frame_count % CLEANUP_INTERVAL == 0:
            self._periodic_cleanup()

    def _render_walls(self, walls):
        """
        Render wall segments as wireframe PCB traces.

        Each wall becomes 4 PCB_TRACK objects (wireframe box):
        - Top edge: (x1, y1_top) → (x2, y2_top)
        - Bottom edge: (x1, y1_bottom) → (x2, y2_bottom)
        - Left edge: (x1, y1_top) → (x1, y1_bottom)
        - Right edge: (x2, y2_top) → (x2, y2_bottom)

        Distance from player determines layer (F.Cu/B.Cu) and width.

        Args:
            walls: List of [x1, y1_top, y1_bottom, x2, y2_top, y2_bottom, distance, silhouette]

        Returns:
            int: Number of traces used for walls
        """
        trace_pool = self.pools['traces']
        trace_index = 0

        for wall in walls:
            if len(wall) < 8:
                continue  # Invalid wall data (need wireframe format)

            x1, y1_top, y1_bottom, x2, y2_top, y2_bottom, distance, silhouette = wall[:8]

            # Skip portal walls (silhouette=0) - these are openings, not solid walls
            if silhouette == 0:
                continue

            # Define 4 edges of wireframe box
            edges = [
                (x1, y1_top, x2, y2_top),          # Top edge
                (x1, y1_bottom, x2, y2_bottom),    # Bottom edge
                (x1, y1_top, x1, y1_bottom),       # Left edge
                (x2, y2_top, x2, y2_bottom)        # Right edge
            ]

            # Render each edge as a separate trace
            for (sx, sy, ex, ey) in edges:
                # Check pool capacity
                if trace_index >= len(trace_pool.objects):
                    if DEBUG_MODE:
                        print(f"WARNING: Trace pool exhausted at {trace_index}")
                    break

                # Get trace from pool (reuse existing object)
                trace = trace_pool.get(trace_index)
                trace_index += 1

                # Convert DOOM coordinates to KiCad coordinates
                kicad_sx, kicad_sy = CoordinateTransform.doom_to_kicad(sx, sy)
                kicad_ex, kicad_ey = CoordinateTransform.doom_to_kicad(ex, ey)

                # Update trace geometry
                trace.SetStart(pcbnew.VECTOR2I(kicad_sx, kicad_sy))
                trace.SetEnd(pcbnew.VECTOR2I(kicad_ex, kicad_ey))

                # Encode distance as layer and width
                # Close walls: F.Cu (red), thick traces (bright)
                # Far walls: B.Cu (cyan), thin traces (dim)
                if distance < DISTANCE_THRESHOLD:
                    trace.SetLayer(pcbnew.F_Cu)
                    trace.SetWidth(TRACE_WIDTH_CLOSE)
                else:
                    trace.SetLayer(pcbnew.B_Cu)
                    trace.SetWidth(TRACE_WIDTH_FAR)

                # Set net (required for electrical authenticity)
                trace.SetNet(self.doom_net)

        # Return number of traces used (caller will hide unused traces after entities)
        return trace_index

    def _render_entities(self, entities, start_index):
        """
        Render player and enemies as wireframe rectangles.

        Each entity becomes 4 PCB_TRACK objects (wireframe box):
        - Top edge: (x_left, y_top) → (x_right, y_top)
        - Bottom edge: (x_left, y_bottom) → (x_right, y_bottom)
        - Left edge: (x_left, y_top) → (x_left, y_bottom)
        - Right edge: (x_right, y_top) → (x_right, y_bottom)

        Entities use consistent styling (always F.Cu, thicker traces) to distinguish
        from walls.

        Args:
            entities: List of dicts with keys: x, y_top, y_bottom, height, type, distance
                     OR legacy format: (x, y, type, angle) tuples
            start_index: Index in trace pool where entity traces start (after walls)

        Returns:
            int: Number of traces used for entities
        """
        trace_pool = self.pools['traces']
        trace_index = start_index
        traces_used = 0

        for entity in entities:
            # Check if this is wireframe format (dict) or legacy format (tuple)
            if isinstance(entity, dict):
                # Wireframe format: {"x": X, "y_top": Yt, "y_bottom": Yb, "height": H, "type": T, "distance": D}
                x = entity.get('x', 0)
                y_top = entity.get('y_top', 0)
                y_bottom = entity.get('y_bottom', 0)
                height = entity.get('height', 16)  # Default sprite width (DOOM units)
                distance = entity.get('distance', 0)

                # Calculate rectangle corners
                # Entity width is centered on x coordinate
                half_width = height / 2
                x_left = x - half_width
                x_right = x + half_width

                # Define 4 edges of wireframe box
                edges = [
                    (x_left, y_top, x_right, y_top),      # Top edge
                    (x_left, y_bottom, x_right, y_bottom), # Bottom edge
                    (x_left, y_top, x_left, y_bottom),    # Left edge
                    (x_right, y_top, x_right, y_bottom)   # Right edge
                ]

                # Render each edge as a separate trace
                for (sx, sy, ex, ey) in edges:
                    # Check pool capacity
                    if trace_index >= len(trace_pool.objects):
                        if DEBUG_MODE:
                            print(f"WARNING: Trace pool exhausted at {trace_index} (entities)")
                        break

                    # Get trace from pool (reuse existing object)
                    trace = trace_pool.get(trace_index)
                    trace_index += 1
                    traces_used += 1

                    # Convert DOOM coordinates to KiCad coordinates
                    kicad_sx, kicad_sy = CoordinateTransform.doom_to_kicad(sx, sy)
                    kicad_ex, kicad_ey = CoordinateTransform.doom_to_kicad(ex, ey)

                    # Update trace geometry
                    trace.SetStart(pcbnew.VECTOR2I(kicad_sx, kicad_sy))
                    trace.SetEnd(pcbnew.VECTOR2I(kicad_ex, kicad_ey))

                    # Entities always use F.Cu layer (consistent visibility)
                    # Use slightly thicker traces than walls to distinguish entities
                    trace.SetLayer(pcbnew.F_Cu)
                    trace.SetWidth(TRACE_WIDTH_CLOSE)  # Always bright/thick for entities

                    # Set net (required for electrical authenticity)
                    trace.SetNet(self.doom_net)

            else:
                # Legacy format: (x, y, type, angle) - not supported in wireframe mode
                # This is only for backwards compatibility during migration
                if DEBUG_MODE:
                    print(f"WARNING: Legacy entity format not supported in wireframe mode")
                continue

        # Return number of traces used for entities
        return traces_used

    def _render_projectiles(self, projectiles):
        """
        Render bullets/projectiles as vias.

        Each projectile becomes a PCB_VIA (drilled hole).
        Vias are visually distinctive and electrically authentic.

        Args:
            projectiles: List of (x, y) tuples
        """
        via_pool = self.pools['vias']
        via_index = 0

        for projectile in projectiles:
            if len(projectile) < 2:
                continue  # Invalid projectile data

            x, y = projectile[:2]

            # Get via from pool
            via = via_pool.get(via_index)
            via_index += 1

            # Convert coordinates
            kicad_x, kicad_y = CoordinateTransform.doom_to_kicad(x, y)

            # Update position
            via.SetPosition(pcbnew.VECTOR2I(kicad_x, kicad_y))

            # Set net (same as walls/entities)
            via.SetNet(self.doom_net)

        # Hide unused vias (move off-screen)
        via_pool.hide_unused(via_index)

    def _render_hud(self, hud):
        """
        Render HUD elements as silkscreen text.

        HUD includes: health, ammo, armor, keys, face, etc.
        Rendered on F.SilkS layer (white silkscreen).

        Args:
            hud: Dictionary with HUD data:
                health: int (0-100+)
                ammo: int
                armor: int (0-100+)
                keys: list of key colors
                face: str (face state)
        """
        text_pool = self.pools['text']
        text_index = 0

        # HUD positions (in DOOM screen coordinates)
        hud_elements = []

        # Health
        health = hud.get('health', 100)
        hud_elements.append((10, 190, f"HEALTH: {health}%"))

        # Ammo
        ammo = hud.get('ammo', 0)
        hud_elements.append((80, 190, f"AMMO: {ammo}"))

        # Armor
        armor = hud.get('armor', 0)
        hud_elements.append((150, 190, f"ARMOR: {armor}%"))

        # Keys
        keys = hud.get('keys', [])
        if keys:
            keys_str = ' '.join(k.upper() for k in keys)
            hud_elements.append((220, 190, f"KEYS: {keys_str}"))

        # Render each HUD element
        for doom_x, doom_y, text in hud_elements:
            text_obj = text_pool.get(text_index)
            text_index += 1

            # Convert coordinates
            kicad_x, kicad_y = CoordinateTransform.doom_to_kicad(doom_x, doom_y)

            # Update text
            text_obj.SetText(text)
            text_obj.SetPosition(pcbnew.VECTOR2I(kicad_x, kicad_y))
            text_obj.SetLayer(pcbnew.F_SilkS)

        # Hide unused text elements
        text_pool.hide_unused(text_index)

    def _periodic_cleanup(self):
        """
        Periodic maintenance to prevent performance degradation.

        Called every CLEANUP_INTERVAL frames (default: 500).
        - Forces garbage collection
        - Logs memory usage
        - Checks for object count anomalies
        """
        if DEBUG_MODE:
            print(f"\nPerforming cleanup at frame {self.frame_count}...")

        # Force Python garbage collection
        gc.collect()

        # Log memory usage (if psutil available)
        try:
            import psutil
            import os
            process = psutil.Process(os.getpid())
            mem_mb = process.memory_info().rss / 1024 / 1024
            if DEBUG_MODE:
                print(f"Memory usage: {mem_mb:.1f} MB")
        except ImportError:
            pass

        # Check board object counts
        try:
            track_count = len(list(self.board.GetTracks()))
            if track_count > 1000:
                print(f"WARNING: Board has {track_count} tracks "
                      f"(expected < 1000)")
        except:
            pass

    def _log_statistics(self):
        """Log rendering statistics."""
        if self.frame_count == 0:
            return

        avg_total = self.total_render_time / self.frame_count
        avg_update = self.total_update_time / self.frame_count
        avg_refresh = self.total_refresh_time / self.frame_count
        avg_fps = self.frame_count / self.total_render_time

        print(f"\n{'=' * 70}")
        print(f"Rendering Statistics (Frame {self.frame_count})")
        print(f"{'=' * 70}")
        print(f"Average FPS: {avg_fps:.1f}")
        print(f"Average frame time: {avg_total*1000:.2f}ms")
        print(f"  Update time: {avg_update*1000:.2f}ms "
              f"({avg_update/avg_total*100:.1f}%)")
        print(f"  Refresh time: {avg_refresh*1000:.2f}ms "
              f"({avg_refresh/avg_total*100:.1f}%)")
        print(f"Slow frames: {self.slow_frame_count} "
              f"({self.slow_frame_count/self.frame_count*100:.1f}%)")
        print(f"{'=' * 70}\n")

    def get_statistics(self):
        """
        Get rendering statistics.

        Returns:
            dict: Statistics including FPS, frame times, etc.
        """
        if self.frame_count == 0:
            return {}

        avg_total = self.total_render_time / self.frame_count
        avg_fps = self.frame_count / self.total_render_time

        return {
            'frame_count': self.frame_count,
            'avg_fps': avg_fps,
            'avg_frame_time_ms': avg_total * 1000,
            'total_render_time': self.total_render_time,
            'slow_frame_count': self.slow_frame_count,
        }

    def start_refresh_timer(self, interval_ms=33):
        """
        Start a timer that calls Refresh() on the main thread.

        This MUST be called from the main thread (where wx event loop runs).
        The timer will call pcbnew.Refresh() at regular intervals.

        Args:
            interval_ms: Refresh interval in milliseconds (default: 33ms = ~30 FPS)
        """
        if self.refresh_timer:
            print("WARNING: Refresh timer already running")
            return

        # Create and start timer (must be on main thread)
        self.refresh_timer = wx.Timer()
        self.refresh_timer.Bind(wx.EVT_TIMER, self._on_refresh_timer)
        self.refresh_timer.Start(interval_ms)

        print(f"✓ Started refresh timer ({1000/interval_ms:.1f} FPS max)")

    def _on_refresh_timer(self, event):
        """
        Timer callback - runs on MAIN THREAD.

        Processes queued frames and refreshes display.
        This is where ALL PCB modifications happen (thread-safe).
        """
        # Check if there's a frame to process
        try:
            # Get frame from queue (non-blocking)
            frame_data = self.frame_queue.get_nowait()

            # Process frame on main thread (safe!)
            self._process_frame(frame_data)

            # Refresh display after updating PCB objects
            refresh_start = time.time()
            try:
                pcbnew.Refresh()
            except Exception as e:
                if DEBUG_MODE:
                    print(f"ERROR: Refresh failed: {e}")
            refresh_time = time.time() - refresh_start
            self.total_refresh_time += refresh_time

        except queue.Empty:
            # No frame available - that's okay, just wait for next timer event
            pass
        except Exception as e:
            if DEBUG_MODE:
                print(f"ERROR: Timer callback failed: {e}")
                import traceback
                traceback.print_exc()

    def stop_refresh_timer(self):
        """
        Stop the refresh timer.

        Safe to call multiple times or if timer not running.
        """
        if self.refresh_timer:
            self.refresh_timer.Stop()
            self.refresh_timer = None
            print("✓ Stopped refresh timer")

    def cleanup(self):
        """
        Cleanup renderer and hide all objects.

        Call this when DOOM exits to clean up the board.
        """
        print("\nCleaning up renderer...")

        # Stop refresh timer first
        self.stop_refresh_timer()

        # Hide all objects
        for pool_name, pool in self.pools.items():
            try:
                pool.reset_all()
            except:
                pass

        # Final refresh (safe to call directly if on main thread, or skip if not)
        try:
            pcbnew.Refresh()
        except:
            pass

        # Log final statistics
        if self.frame_count > 0:
            print("\n" + "=" * 70)
            print("Final Rendering Statistics")
            print("=" * 70)
            stats = self.get_statistics()
            print(f"Total frames rendered: {stats['frame_count']}")
            print(f"Average FPS: {stats['avg_fps']:.1f}")
            print(f"Average frame time: {stats['avg_frame_time_ms']:.2f}ms")
            print(f"Total runtime: {stats['total_render_time']:.1f}s")
            print(f"Slow frames: {stats['slow_frame_count']} "
                  f"({stats['slow_frame_count']/stats['frame_count']*100:.1f}%)")
            print("=" * 70)

        print("✓ Renderer cleaned up")
