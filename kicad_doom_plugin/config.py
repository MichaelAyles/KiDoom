"""
Configuration constants for KiDoom plugin.

All tunable parameters are centralized here for easy adjustment.
"""

import os

# ============================================================================
# Socket Communication
# ============================================================================

# Unix socket path for IPC between DOOM and Python
SOCKET_PATH = "/tmp/kicad_doom.sock"

# Socket timeout for connection (seconds)
SOCKET_TIMEOUT = 10.0

# Socket receive timeout during gameplay (seconds)
SOCKET_RECV_TIMEOUT = 1.0

# ============================================================================
# Object Pool Sizes
# ============================================================================

# Maximum number of wall traces per frame
# WIREFRAME MODE: Each wall = 4 edges (top, bottom, left, right)
# Typical DOOM frame: 30-70 walls x 4 edges = 120-280 traces
# Entities: 10 entities x 4 edges = 40 traces
# Total: ~320 traces per frame
# We pre-allocate 500 for safety margin
# Temporarily reduced to 100 for faster startup during testing
MAX_WALL_TRACES = 100

# Wireframe rendering parameters
EDGES_PER_WALL = 4  # Top, bottom, left, right edges
MAX_WALLS_PER_FRAME = 70  # Typical max walls visible
MAX_ENTITIES_PER_FRAME = 10  # Typical max entities visible

# Maximum number of entities (player + enemies)
# Typical: 1 player + 5-15 enemies
MAX_ENTITIES = 20

# Maximum number of projectiles (bullets, fireballs)
# Typical: 5-20 active projectiles
MAX_PROJECTILES = 50

# Maximum number of HUD text elements
MAX_HUD_ELEMENTS = 10

# ============================================================================
# Coordinate Transformation
# ============================================================================

# DOOM screen dimensions (pixels)
DOOM_WIDTH = 320
DOOM_HEIGHT = 200

# Scale factor: DOOM pixels to millimeters
# 0.5mm per pixel = 160mm x 100mm PCB for full screen
DOOM_TO_MM = 0.5

# Millimeters to nanometers (KiCad internal units)
MM_TO_NM = 1000000

# Combined scale: DOOM pixels to nanometers
DOOM_TO_NM = int(DOOM_TO_MM * MM_TO_NM)  # 500,000 nm per pixel

# ============================================================================
# PCB Rendering Parameters
# ============================================================================

# Trace widths (nanometers)
TRACE_WIDTH_CLOSE = 300000   # 0.3mm for close walls (bright)
TRACE_WIDTH_FAR = 150000     # 0.15mm for far walls (dim)
TRACE_WIDTH_DEFAULT = 200000 # 0.2mm default

# Via dimensions (nanometers)
VIA_DRILL_SIZE = 400000      # 0.4mm drill
VIA_PAD_SIZE = 600000        # 0.6mm pad

# Distance threshold for layer selection (DOOM units)
# Walls closer than this use F.Cu (red), farther use B.Cu (cyan)
DISTANCE_THRESHOLD = 100

# ============================================================================
# Entity Footprint Mappings
# ============================================================================

# Map DOOM entity types to KiCad footprint library references
# Format: "library_name:footprint_name"
ENTITY_FOOTPRINTS = {
    'player': 'Package_QFP:QFP-64_10x10mm_P0.5mm',
    'imp': 'Package_TO_SOT_SMD:SOT-23',
    'demon': 'Package_TO_SOT_SMD:SOT-23',
    'baron': 'Package_TO_THT:TO-220-3_Vertical',
    'cacodemon': 'Package_DIP:DIP-8_W7.62mm',
    'default': 'Package_TO_SOT_SMD:SOT-23',  # Fallback
}

# ============================================================================
# Performance Tuning
# ============================================================================

# HUD update frequency (frames)
# HUD doesn't change every frame, so we can update less frequently
HUD_UPDATE_INTERVAL = 5

# Cleanup interval (frames)
# Force garbage collection and check for memory leaks
CLEANUP_INTERVAL = 500

# Performance monitoring interval (frames)
# Log statistics every N frames
STATS_LOG_INTERVAL = 100

# Warning threshold for slow frames (seconds)
SLOW_FRAME_THRESHOLD = 0.050  # 50ms = 20 FPS

# Warning threshold for FPS degradation
MIN_ACCEPTABLE_FPS = 10.0

# ============================================================================
# File Paths
# ============================================================================

# DOOM binary path (relative to plugin directory)
DOOM_BINARY_NAME = "doomgeneric_kicad"

# WAD file path (relative to plugin directory)
WAD_FILE_NAME = "doom1.wad"


def get_plugin_directory():
    """Get the absolute path to the plugin directory."""
    return os.path.dirname(os.path.abspath(__file__))


def get_doom_binary_path():
    """Get the absolute path to the DOOM binary."""
    plugin_dir = get_plugin_directory()
    return os.path.join(plugin_dir, "doom", DOOM_BINARY_NAME)


def get_wad_file_path():
    """Get the absolute path to the WAD file."""
    plugin_dir = get_plugin_directory()
    return os.path.join(plugin_dir, "doom", WAD_FILE_NAME)


def get_footprint_library_path():
    """
    Get the KiCad footprint library path for the current OS.

    Returns:
        str: Absolute path to KiCad footprint library directory

    Raises:
        RuntimeError: If footprint library cannot be found
    """
    import platform

    # Try environment variable first (most reliable)
    kisysmod = os.getenv('KISYSMOD')
    if kisysmod and os.path.isdir(kisysmod):
        return kisysmod

    # Fallback: detect by OS
    system = platform.system()

    if system == 'Darwin':  # macOS
        paths = [
            '/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints',
            '/Applications/KiCad.app/Contents/SharedSupport/footprints',
        ]
    elif system == 'Linux':
        paths = [
            '/usr/share/kicad/footprints',
            '/usr/share/kicad-nightly/footprints',
        ]
    elif system == 'Windows':
        paths = [
            r'C:\Program Files\KiCad\share\kicad\footprints',
            r'C:\Program Files (x86)\KiCad\share\kicad\footprints',
        ]
    else:
        raise RuntimeError(f"Unsupported OS: {system}")

    # Check each path
    for path in paths:
        if os.path.isdir(path):
            return path

    raise RuntimeError(
        f"Could not find KiCad footprint library. Tried: {paths}\n"
        f"Please set KISYSMOD environment variable."
    )


# ============================================================================
# Message Protocol Constants
# ============================================================================

# Message types for socket communication
MSG_FRAME_DATA = 0x01      # DOOM -> Python: Frame rendering data
MSG_KEY_EVENT = 0x02       # Python -> DOOM: Keyboard event
MSG_INIT_COMPLETE = 0x03   # Python -> DOOM: Initialization complete
MSG_SHUTDOWN = 0x04        # Bidirectional: Request shutdown

# ============================================================================
# Debug Settings
# ============================================================================

# Enable verbose logging
DEBUG_MODE = os.getenv('KIDOOM_DEBUG', '0') == '1'

# Enable frame time logging
LOG_FRAME_TIMES = os.getenv('KIDOOM_LOG_FRAMES', '0') == '1'

# Enable socket communication logging
LOG_SOCKET = os.getenv('KIDOOM_LOG_SOCKET', '0') == '1'
