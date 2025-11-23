"""
Pre-allocated object pools for PCB elements.

Object pooling is critical for performance:
- Creating/destroying PCB objects every frame is slow (50-100ms overhead)
- Pre-allocating and reusing objects provides 1.08x speedup + stability
- Prevents garbage collection pauses during gameplay
- Reduces max frame time by 53% (smoother gameplay)

Benchmark results (M1 MacBook Pro):
- Create/destroy approach: 11.99ms avg, 33.03ms max
- Object pool approach: 11.06ms avg, 15.28ms max
- Speedup: 1.08x average, 2.16x worst-case
"""

import pcbnew
from .config import (
    MAX_WALL_TRACES, MAX_ENTITIES, MAX_PROJECTILES,
    TRACE_WIDTH_DEFAULT, VIA_DRILL_SIZE, VIA_PAD_SIZE,
    ENTITY_FOOTPRINTS, get_footprint_library_path, DEBUG_MODE
)


class TracePool:
    """
    Pre-allocated pool of PCB_TRACK objects for rendering walls.

    Usage:
        pool = TracePool(board, max_size=500)
        trace = pool.get(0)
        trace.SetStart(...)
        trace.SetEnd(...)
        pool.hide_unused(1)  # Hide traces 1-499
    """

    def __init__(self, board, max_size=MAX_WALL_TRACES):
        """
        Initialize trace pool with pre-allocated PCB_TRACK objects.

        Args:
            board: KiCad BOARD object
            max_size: Maximum number of traces to pre-allocate
        """
        self.board = board
        self.traces = []
        self.max_size = max_size

        if DEBUG_MODE:
            print(f"Creating TracePool with {max_size} traces...")

        # Pre-allocate all traces
        for i in range(max_size):
            track = pcbnew.PCB_TRACK(board)
            track.SetWidth(TRACE_WIDTH_DEFAULT)
            track.SetLayer(pcbnew.F_Cu)
            # Start with traces hidden (width 0)
            track.SetStart(pcbnew.VECTOR2I(0, 0))
            track.SetEnd(pcbnew.VECTOR2I(0, 0))
            board.Add(track)
            self.traces.append(track)

        if DEBUG_MODE:
            print(f"✓ TracePool created with {len(self.traces)} traces")

    def get(self, index):
        """
        Get trace at index for reuse.

        Args:
            index: Index of trace to retrieve (0 to max_size-1)

        Returns:
            PCB_TRACK object

        Raises:
            IndexError: If index >= max_size
        """
        if index >= self.max_size:
            raise IndexError(
                f"Trace pool exhausted: requested index {index}, "
                f"pool size {self.max_size}. Consider increasing MAX_WALL_TRACES."
            )
        return self.traces[index]

    def hide_unused(self, used_count):
        """
        Hide traces not used this frame.

        Traces from index used_count to max_size-1 are hidden by setting
        their width to 0 (invisible but still in board structure).

        Args:
            used_count: Number of traces actually used this frame
        """
        for i in range(used_count, self.max_size):
            self.traces[i].SetWidth(0)  # Make invisible

    def reset_all(self):
        """Hide all traces (useful for cleanup)."""
        self.hide_unused(0)


