"""
Main KiCad ActionPlugin for DOOM on PCB.

This is the entry point when user clicks the plugin button in KiCad.
Orchestrates all components:
- Launches DOOM process
- Creates socket bridge
- Initializes renderer
- Starts input handler
- Manages lifecycle and cleanup

Usage:
    1. Open KiCad PCBnew
    2. Tools → External Plugins → DOOM on PCB
    3. Wait for DOOM to launch
    4. Play!
"""

import pcbnew
import os
import subprocess
import time

from .config import (
    get_doom_binary_path, get_wad_file_path, DEBUG_MODE
)
from .pcb_renderer import DoomPCBRenderer
from .doom_bridge import DoomBridge
from .input_handler import InputHandler


class DoomKiCadPlugin(pcbnew.ActionPlugin):
    """
    KiCad ActionPlugin to run DOOM using PCB traces as the display.

    Appears in: Tools → External Plugins → DOOM on PCB
    """

    def defaults(self):
        """
        Set plugin metadata shown in KiCad UI.

        This method is called by KiCad during plugin registration.
        """
        self.name = "DOOM on PCB"
        self.category = "Game"
        self.description = "Run DOOM using PCB traces as the rendering medium"
        self.show_toolbar_button = True
        self.icon_file_name = os.path.join(
            os.path.dirname(__file__),
            'doom_icon.png'
        )

    def Run(self):
        """
        Main entry point when plugin is activated.

        This is called when user clicks the plugin button.
        """
        # Get current board
        board = pcbnew.GetBoard()

        if not board:
            self._show_error("No board loaded!")
            return

        print("\n" + "=" * 70)
        print("=" * 70)
        print("     DOOM ON PCB - KiCad Plugin")
        print("=" * 70)
        print("=" * 70)

        # Display board info
        board_file = board.GetFileName()
        if board_file:
            print(f"\nBoard: {os.path.basename(board_file)}")
        else:
            print("\nBoard: Untitled (save before running for best results)")

        # Configure board for optimal performance
        print("\n" + "=" * 70)
        print("Configuring Board for Performance")
        print("=" * 70)
        self._configure_board_for_performance(board)

        # Check for DOOM binary
        doom_binary = get_doom_binary_path()
        if not os.path.exists(doom_binary):
            print(f"\nERROR: DOOM binary not found at: {doom_binary}")
            print("\nYou need to compile the DOOM engine first!")
            print("See README.md for build instructions.")
            self._show_error(
                "DOOM binary not found!\n\n"
                f"Expected: {doom_binary}\n\n"
                "Please compile doomgeneric_kicad first."
            )
            return

        print(f"\n✓ DOOM binary found: {doom_binary}")

        # Check for WAD file
        wad_file = get_wad_file_path()
        if not os.path.exists(wad_file):
            print(f"\nWARNING: WAD file not found at: {wad_file}")
            print("DOOM may not start without a WAD file.")

        # Create renderer
        print("\n" + "=" * 70)
        print("Creating Renderer")
        print("=" * 70)
        try:
            renderer = DoomPCBRenderer(board)
        except Exception as e:
            print(f"\nERROR: Failed to create renderer: {e}")
            if DEBUG_MODE:
                import traceback
                traceback.print_exc()
            self._show_error(f"Failed to create renderer:\n{e}")
            return

        # Create bridge (socket server)
        print("\n" + "=" * 70)
        print("Creating Communication Bridge")
        print("=" * 70)
        bridge = DoomBridge(renderer)

        # Create input handler
        input_handler = InputHandler(bridge)

        # Track components for cleanup
        doom_process = None

        try:
            # Start socket server (waits for DOOM to connect)
            bridge.start()

            # Launch DOOM process
            print("\n" + "=" * 70)
            print("Launching DOOM")
            print("=" * 70)
            print(f"Binary: {doom_binary}")
            print(f"Working directory: {os.path.dirname(doom_binary)}")

            doom_process = subprocess.Popen(
                [doom_binary],
                cwd=os.path.dirname(doom_binary),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            print(f"✓ DOOM process started (PID: {doom_process.pid})")

            # Give DOOM a moment to connect
            time.sleep(1)

            # Check if DOOM process is still alive
            if doom_process.poll() is not None:
                # Process already exited
                stdout, stderr = doom_process.communicate()
                print(f"\nERROR: DOOM exited immediately!")
                if stdout:
                    print(f"\nStdout:\n{stdout.decode('utf-8')}")
                if stderr:
                    print(f"\nStderr:\n{stderr.decode('utf-8')}")
                self._show_error(
                    "DOOM process exited immediately!\n\n"
                    "Check console for error messages."
                )
                return

            # Start input capture
            if input_handler.start():
                print("✓ Input handler started")
            else:
                print("WARNING: Input handler failed to start")
                print("Gameplay will not respond to keyboard input.")

            # Display gameplay instructions
            print("\n" + "=" * 70)
            print("=" * 70)
            print("     DOOM IS RUNNING!")
            print("=" * 70)
            print("=" * 70)
            print("\nControls:")
            print("  WASD          - Move (forward/back/strafe)")
            print("  Arrow keys    - Turn left/right")
            print("  Ctrl          - Fire weapon")
            print("  Space / E     - Use / Open doors")
            print("  1-7           - Select weapon")
            print("  Esc           - Menu / Quit")
            print("\nThe DOOM window should appear shortly.")
            print("Watch the PCB editor - traces will animate!")
            print("\nPress ESC in DOOM to quit when done.")
            print("=" * 70 + "\n")

            # Wait for DOOM process to exit
            # This blocks until user quits DOOM
            return_code = doom_process.wait()

            print(f"\nDOOM exited with code: {return_code}")

            # Check for errors
            if return_code != 0:
                stdout, stderr = doom_process.communicate()
                if stderr:
                    print(f"\nDOOM stderr:\n{stderr.decode('utf-8')}")

        except KeyboardInterrupt:
            print("\n\nInterrupted by user (Ctrl+C)")

        except Exception as e:
            print(f"\nERROR: Unexpected exception: {e}")
            if DEBUG_MODE:
                import traceback
                traceback.print_exc()

        finally:
            # Cleanup
            print("\n" + "=" * 70)
            print("Cleaning Up")
            print("=" * 70)

            # Stop input handler
            try:
                input_handler.stop()
                print("✓ Input handler stopped")
            except Exception as e:
                print(f"WARNING: Error stopping input handler: {e}")

            # Stop bridge
            try:
                bridge.stop()
                print("✓ Bridge stopped")
            except Exception as e:
                print(f"WARNING: Error stopping bridge: {e}")

            # Kill DOOM process if still running
            if doom_process and doom_process.poll() is None:
                try:
                    doom_process.terminate()
                    doom_process.wait(timeout=5)
                    print("✓ DOOM process terminated")
                except:
                    doom_process.kill()
                    print("✓ DOOM process killed")

            # Cleanup renderer
            try:
                renderer.cleanup()
                print("✓ Renderer cleaned up")
            except Exception as e:
                print(f"WARNING: Error cleaning up renderer: {e}")

            # Display final statistics
            print("\n" + "=" * 70)
            print("Session Summary")
            print("=" * 70)

            renderer_stats = renderer.get_statistics()
            bridge_stats = bridge.get_stats()

            print("\nRenderer Statistics:")
            if renderer_stats:
                print(f"  Frames rendered: {renderer_stats['frame_count']}")
                print(f"  Average FPS: {renderer_stats['avg_fps']:.1f}")
                print(f"  Total runtime: {renderer_stats['total_render_time']:.1f}s")
            else:
                print("  No frames rendered")

            print("\nBridge Statistics:")
            print(f"  Frames received: {bridge_stats['frames_received']}")
            print(f"  Receive errors: {bridge_stats['receive_errors']}")

            print("\n" + "=" * 70)
            print("DOOM on PCB - Session Complete")
            print("=" * 70 + "\n")

    def _configure_board_for_performance(self, board):
        """
        Apply performance optimizations to the board.

        These optimizations are applied automatically where possible.
        Some settings must be configured manually in KiCad UI.
        """
        try:
            # Get board design settings
            settings = board.GetDesignSettings()

            # Set to 2-layer board (F.Cu + B.Cu only)
            settings.SetCopperLayerCount(2)
            board.SetDesignSettings(settings)
            print("✓ Set to 2-layer board")

            # Enable only necessary layers
            layer_set = pcbnew.LSET()
            layer_set.addLayer(pcbnew.F_Cu)
            layer_set.addLayer(pcbnew.B_Cu)
            layer_set.addLayer(pcbnew.F_SilkS)  # For HUD text
            layer_set.addLayer(pcbnew.Edge_Cuts)  # Keep board outline
            board.SetEnabledLayers(layer_set)
            board.SetVisibleLayers(layer_set)
            print("✓ Enabled minimal layers")

            # Clear any existing highlighting
            board.SetHighLightNet(-1)
            print("✓ Cleared highlighting")

        except Exception as e:
            print(f"WARNING: Error configuring board: {e}")

        # Print manual optimization instructions
        print("\nMANUAL SETTINGS (for optimal performance):")
        print("  Please ensure these are configured in KiCad:")
        print("    1. View → Show Grid: OFF")
        print("    2. View → Ratsnest: OFF")
        print("    3. Preferences → Display Options:")
        print("       - Clearance outlines: OFF")
        print("       - Pad/Via holes: Do not show")
        print("    4. Preferences → Graphics:")
        print("       - Antialiasing: Fast or Disabled")
        print("       - Rendering engine: Accelerated")
        print("\n  These settings can improve FPS by 50-100%!")

    def _show_error(self, message):
        """
        Show error message to user.

        Args:
            message: Error message string
        """
        # Try to use wx if available
        try:
            import wx
            wx.MessageBox(message, "DOOM on PCB - Error", wx.OK | wx.ICON_ERROR)
        except:
            # Fall back to console only
            print(f"\nERROR: {message}")


# Note: Plugin is registered in __init__.py, not here
