"""
Coordinate system transformation utilities.

Handles conversion between DOOM screen coordinates and KiCad board coordinates.

DOOM coordinate system:
    - Origin (0,0) at top-left corner
    - X increases right (0 to 320)
    - Y increases down (0 to 200)
    - Units: pixels

KiCad coordinate system:
    - Origin (0,0) at arbitrary board location (typically center)
    - X increases right
    - Y increases DOWN on screen (same as DOOM - higher Y = lower on screen)
    - Units: nanometers (nm)
"""

from .config import DOOM_WIDTH, DOOM_HEIGHT, DOOM_TO_NM


class CoordinateTransform:
    """
    Transforms coordinates between DOOM and KiCad coordinate systems.

    Example usage:
        doom_x, doom_y = 160, 100  # Center of DOOM screen
        kicad_x, kicad_y = CoordinateTransform.doom_to_kicad(doom_x, doom_y)
        # Result: (0, 0) - centered on board origin
    """

    # Screen dimensions
    DOOM_WIDTH = DOOM_WIDTH
    DOOM_HEIGHT = DOOM_HEIGHT

    # Scale factor
    SCALE = DOOM_TO_NM

    # Center offsets (for centering DOOM screen on board origin)
    CENTER_X = DOOM_WIDTH / 2
    CENTER_Y = DOOM_HEIGHT / 2

    # A4 landscape page center offset (in nanometers)
    # A4 landscape: 297mm x 210mm, center at (148.5mm, 105mm)
    A4_CENTER_X_NM = 148500000  # 148.5mm in nm
    A4_CENTER_Y_NM = 105000000  # 105mm in nm

    @staticmethod
    def doom_to_kicad(doom_x, doom_y):
        """
        Convert DOOM screen coordinates to KiCad board coordinates.

        Args:
            doom_x: X coordinate in DOOM screen space (0-320)
            doom_y: Y coordinate in DOOM screen space (0-200)

        Returns:
            tuple: (kicad_x_nm, kicad_y_nm) in nanometers

        Example:
            >>> CoordinateTransform.doom_to_kicad(0, 0)
            (68500000, 55000000)  # Top-left corner (centered on A4)

            >>> CoordinateTransform.doom_to_kicad(160, 100)
            (148500000, 105000000)  # Center (A4 page center)

            >>> CoordinateTransform.doom_to_kicad(320, 200)
            (228500000, 155000000)  # Bottom-right corner
        """
        # Center the coordinate system (relative to DOOM center)
        x_centered = doom_x - CoordinateTransform.CENTER_X
        y_centered = doom_y - CoordinateTransform.CENTER_Y

        # No Y flip needed - both DOOM and KiCad have Y increasing downward on screen
        # (KiCad's engineering coordinate system has Y "up" mathematically,
        #  but on screen, higher Y values appear lower/toward bottom)

        # Scale to nanometers
        kicad_x = int(x_centered * CoordinateTransform.SCALE)
        kicad_y = int(y_centered * CoordinateTransform.SCALE)

        # Offset to center on A4 page
        kicad_x += CoordinateTransform.A4_CENTER_X_NM
        kicad_y += CoordinateTransform.A4_CENTER_Y_NM

        return kicad_x, kicad_y

    @staticmethod
    def kicad_to_doom(kicad_x_nm, kicad_y_nm):
        """
        Convert KiCad board coordinates to DOOM screen coordinates.

        Args:
            kicad_x_nm: X coordinate in nanometers
            kicad_y_nm: Y coordinate in nanometers

        Returns:
            tuple: (doom_x, doom_y) in pixels

        Note: This is rarely needed, but provided for completeness.
        """
        # Remove A4 page offset
        kicad_x_nm -= CoordinateTransform.A4_CENTER_X_NM
        kicad_y_nm -= CoordinateTransform.A4_CENTER_Y_NM

        # Unscale from nanometers
        x_unscaled = kicad_x_nm / CoordinateTransform.SCALE
        y_unscaled = kicad_y_nm / CoordinateTransform.SCALE

        # No Y unflip needed (wasn't flipped in forward transform)

        # Uncenter
        doom_x = x_unscaled + CoordinateTransform.CENTER_X
        doom_y = y_unscaled + CoordinateTransform.CENTER_Y

        return int(doom_x), int(doom_y)

    @staticmethod
    def get_board_bounds():
        """
        Get the bounding box for DOOM screen in KiCad coordinates.

        Returns:
            tuple: (min_x_nm, min_y_nm, max_x_nm, max_y_nm)

        This is useful for:
        - Setting board edge cuts
        - Determining board size
        - Checking if objects are on-screen
        """
        # DOOM screen corners
        top_left = CoordinateTransform.doom_to_kicad(0, 0)
        bottom_right = CoordinateTransform.doom_to_kicad(
            CoordinateTransform.DOOM_WIDTH,
            CoordinateTransform.DOOM_HEIGHT
        )

        min_x = min(top_left[0], bottom_right[0])
        max_x = max(top_left[0], bottom_right[0])
        min_y = min(top_left[1], bottom_right[1])
        max_y = max(top_left[1], bottom_right[1])

        return min_x, min_y, max_x, max_y

    @staticmethod
    def get_board_size_mm():
        """
        Get the board size in millimeters.

        Returns:
            tuple: (width_mm, height_mm)
        """
        min_x, min_y, max_x, max_y = CoordinateTransform.get_board_bounds()

        width_nm = max_x - min_x
        height_nm = max_y - min_y

        width_mm = width_nm / 1000000
        height_mm = height_nm / 1000000

        return width_mm, height_mm

    @staticmethod
    def is_on_screen(doom_x, doom_y):
        """
        Check if DOOM coordinates are within screen bounds.

        Args:
            doom_x: X coordinate in DOOM space
            doom_y: Y coordinate in DOOM space

        Returns:
            bool: True if coordinates are on screen
        """
        return (0 <= doom_x < CoordinateTransform.DOOM_WIDTH and
                0 <= doom_y < CoordinateTransform.DOOM_HEIGHT)

    @staticmethod
    def clamp_to_screen(doom_x, doom_y):
        """
        Clamp DOOM coordinates to screen bounds.

        Args:
            doom_x: X coordinate in DOOM space
            doom_y: Y coordinate in DOOM space

        Returns:
            tuple: (clamped_x, clamped_y)
        """
        x = max(0, min(doom_x, CoordinateTransform.DOOM_WIDTH - 1))
        y = max(0, min(doom_y, CoordinateTransform.DOOM_HEIGHT - 1))
        return x, y


