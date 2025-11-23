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

    Usage:
        renderer = DoomPCBRenderer(board)
        renderer.render_frame(frame_data)
        # ... repeat for each frame ...
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
        Render a complete DOOM frame to PCB.

        This is the hot path - called 20-60 times per second.

        Args:
            frame_data: Dictionary containing:
                walls: List of wall segments [(x1, y1, x2, y2, distance), ...]
                entities: List of entities [(x, y, type, angle), ...]
                projectiles: List of projectiles [(x, y), ...]
                hud: Dictionary with HUD elements

        Performance breakdown (M1 MacBook Pro):
            - Trace updates: 0.44ms (3.6%)
            - Display refresh: 11.67ms (96.3%)
            - Total: 12.11ms (82.6 FPS)
        """
        frame_start = time.time()

        # Update PCB objects
        update_start = time.time()

        try:
            # 1. Render walls (most objects, highest priority)
            walls = frame_data.get('walls', [])
            self._render_walls(walls)

            # 2. Render entities (player, enemies)
            entities = frame_data.get('entities', [])
            self._render_entities(entities)

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

        # 5. Refresh display (this is the bottleneck)
        refresh_start = time.time()
        pcbnew.Refresh()
        refresh_time = time.time() - refresh_start
        self.total_refresh_time += refresh_time

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
        Render wall segments as PCB traces.

        Each wall becomes a PCB_TRACK object. Distance from player
        determines layer (F.Cu/B.Cu) and width (thick/thin).

        Args:
            walls: List of (x1, y1, x2, y2, distance) tuples
        """
        trace_pool = self.pools['traces']
        trace_index = 0

        for wall in walls:
            if len(wall) < 5:
                continue  # Invalid wall data

            x1, y1, x2, y2, distance = wall[:5]

            # Get trace from pool (reuse existing object)
            try:
                trace = trace_pool.get(trace_index)
            except IndexError:
                # Pool exhausted, skip remaining walls
                if DEBUG_MODE:
                    print(f"WARNING: Trace pool exhausted at {trace_index}")
                break

            trace_index += 1

            # Convert DOOM coordinates to KiCad coordinates
            kicad_x1, kicad_y1 = CoordinateTransform.doom_to_kicad(x1, y1)
            kicad_x2, kicad_y2 = CoordinateTransform.doom_to_kicad(x2, y2)

            # Update trace geometry
            trace.SetStart(pcbnew.VECTOR2I(kicad_x1, kicad_y1))
            trace.SetEnd(pcbnew.VECTOR2I(kicad_x2, kicad_y2))

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

        # Hide unused traces (set width to 0)
        trace_pool.hide_unused(trace_index)

    def _render_entities(self, entities):
        """
        Render player and enemies as footprints.

        Each entity becomes a real KiCad footprint (component).
        Different entity types use different footprints for visual distinction.

        Args:
            entities: List of (x, y, type, angle) tuples
        """
        footprint_pool = self.pools['footprints']
        footprint_index = 0

        for entity in entities:
            if len(entity) < 4:
                continue  # Invalid entity data

            x, y, entity_type, angle = entity[:4]

            # Get footprint from pool
            footprint = footprint_pool.get(footprint_index, entity_type)
            if not footprint:
                continue  # Footprint pool not available

            footprint_index += 1

            # Convert coordinates
            kicad_x, kicad_y = CoordinateTransform.doom_to_kicad(x, y)

            # Update position
            footprint.SetPosition(pcbnew.VECTOR2I(kicad_x, kicad_y))

            # Update rotation (DOOM angle to KiCad angle)
            # DOOM angles: 0 = east, 90 = north (counterclockwise)
            # KiCad angles: 0 = east, 90 = north (counterclockwise)
            # They match! Just need to convert to KiCad's EDA_ANGLE
            try:
                footprint.SetOrientation(
                    pcbnew.EDA_ANGLE(angle, pcbnew.DEGREES_T)
                )
            except AttributeError:
                # KiCad 5 compatibility (uses decidegrees)
                footprint.SetOrientation(int(angle * 10))

            # Ensure footprint is on correct layer
            layer_set = pcbnew.LSET()
            layer_set.addLayer(pcbnew.F_Cu)
            footprint.SetLayerSet(layer_set)

        # Hide unused footprints (move off-screen)
        footprint_pool.hide_unused(footprint_index)

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

    def cleanup(self):
        """
        Cleanup renderer and hide all objects.

        Call this when DOOM exits to clean up the board.
        """
        print("\nCleaning up renderer...")

        # Hide all objects
        for pool_name, pool in self.pools.items():
            try:
                pool.reset_all()
            except:
                pass

        # Final refresh
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