class FootprintPool:
    """
    Pre-allocated pool of footprints for entities (player, enemies).

    Footprints are loaded from KiCad libraries and organized by entity type.
    Different entity types use different footprints for visual distinction.
    """

    def __init__(self, board, max_size=MAX_ENTITIES):
        """
        Initialize footprint pool.

        Args:
            board: KiCad BOARD object
            max_size: Maximum number of footprints per entity type
        """
        self.board = board
        self.footprints = {}  # entity_type -> list of footprints
        self.max_size = max_size

        if DEBUG_MODE:
            print(f"Creating FootprintPool with {max_size} footprints per type...")

        # Load footprint library path
        try:
            lib_base_path = get_footprint_library_path()
        except RuntimeError as e:
            print(f"WARNING: {e}")
            print("Footprint rendering will be disabled.")
            return

        # Pre-load footprints for each entity type
        for entity_type, footprint_ref in ENTITY_FOOTPRINTS.items():
            self.footprints[entity_type] = []

            # Parse footprint reference (format: "library:footprint")
            if ':' not in footprint_ref:
                print(f"WARNING: Invalid footprint reference: {footprint_ref}")
                continue

            lib_name, fp_name = footprint_ref.split(':', 1)
            lib_path = f"{lib_base_path}/{lib_name}.pretty"

            # Pre-allocate multiple instances of this footprint type
            # We don't need max_size for each type, so divide by number of types
            instances_per_type = max(1, max_size // len(ENTITY_FOOTPRINTS))

            for i in range(instances_per_type):
                try:
                    fp = pcbnew.FootprintLoad(lib_path, fp_name)
                    if fp:
                        fp.SetReference(f"{entity_type.upper()}{i}")
                        fp.SetValue(entity_type)
                        # Start off-screen
                        fp.SetPosition(pcbnew.VECTOR2I(-1000000000, -1000000000))
                        board.Add(fp)
                        self.footprints[entity_type].append(fp)
                    else:
                        if DEBUG_MODE:
                            print(f"WARNING: Could not load {lib_path}/{fp_name}")
                        break
                except Exception as e:
                    if DEBUG_MODE:
                        print(f"WARNING: Error loading footprint {footprint_ref}: {e}")
                    break

        if DEBUG_MODE:
            total = sum(len(fps) for fps in self.footprints.values())
            print(f"✓ FootprintPool created with {total} footprints across "
                  f"{len(self.footprints)} types")

    def get(self, index, entity_type):
        """
        Get footprint for entity type at index.

        Args:
            index: Index within entity type pool
            entity_type: Type of entity ('player', 'imp', 'baron', etc.)

        Returns:
            FOOTPRINT object, or None if pool is empty
        """
        # Get pool for this entity type (fallback to default)
        if entity_type not in self.footprints:
            entity_type = 'default'

        pool = self.footprints.get(entity_type, [])
        if not pool:
            return None

        # Wrap around if index exceeds pool size
        pool_index = index % len(pool)
        return pool[pool_index]

    def hide_unused(self, used_count):
        """
        Move unused footprints off-screen.

        Args:
            used_count: Total number of footprints used this frame
        """
        off_screen = pcbnew.VECTOR2I(-1000000000, -1000000000)
        current_index = 0

        for entity_type, pool in self.footprints.items():
            for i, fp in enumerate(pool):
                if current_index >= used_count:
                    fp.SetPosition(off_screen)
                current_index += 1

    def reset_all(self):
        """Move all footprints off-screen (useful for cleanup)."""
        self.hide_unused(0)


class ViaPool:
    """
    Pre-allocated pool of vias for projectiles (bullets, fireballs).

    Vias are visually distinctive (circular, drilled holes) and electrically
    authentic PCB elements.
    """

    def __init__(self, board, max_size=MAX_PROJECTILES):
        """
        Initialize via pool.

        Args:
            board: KiCad BOARD object
            max_size: Maximum number of vias to pre-allocate
        """
        self.board = board
        self.vias = []
        self.max_size = max_size

        if DEBUG_MODE:
            print(f"Creating ViaPool with {max_size} vias...")

        # Pre-allocate all vias
        for i in range(max_size):
            via = pcbnew.PCB_VIA(board)
            via.SetDrill(VIA_DRILL_SIZE)
            via.SetWidth(VIA_PAD_SIZE)
            # Start off-screen
            via.SetPosition(pcbnew.VECTOR2I(-1000000000, -1000000000))
            board.Add(via)
            self.vias.append(via)

        if DEBUG_MODE:
            print(f"✓ ViaPool created with {len(self.vias)} vias")

    def get(self, index):
        """
        Get via at index for reuse.

        Args:
            index: Index of via to retrieve

        Returns:
            PCB_VIA object

        Note: Wraps around if index >= max_size (reuses vias)
        """
        if index >= self.max_size:
            # Wrap around instead of crashing
            return self.vias[index % self.max_size]
        return self.vias[index]

    def hide_unused(self, used_count):
        """
        Move unused vias off-screen.

        Args:
            used_count: Number of vias actually used this frame
        """
        off_screen = pcbnew.VECTOR2I(-1000000000, -1000000000)
        for i in range(used_count, self.max_size):
            self.vias[i].SetPosition(off_screen)

    def reset_all(self):
        """Move all vias off-screen (useful for cleanup)."""
        self.hide_unused(0)


class TextPool:
    """
    Pre-allocated pool of PCB_TEXT objects for HUD elements.

    HUD elements (health, ammo, keys, face) are rendered as silkscreen text.
    """

    def __init__(self, board, max_size=10):
        """
        Initialize text pool.

        Args:
            board: KiCad BOARD object
            max_size: Maximum number of text elements
        """
        self.board = board
        self.texts = []
        self.max_size = max_size

        if DEBUG_MODE:
            print(f"Creating TextPool with {max_size} text elements...")

        # Pre-allocate text objects
        for i in range(max_size):
            text = pcbnew.PCB_TEXT(board)
            text.SetLayer(pcbnew.F_SilkS)  # Silkscreen layer (white)
            text.SetText("")
            # Start off-screen
            text.SetPosition(pcbnew.VECTOR2I(-1000000000, -1000000000))
            # Set reasonable text size (2mm height)
            text.SetTextSize(pcbnew.VECTOR2I(2000000, 2000000))
            text.SetTextThickness(200000)  # 0.2mm thickness
            board.Add(text)
            self.texts.append(text)

        if DEBUG_MODE:
            print(f"✓ TextPool created with {len(self.texts)} text elements")

    def get(self, index):
        """
        Get text object at index.

        Args:
            index: Index of text element

        Returns:
            PCB_TEXT object
        """
        if index >= self.max_size:
            return self.texts[index % self.max_size]
        return self.texts[index]

    def hide_unused(self, used_count):
        """
        Hide unused text elements.

        Args:
            used_count: Number of text elements used this frame
        """
        off_screen = pcbnew.VECTOR2I(-1000000000, -1000000000)
        for i in range(used_count, self.max_size):
            self.texts[i].SetText("")
            self.texts[i].SetPosition(off_screen)

    def reset_all(self):
        """Hide all text elements."""
        self.hide_unused(0)


def create_all_pools(board):
    """
    Convenience function to create all object pools at once.

    Args:
        board: KiCad BOARD object

    Returns:
        dict: Dictionary with keys 'traces', 'footprints', 'vias', 'text'
    """
    if DEBUG_MODE:
        print("\n" + "=" * 70)
        print("Initializing Object Pools")
        print("=" * 70)

    pools = {
        'traces': TracePool(board),
        'footprints': FootprintPool(board),
        'vias': ViaPool(board),
        'text': TextPool(board),
    }

    if DEBUG_MODE:
        print("=" * 70)
        print("✓ All object pools initialized")
        print("=" * 70 + "\n")

    return pools