def debug_coordinate_system():
    """
    Print debug information about coordinate transformations.

    Useful for verifying the coordinate system is set up correctly.
    """
    print("=" * 70)
    print("KiDoom Coordinate System Debug")
    print("=" * 70)

    print("\nDOOM screen dimensions:")
    print(f"  Width:  {DOOM_WIDTH} pixels")
    print(f"  Height: {DOOM_HEIGHT} pixels")
    print(f"  Scale:  {DOOM_TO_NM} nm/pixel ({DOOM_TO_NM/1000000} mm/pixel)")

    print("\nBoard size:")
    width_mm, height_mm = CoordinateTransform.get_board_size_mm()
    print(f"  Width:  {width_mm} mm")
    print(f"  Height: {height_mm} mm")

    print("\nBoard bounds (nanometers):")
    min_x, min_y, max_x, max_y = CoordinateTransform.get_board_bounds()
    print(f"  Min X: {min_x:>12} nm ({min_x/1000000:>7.2f} mm)")
    print(f"  Max X: {max_x:>12} nm ({max_x/1000000:>7.2f} mm)")
    print(f"  Min Y: {min_y:>12} nm ({min_y/1000000:>7.2f} mm)")
    print(f"  Max Y: {max_y:>12} nm ({max_y/1000000:>7.2f} mm)")

    print("\nKey coordinate mappings:")
    test_points = [
        ("Top-left", 0, 0),
        ("Top-right", DOOM_WIDTH, 0),
        ("Center", DOOM_WIDTH/2, DOOM_HEIGHT/2),
        ("Bottom-left", 0, DOOM_HEIGHT),
        ("Bottom-right", DOOM_WIDTH, DOOM_HEIGHT),
    ]

    for name, dx, dy in test_points:
        kx, ky = CoordinateTransform.doom_to_kicad(dx, dy)
        print(f"  {name:15} DOOM({dx:>5.0f}, {dy:>5.0f}) -> "
              f"KiCad({kx:>10}, {ky:>10}) nm")

    print("=" * 70)


if __name__ == "__main__":
    # Run debug output when executed directly
    debug_coordinate_system()
