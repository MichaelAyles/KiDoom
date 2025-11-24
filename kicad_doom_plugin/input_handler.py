"""
Keyboard input handler for DOOM controls.

Captures OS-level keyboard events using pynput and forwards them to DOOM
via the socket bridge.

Why pynput:
- KiCad's Python plugin doesn't provide event loop access
- Need global keyboard capture during gameplay
- Works across all platforms (macOS, Linux, Windows)

Warning:
- Captures keyboard globally (system-wide)
- May interfere with other applications if KiCad loses focus
- Should be stopped when DOOM exits

DOOM Key Mappings:
    Movement:
        W - Move forward
        S - Move backward
        A - Strafe left
        D - Strafe right

    Turning:
        Left Arrow - Turn left
        Right Arrow - Turn right

    Actions:
        Ctrl - Fire weapon
        Space - Use/Open doors
        E - Use (alternate)

    Weapons:
        1-7 - Select weapon

    Menu:
        Esc - Menu/Quit
"""

try:
    from pynput import keyboard
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
    print("WARNING: pynput not installed. Input will not work.")
    print("Install with: pip install pynput")

from .config import DEBUG_MODE


class DoomInputHandler:
    """
    Captures keyboard input at OS level and forwards to DOOM.

    Usage:
        handler = DoomInputHandler(bridge)
        handler.start()
        # ... gameplay ...
        handler.stop()
    """

    # DOOM key code mappings
    # See DOOM source: doomkeys.h for key codes
    KEY_MAP = {
        # Movement keys (WASD)
        'w': 0x77,  # Forward
        's': 0x73,  # Backward
        'a': 0x61,  # Strafe left
        'd': 0x64,  # Strafe right

        # Arrow keys for turning
        keyboard.Key.left: 0xAC,   # Turn left (KEY_LEFTARROW)
        keyboard.Key.right: 0xAE,  # Turn right (KEY_RIGHTARROW)
        keyboard.Key.up: 0xAD,     # Forward (KEY_UPARROW)
        keyboard.Key.down: 0xAF,   # Backward (KEY_DOWNARROW)

        # Action keys
        keyboard.Key.ctrl: 0x9D,      # Fire (KEY_RCTRL)
        keyboard.Key.ctrl_l: 0x9D,    # Fire (KEY_RCTRL)
        keyboard.Key.ctrl_r: 0x9D,    # Fire (KEY_RCTRL)
        keyboard.Key.space: 0x39,     # Use/Open (KEY_SPACE)
        'e': 0x45,                     # Use (KEY_USE)

        # Weapon selection
        '1': 0x31,  # Fist/Chainsaw
        '2': 0x32,  # Pistol
        '3': 0x33,  # Shotgun/Super Shotgun
        '4': 0x34,  # Chaingun
        '5': 0x35,  # Rocket Launcher
        '6': 0x36,  # Plasma Rifle
        '7': 0x37,  # BFG9000

        # Menu/System
        keyboard.Key.esc: 0x1B,       # Escape (KEY_ESCAPE)
        keyboard.Key.enter: 0x0D,     # Enter (KEY_ENTER)

        # Automap
        keyboard.Key.tab: 0x09,       # Show automap (KEY_TAB)

        # Strafe modifiers (alt keys)
        keyboard.Key.alt: 0xB8,       # Strafe on (KEY_RALT)
        keyboard.Key.alt_l: 0xB8,     # Strafe on (KEY_RALT)
        keyboard.Key.alt_r: 0xB8,     # Strafe on (KEY_RALT)

        # Shift for running
        keyboard.Key.shift: 0xB6,     # Run (KEY_RSHIFT)
        keyboard.Key.shift_l: 0xB6,   # Run (KEY_RSHIFT)
        keyboard.Key.shift_r: 0xB6,   # Run (KEY_RSHIFT)
    }

    def __init__(self, bridge):
        """
        Initialize input handler.

        Args:
            bridge: DoomBridge instance to send key events through
        """
        self.bridge = bridge
        self.listener = None
        self.pressed_keys = set()  # Track pressed keys to avoid repeats

        if not PYNPUT_AVAILABLE:
            print("ERROR: Input handler cannot start (pynput not installed)")

    def start(self):
        """
        Start keyboard listener in background.

        Returns:
            bool: True if started successfully, False if pynput unavailable
        """
        if not PYNPUT_AVAILABLE:
            return False

        print("\n" + "=" * 70)
        print("Starting Input Handler")
        print("=" * 70)
        print("Controls:")
        print("  WASD          - Move (forward/back/strafe)")
        print("  Arrow keys    - Turn left/right, move forward/back")
        print("  Ctrl          - Fire weapon")
        print("  Space / E     - Use / Open doors")
        print("  1-7           - Select weapon")
        print("  Shift         - Run")
        print("  Tab           - Show automap")
        print("  Esc           - Menu / Quit")
        print("=" * 70 + "\n")

        self.listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release
        )
        self.listener.start()

        if DEBUG_MODE:
            print("[OK] Input listener started")

        return True

    def _on_key_press(self, key):
        """
        Called when a key is pressed.

        Args:
            key: pynput key object
        """
        try:
            # Get character or special key
            if hasattr(key, 'char') and key.char is not None:
                key_char = key.char.lower()  # Normalize to lowercase
            else:
                key_char = key

            # Check if this key is mapped to a DOOM key
            if key_char in self.KEY_MAP:
                doom_key = self.KEY_MAP[key_char]

                # Only send if not already pressed (avoid key repeat)
                if doom_key not in self.pressed_keys:
                    self.pressed_keys.add(doom_key)
                    self.bridge.send_key_event(pressed=True, key_code=doom_key)

                    if DEBUG_MODE:
                        print(f"Key press: {key_char} -> DOOM key {doom_key:#04x}")

        except Exception as e:
            if DEBUG_MODE:
                print(f"ERROR: Key press handler failed: {e}")

    def _on_key_release(self, key):
        """
        Called when a key is released.

        Args:
            key: pynput key object
        """
        try:
            # Get character or special key
            if hasattr(key, 'char') and key.char is not None:
                key_char = key.char.lower()
            else:
                key_char = key

            # Check if this key is mapped to a DOOM key
            if key_char in self.KEY_MAP:
                doom_key = self.KEY_MAP[key_char]

                # Only send if actually pressed
                if doom_key in self.pressed_keys:
                    self.pressed_keys.remove(doom_key)
                    self.bridge.send_key_event(pressed=False, key_code=doom_key)

                    if DEBUG_MODE:
                        print(f"Key release: {key_char} -> DOOM key {doom_key:#04x}")

        except Exception as e:
            if DEBUG_MODE:
                print(f"ERROR: Key release handler failed: {e}")

    def stop(self):
        """
        Stop keyboard listener and cleanup.

        Safe to call multiple times.
        """
        if self.listener:
            try:
                self.listener.stop()
                if DEBUG_MODE:
                    print("[OK] Input listener stopped")
            except Exception as e:
                if DEBUG_MODE:
                    print(f"WARNING: Error stopping listener: {e}")
            finally:
                self.listener = None

        # Clear pressed keys
        self.pressed_keys.clear()

    def is_running(self):
        """
        Check if input handler is running.

        Returns:
            bool: True if listener is active
        """
        return self.listener is not None and self.listener.running


# Fallback stub for when pynput is not available
class DummyInputHandler:
    """
    Dummy input handler for when pynput is not installed.

    Provides same interface but does nothing.
    """

    def __init__(self, bridge):
        self.bridge = bridge
        print("WARNING: Using dummy input handler (pynput not available)")

    def start(self):
        print("WARNING: Input handler not started (install pynput)")
        return False

    def stop(self):
        pass

    def is_running(self):
        return False


# Export the appropriate handler based on pynput availability
if PYNPUT_AVAILABLE:
    InputHandler = DoomInputHandler
else:
    InputHandler = DummyInputHandler
