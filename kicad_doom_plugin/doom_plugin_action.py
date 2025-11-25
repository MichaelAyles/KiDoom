"""
Enhanced KiCad ActionPlugin for DOOM on PCB (Triple Mode).

This version includes:
- File logging for debugging
- Non-blocking process management
- Python wireframe renderer support
- SDL DOOM window
- KiCad PCB rendering
- Coordinated shutdown

Triple Mode:
- SDL Window: Full DOOM graphics for gameplay
- Python Wireframe: Standalone wireframe renderer
- KiCad PCB: Wireframe rendering on PCB traces

All components monitored by background thread for clean shutdown.
"""

import pcbnew
import os
import subprocess
import time
import threading
import queue
import sys
import logging
from datetime import datetime

from .config import (
    get_doom_binary_path, get_wad_file_path, DEBUG_MODE
)
from .pcb_renderer import DoomPCBRenderer
from .doom_bridge import DoomBridge


class DoomKiCadPlugin(pcbnew.ActionPlugin):
    """
    Enhanced KiCad ActionPlugin with logging and multi-process management.
    """

    def __init__(self):
        super().__init__()
        self.setup_logging()

    def setup_logging(self):
        """Setup file logging for debugging."""
        # Create logs directory if it doesn't exist
        log_dir = os.path.expanduser("~/Desktop/Projects/KiDoom/logs/plugin")
        os.makedirs(log_dir, exist_ok=True)

        # Create timestamped log file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f"kidoom_{timestamp}.log")

        # Configure logging
        logging.basicConfig(
            level=logging.DEBUG if DEBUG_MODE else logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)  # Also log to console
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info("=" * 70)
        self.logger.info("KiDoom Plugin Initialized")
        self.logger.info(f"Log file: {log_file}")
        self.logger.info("=" * 70)

    def defaults(self):
        """Set plugin metadata."""
        self.name = "KiDoom - DOOM on PCB (Enhanced)"
        self.category = "Game"
        self.description = "Run DOOM with SDL + Python wireframe + PCB rendering"
        self.show_toolbar_button = True
        self.test_mode = os.environ.get('KIDOOM_TEST_MODE', '').lower() == 'true'

        icon_path = os.path.join(os.path.dirname(__file__), 'doom_icon.png')
        if os.path.exists(icon_path):
            self.icon_file_name = icon_path

    def Run(self):
        """Main entry point when plugin is activated."""
        try:
            self.logger.info("\n" + "=" * 70)
            self.logger.info("STARTING DOOM ON PCB")
            self.logger.info("=" * 70)

            # Get current board
            board = pcbnew.GetBoard()
            if not board:
                self._show_error("No board loaded!")
                self.logger.error("No board loaded!")
                return

            board_file = board.GetFileName() or "Untitled"
            self.logger.info(f"Board: {board_file}")

            # Check for test mode
            if self.test_mode:
                self.logger.info("Test mode enabled - running smiley test")
                self._run_smiley_test(board)
                return

            # Configure board for performance
            self.logger.info("Configuring board for performance...")
            self._configure_board_for_performance(board)

            # Check for DOOM binary
            doom_binary = get_doom_binary_path()
            self.logger.info(f"DOOM binary: {doom_binary}")
            if not os.path.exists(doom_binary):
                self.logger.error(f"DOOM binary not found at: {doom_binary}")
                self._show_error(f"DOOM binary not found!\n{doom_binary}")
                return

            # Check for WAD file
            wad_file = get_wad_file_path()
            self.logger.info(f"WAD file: {wad_file}")
            if not os.path.exists(wad_file):
                self.logger.warning(f"WAD file not found at: {wad_file}")

            # Create renderer
            self.logger.info("Creating PCB renderer...")
            try:
                renderer = DoomPCBRenderer(board)
                self.logger.info("Renderer created successfully")
            except Exception as e:
                self.logger.exception("Failed to create renderer")
                self._show_error(f"Failed to create renderer:\n{e}")
                return

            # Start refresh timer
            self.logger.info("Starting refresh timer...")
            try:
                renderer.start_refresh_timer(interval_ms=33)
                self.logger.info("Refresh timer started (30 FPS target)")
            except Exception as e:
                self.logger.warning(f"Failed to start refresh timer: {e}")

            # Create bridge (socket server)
            self.logger.info("Creating communication bridge...")
            bridge = DoomBridge(renderer)

            # Setup socket FIRST (creates and starts listening)
            self.logger.info("Setting up socket server...")
            bridge.setup_socket()
            self.logger.info("Socket server ready and listening")

            # NOW launch DOOM (it can connect immediately)
            self.logger.info("Launching DOOM processes...")
            processes = self._launch_processes(doom_binary)

            if not processes:
                self.logger.error("Failed to launch processes")
                self._cleanup(bridge, renderer, None, None)
                return

            doom_process = processes.get('doom')
            python_renderer = processes.get('python_renderer')

            # Accept the connection from DOOM (blocking but should be quick)
            self.logger.info("Waiting for DOOM to connect...")
            bridge.accept_connection()
            self.logger.info("DOOM connected successfully!")

            # Continue with monitoring

            # Display instructions
            self._display_instructions()

            # Start monitoring thread (non-blocking)
            self.logger.info("Starting monitor thread...")
            monitor_thread = threading.Thread(
                target=self._monitor_processes,
                args=(doom_process, python_renderer, bridge, renderer),
                daemon=True
            )
            monitor_thread.start()
            self.logger.info("Monitor thread started")

            # Store for potential cleanup
            self.active_components = {
                'bridge': bridge,
                'renderer': renderer,
                'doom_process': doom_process,
                'python_renderer': python_renderer,
                'monitor_thread': monitor_thread
            }

            self.logger.info("All components launched successfully!")
            self.logger.info("Plugin Run() method returning control to KiCad")

        except Exception as e:
            self.logger.exception("Unexpected error in Run()")
            self._show_error(f"Unexpected error:\n{e}")

    def _launch_processes(self, doom_binary):
        """Launch DOOM and Python renderer processes."""
        processes = {}

        try:
            # Launch DOOM (SDL window + socket connection)
            self.logger.info(f"Launching DOOM: {doom_binary}")
            doom_process = subprocess.Popen(
                [doom_binary],
                cwd=os.path.dirname(doom_binary),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            processes['doom'] = doom_process
            self.logger.info(f"DOOM launched (PID: {doom_process.pid})")

            # Give DOOM a moment to start
            time.sleep(1)

            # Check if DOOM is still running
            if doom_process.poll() is not None:
                stdout, stderr = doom_process.communicate()
                self.logger.error("DOOM exited immediately!")
                if stdout:
                    self.logger.error(f"DOOM stdout: {stdout.decode('utf-8')}")
                if stderr:
                    self.logger.error(f"DOOM stderr: {stderr.decode('utf-8')}")
                return None

            # Launch Python wireframe renderer
            # Navigate from plugin dir to project root
            plugin_dir = os.path.dirname(__file__)
            project_root = os.path.dirname(plugin_dir)
            python_renderer_path = os.path.join(project_root, "src", "standalone_renderer.py")

            if os.path.exists(python_renderer_path):
                self.logger.info(f"Launching Python renderer: {python_renderer_path}")
                python_renderer = subprocess.Popen(
                    [sys.executable, python_renderer_path],
                    cwd=os.path.dirname(python_renderer_path),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                processes['python_renderer'] = python_renderer
                self.logger.info(f"Python renderer launched (PID: {python_renderer.pid})")
            else:
                self.logger.warning(f"Python renderer not found at: {python_renderer_path}")
                processes['python_renderer'] = None

            return processes

        except Exception as e:
            self.logger.exception(f"Error launching processes: {e}")
            # Clean up any launched processes
            for name, proc in processes.items():
                if proc and proc.poll() is None:
                    self.logger.info(f"Terminating {name}...")
                    proc.terminate()
            return None

    def _monitor_processes(self, doom_process, python_renderer, bridge, renderer):
        """Monitor processes in background thread (non-blocking)."""
        self.logger.info("Monitor thread started - watching processes")
        self.logger.info("To stop DOOM: Close SDL window or Python renderer window")
        self.logger.info("KiCad will remain running after DOOM exits")

        try:
            while True:
                time.sleep(1)  # Check every second

                # Check if DOOM is still running
                if doom_process and doom_process.poll() is not None:
                    self.logger.info(f"DOOM exited with code: {doom_process.returncode}")
                    self.logger.info("Cleaning up other processes...")
                    break

                # Check if Python renderer is still running
                if python_renderer and python_renderer.poll() is not None:
                    self.logger.info(f"Python renderer exited with code: {python_renderer.returncode}")
                    self.logger.info("Cleaning up other processes...")
                    break

        except Exception as e:
            self.logger.exception(f"Monitor thread error: {e}")

        finally:
            self.logger.info("Monitor thread initiating safe cleanup (processes only)...")
            self._cleanup(bridge, renderer, doom_process, python_renderer)

    def _cleanup(self, bridge, renderer, doom_process, python_renderer):
        """Clean up all components."""
        self.logger.info("\n" + "=" * 70)
        self.logger.info("CLEANUP INITIATED")
        self.logger.info("=" * 70)

        # Stop bridge
        if bridge:
            try:
                bridge.stop()
                self.logger.info("Bridge stopped")
            except Exception as e:
                self.logger.warning(f"Error stopping bridge: {e}")

        # Kill DOOM process
        if doom_process and doom_process.poll() is None:
            try:
                doom_process.terminate()
                doom_process.wait(timeout=2)
                self.logger.info("DOOM process terminated")
            except subprocess.TimeoutExpired:
                doom_process.kill()
                self.logger.info("DOOM process killed")
            except Exception as e:
                self.logger.warning(f"Error stopping DOOM: {e}")

        # Kill Python renderer
        if python_renderer and python_renderer.poll() is None:
            try:
                python_renderer.terminate()
                python_renderer.wait(timeout=2)
                self.logger.info("Python renderer terminated")
            except subprocess.TimeoutExpired:
                python_renderer.kill()
                self.logger.info("Python renderer killed")
            except Exception as e:
                self.logger.warning(f"Error stopping Python renderer: {e}")

        # NOTE: Do NOT stop refresh timer or clean up renderer from background thread!
        # These involve wx objects which are NOT thread-safe.
        # Let KiCad's normal shutdown handle renderer cleanup.
        # The timer will be stopped when KiCad exits.
        self.logger.info("Renderer cleanup skipped (thread-safety - will cleanup on KiCad exit)")

        self.logger.info("Cleanup complete")
        self.logger.info("=" * 70 + "\n")

    def _display_instructions(self):
        """Display gameplay instructions."""
        instructions = """
======================================================================
                    DOOM IS RUNNING!
======================================================================

Triple Mode Active:
  1. SDL Window     - Full DOOM graphics (play here)
  2. Python Window  - Wireframe renderer (reference view)
  3. KiCad PCB      - Traces rendering (technical demo)

Controls (in SDL window):
  WASD          - Move (forward/back/strafe)
  Arrow keys    - Turn left/right
  Ctrl          - Fire weapon
  Space         - Use / Open doors
  1-7           - Select weapon
  Esc           - Menu / Quit

To Stop:
  - Press ESC in SDL window
  - Close Python wireframe window
  - Or use Tools -> External Plugins -> Refresh in KiCad

======================================================================
"""
        print(instructions)
        self.logger.info(instructions)

    def _configure_board_for_performance(self, board):
        """Configure board settings for optimal performance."""
        # Removed verbose print statements - just configure silently
        # Manual settings should be configured by user in KiCad UI
        pass

    def _show_error(self, message):
        """Show error dialog to user."""
        import wx
        wx.MessageBox(message, "KiDoom Error", wx.OK | wx.ICON_ERROR)

    def _run_smiley_test(self, board):
        """Run simple smiley face test."""
        self.logger.info("Running smiley test...")
        # Implementation would go here
        pass