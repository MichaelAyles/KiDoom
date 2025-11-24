# Porting DOOM to KiCad PCBnew: Comprehensive Implementation Plan

## Executive Summary

This document outlines the complete implementation plan for running DOOM within KiCad's PCBnew using real PCB traces as the rendering medium. This is a technical demonstration ("tech demo") showing vector-based game rendering using authentic PCB design elements.

**Expected Performance:** 10-25 FPS (playable, but not smooth)
**Approach:** Vector rendering using PCB traces, not raster pixels
**Platform:** KiCad 6+ Python plugin API

---

## Table of Contents

1. [Why This Approach Works](#why-this-approach-works)
2. [Critical Performance Decisions](#critical-performance-decisions)
3. [Architecture Overview](#architecture-overview)
4. [Implementation Phases](#implementation-phases)
5. [Known Pitfalls and Solutions](#known-pitfalls-and-solutions)
6. [Testing and Benchmarking Strategy](#testing-and-benchmarking-strategy)
7. [Code Structure](#code-structure)
8. [API Reference and Gotchas](#api-reference-and-gotchas)

---

## Why This Approach Works

### The Evolution of the Idea

**Initial concept:** Render DOOM pixel-by-pixel using PCB pads
- **Problem:** 320x200 = 64,000 objects per frame
- **Math:** 0.1ms per object = 6.4 seconds per frame (0.15 FPS)
- **Verdict:** Completely unworkable

**Key insight:** Use vector rendering instead of raster
- DOOM's engine already calculates visible wall segments as vectors
- PCB traces ARE vectors (line segments)
- Typical frame: 100-300 line segments instead of 64,000 pixels
- **Performance gain:** 200-500x improvement
- **Verdict:** Actually feasible

**Authenticity requirement:** Must use real PCB objects
- Can't use `PCB_SHAPE` (just drawings, no electrical meaning)
- Must use `PCB_TRACK` (real copper traces)
- Must use `FOOTPRINT` (real components for player/enemies)
- Must use `PCB_VIA` (real vias for projectiles)
- **Result:** This is a legitimate PCB design that could be fabricated

---

## Critical Performance Decisions

### Decision Matrix

| Optimization | Impact | Why We're Doing It |
|-------------|--------|-------------------|
| **Vector rendering** | 200-500x speedup | Doom internally uses vectors; matches PCB trace paradigm |
| **Minimal layers (2 copper only)** | 30-40% speedup | Each layer adds rendering overhead even if empty |
| **Single shared net** | 20-30% speedup | Eliminates ratsnest calculation (airwire) overhead |
| **Disable DRC** | 20-40% speedup | Design rule checking adds massive overhead per trace |
| **Object reuse** | 3-5x speedup | Creating/destroying objects triggers memory management |
| **No grid display** | 5-10% speedup | Grid is recalculated and rendered every frame |
| **Disable antialiasing** | 5-15% speedup | MSAA adds GPU overhead |
| **Pre-allocate objects** | 3-5x speedup | Avoids Python/C++ allocation overhead in hot loop |

### Cumulative Effect

**Baseline (naive implementation):**
- 200 traces/frame × 0.5ms = 100ms
- + DRC overhead: +40ms
- + Ratsnest: +30ms
- + Grid: +10ms
- + Display list rebuild: +50ms
- **Total: 230ms = 4.3 FPS**

**Optimized implementation:**
- 200 trace updates (reused) × 0.1ms = 20ms
- + No DRC: +0ms
- + No ratsnest: +0ms
- + No grid: +0ms
- + Minimal layers: +0ms
- + Display list rebuild (optimized): +30ms
- **Total: 50ms = 20 FPS**

---

## Architecture Overview

### Component Mapping: DOOM → PCB

| DOOM Element | PCB Element | Layer | Justification |
|-------------|-------------|-------|---------------|
| Wall segments | `PCB_TRACK` | F.Cu | Real copper traces, electrically authentic |
| Floor/ceiling | `ZONE` (optional) | B.Cu | Filled copper pour, creates depth separation |
| Player (Doomguy) | `FOOTPRINT` | F.Cu | Actual component with reference designator "U1" |
| Enemies | `FOOTPRINT` | F.Cu | Different footprints per enemy type (SOT-23, TO-220, etc.) |
| Projectiles | `PCB_VIA` | All layers | Drilled holes, visually distinct, electrically authentic |
| HUD elements | `PCB_TEXT` | F.SilkS | Silkscreen text (white), ideal for UI overlay |
| Doors | `ZONE` (animated) | F.Cu | Filled zones that shrink/grow to simulate opening |

### Visual Encoding Strategy

Since PCBs have limited "color", we use multiple encoding methods:

**Depth/Distance (using layers):**
- F.Cu (red in editor) = Close objects (0-200 units)
- B.Cu (cyan in editor) = Far objects (200+ units) or floor

**Brightness (using track width):**
- Thick traces (0.3-0.5mm) = Bright/near
- Thin traces (0.1-0.2mm) = Dim/far

**Entity type (using footprint packages):**
- Player: QFP-64 (large, distinctive)
- Imp: SOT-23 (small demon)
- Baron of Hell: TO-220 (large demon)
- Cacodemon: DIP-8 (round-ish)

---

## Implementation Phases

### Phase 0: Environment Setup and Benchmarking (Critical First Step)

**Why this comes first:** We need to validate our performance assumptions before investing in a full implementation.

**Deliverables:**
1. Empty KiCad project configured for optimal performance
2. Benchmark script that measures actual `Refresh()` time
3. Performance baseline data

**Steps:**

```python
# File: benchmark_kicad_refresh.py
import pcbnew
import time

def benchmark_trace_creation_and_refresh():
    """
    Creates N traces, modifies them, and measures refresh time.
    This tells us if our 20 FPS target is realistic.
    """
    board = pcbnew.GetBoard()
    
    # Test with 200 traces (typical DOOM frame)
    traces = []
    for i in range(200):
        track = pcbnew.PCB_TRACK(board)
        track.SetStart(pcbnew.VECTOR2I(i * 100000, 0))
        track.SetEnd(pcbnew.VECTOR2I(i * 100000, 10000000))
        track.SetWidth(100000)
        track.SetLayer(pcbnew.F_Cu)
        board.Add(track)
        traces.append(track)
    
    # Benchmark: modify and refresh 100 times
    refresh_times = []
    for frame in range(100):
        start = time.time()
        
        # Modify traces (simulate animation)
        for i, track in enumerate(traces):
            offset = (frame * 10000) % 1000000
            track.SetStart(pcbnew.VECTOR2I(i * 100000 + offset, 0))
        
        pcbnew.Refresh()
        refresh_times.append(time.time() - start)
    
    avg_time = sum(refresh_times) / len(refresh_times)
    fps = 1.0 / avg_time if avg_time > 0 else 0
    
    print(f"Average frame time: {avg_time*1000:.2f}ms")
    print(f"Estimated FPS: {fps:.1f}")
    print(f"Min frame time: {min(refresh_times)*1000:.2f}ms")
    print(f"Max frame time: {max(refresh_times)*1000:.2f}ms")
    
    return avg_time

# Run benchmark
benchmark_trace_creation_and_refresh()
```

**Success criteria:**
- Average frame time < 50ms (20 FPS)
- If > 100ms (10 FPS): proceed with lower expectations
- If > 200ms (5 FPS): reconsider entire approach

**Manual setup before running benchmark:**
1. Create new KiCad project
2. Open PCBnew
3. Tools → External Plugins → Open Plugin Directory
4. Place benchmark script there
5. Set board size to 200mm × 200mm (large working area)
6. Preferences → PCB Editor → Display Options:
   - Uncheck "Show grid"
   - Uncheck "Clearance outlines"
   - Set "Pad/Via holes" to "Do not show"
7. Preferences → Common → Graphics:
   - Antialiasing: "Fast" or "Disabled"
8. View → Ratsnest: Uncheck (disable airwires)

---

### Phase 1: Minimal DOOM Engine Integration

**Goal:** Get DOOM's rendering loop calling our PCB rendering functions.

**DOOM Source Port Selection:**

We'll use **doomgeneric** because:
- Designed specifically for porting to new platforms
- Minimal dependencies
- Clear separation between game logic and rendering
- Only need to implement 5 functions

**Alternative considered:** chocolate-doom (rejected: too complex, more dependencies)

**Files to modify/create:**

```
doomgeneric/
├── doomgeneric_kicad.c        # Our platform implementation
├── doomgeneric_kicad.h        # Header
└── Makefile.kicad             # Build configuration
```

**The 5 required functions:**

```c
// doomgeneric_kicad.c

#include "doomgeneric.h"

// 1. Initialize display (called once at startup)
void DG_Init() {
    // Set up connection to KiCad Python bridge
    // We'll use a socket/pipe to communicate with Python
}

// 2. Draw frame (called 35 times per second by DOOM)
void DG_DrawFrame() {
    // Send frame buffer to Python via socket
    // Python will convert to PCB traces
    // This is the hot path - must be fast
}

// 3. Sleep for given milliseconds
void DG_SleepMs(uint32_t ms) {
    usleep(ms * 1000);
}

// 4. Get elapsed time in milliseconds
uint32_t DG_GetTicksMs() {
    struct timeval tp;
    gettimeofday(&tp, NULL);
    return (tp.tv_sec * 1000) + (tp.tv_usec / 1000);
}

// 5. Get key state (keyboard input)
int DG_GetKey(int* pressed, unsigned char* key) {
    // Read from Python via socket
    // Python will capture keyboard using pynput
}
```

**Why this architecture:**
- DOOM engine runs as separate C process (fast)
- Python plugin runs in KiCad (has access to PCB API)
- Communication via Unix socket or named pipe (fast IPC)
- Python receives frame data, converts to PCB traces

**Alternative architecture considered:** Compile DOOM as Python C extension
- **Rejected because:** DOOM has many dependencies, harder to build, Python GIL issues

---

### Phase 2: Python PCB Renderer

**Goal:** Receive vector data from DOOM, render as PCB traces.

**File structure:**

```
kicad_doom_plugin/
├── __init__.py                 # Plugin registration
├── doom_plugin_action.py       # Main plugin class
├── pcb_renderer.py             # PCB trace rendering
├── doom_bridge.py              # Communication with C DOOM process
├── object_pool.py              # Pre-allocated PCB object management
└── config.py                   # Configuration constants
```

**Key class: PCB Renderer**

```python
# File: pcb_renderer.py

import pcbnew

class DoomPCBRenderer:
    """
    Manages PCB traces representing DOOM's rendered frame.
    
    Performance critical: This is called 20-35 times per second.
    """
    
    def __init__(self, board):
        self.board = board
        self.scale = 50000  # Convert DOOM units to nanometers (0.05mm per unit)
        
        # Pre-allocate object pools (critical for performance)
        self.wall_trace_pool = TracePool(board, max_size=500)
        self.footprint_pool = FootprintPool(board, max_size=20)
        self.via_pool = ViaPool(board, max_size=50)
        
        # Single shared net (eliminates ratsnest calculation)
        self.doom_net = self._create_doom_net()
        
        # Statistics
        self.frame_count = 0
        self.total_render_time = 0.0
    
    def _create_doom_net(self):
        """Create a single net for all DOOM geometry."""
        net = pcbnew.NETINFO_ITEM(self.board, "DOOM_WORLD")
        self.board.Add(net)
        return net
    
    def render_frame(self, frame_data):
        """
        Render a complete DOOM frame to PCB.
        
        Args:
            frame_data: Dictionary containing:
                - walls: List of wall segments [(x1, y1, x2, y2, distance), ...]
                - entities: List of entities [(x, y, type, angle), ...]
                - projectiles: List of projectiles [(x, y), ...]
                - hud: HUD text elements
        """
        import time
        start = time.time()
        
        # 1. Render walls (most objects, most critical for performance)
        self._render_walls(frame_data['walls'])
        
        # 2. Render entities (player, enemies)
        self._render_entities(frame_data['entities'])
        
        # 3. Render projectiles
        self._render_projectiles(frame_data['projectiles'])
        
        # 4. Render HUD
        self._render_hud(frame_data['hud'])
        
        # 5. Refresh display (this is the slow part)
        pcbnew.Refresh()
        
        # Statistics
        elapsed = time.time() - start
        self.total_render_time += elapsed
        self.frame_count += 1
        
        if self.frame_count % 100 == 0:
            avg_fps = self.frame_count / self.total_render_time
            print(f"Frame {self.frame_count}: {elapsed*1000:.2f}ms, Avg FPS: {avg_fps:.1f}")
    
    def _render_walls(self, walls):
        """Render wall segments as PCB traces."""
        trace_index = 0
        
        for wall in walls:
            x1, y1, x2, y2, distance = wall
            
            # Get trace from pool (reuse, don't allocate)
            trace = self.wall_trace_pool.get(trace_index)
            trace_index += 1
            
            # Convert coordinates
            start_x = int((x1 - 160) * self.scale)  # Center at origin
            start_y = int((100 - y1) * self.scale)  # Flip Y (PCB Y is inverted)
            end_x = int((x2 - 160) * self.scale)
            end_y = int((100 - y2) * self.scale)
            
            # Update trace position
            trace.SetStart(pcbnew.VECTOR2I(start_x, start_y))
            trace.SetEnd(pcbnew.VECTOR2I(end_x, end_y))
            
            # Encode distance as layer and width
            if distance < 100:
                trace.SetLayer(pcbnew.F_Cu)  # Close = front copper (red)
                trace.SetWidth(300000)  # 0.3mm (thick = bright)
            else:
                trace.SetLayer(pcbnew.B_Cu)  # Far = back copper (cyan)
                trace.SetWidth(150000)  # 0.15mm (thin = dim)
            
            # Set net (required for electrical authenticity)
            trace.SetNet(self.doom_net)
        
        # Hide unused traces
        self.wall_trace_pool.hide_unused(trace_index)
    
    def _render_entities(self, entities):
        """Render player and enemies as footprints."""
        footprint_index = 0
        
        for entity in entities:
            x, y, entity_type, angle = entity
            
            # Get footprint from pool
            footprint = self.footprint_pool.get(footprint_index, entity_type)
            footprint_index += 1
            
            # Convert coordinates
            pos_x = int((x - 160) * self.scale)
            pos_y = int((100 - y) * self.scale)
            
            # Update position and rotation
            footprint.SetPosition(pcbnew.VECTOR2I(pos_x, pos_y))
            footprint.SetOrientation(pcbnew.EDA_ANGLE(angle, pcbnew.DEGREES_T))
            
            # Make visible
            footprint.SetLayerSet(pcbnew.LSET(pcbnew.F_Cu))
        
        # Hide unused footprints
        self.footprint_pool.hide_unused(footprint_index)
    
    def _render_projectiles(self, projectiles):
        """Render bullets/projectiles as vias."""
        via_index = 0
        
        for projectile in projectiles:
            x, y = projectile
            
            # Get via from pool
            via = self.via_pool.get(via_index)
            via_index += 1
            
            # Convert coordinates
            pos_x = int((x - 160) * self.scale)
            pos_y = int((100 - y) * self.scale)
            
            # Update position
            via.SetPosition(pcbnew.VECTOR2I(pos_x, pos_y))
            via.SetDrill(400000)  # 0.4mm drill
            via.SetWidth(600000)  # 0.6mm pad
            via.SetNet(self.doom_net)
        
        # Hide unused vias
        self.via_pool.hide_unused(via_index)
    
    def _render_hud(self, hud_elements):
        """Render HUD text on silkscreen."""
        # HUD is static-ish (health, ammo, face)
        # Can update less frequently (every 5 frames)
        if self.frame_count % 5 != 0:
            return
        
        # Update health text, ammo text, etc.
        # Using PCB_TEXT on F.SilkS layer
        pass  # Implementation details...
```

**Object Pool Implementation (Critical for Performance):**

```python
# File: object_pool.py

import pcbnew

class TracePool:
    """
    Pre-allocated pool of PCB_TRACK objects.
    
    Why: Creating/destroying objects every frame is slow due to:
    - Python/C++ allocation overhead
    - Board object tree modification
    - Memory fragmentation
    
    Solution: Create objects once, reuse by updating positions.
    """
    
    def __init__(self, board, max_size):
        self.board = board
        self.traces = []
        
        # Pre-allocate all traces
        for i in range(max_size):
            track = pcbnew.PCB_TRACK(board)
            track.SetWidth(200000)  # Default 0.2mm
            track.SetLayer(pcbnew.F_Cu)
            board.Add(track)
            self.traces.append(track)
    
    def get(self, index):
        """Get trace at index (reuse existing object)."""
        if index >= len(self.traces):
            raise IndexError(f"Trace pool exhausted: {index} >= {len(self.traces)}")
        return self.traces[index]
    
    def hide_unused(self, used_count):
        """Hide traces not used this frame (set width to 0)."""
        for i in range(used_count, len(self.traces)):
            self.traces[i].SetWidth(0)  # Invisible

class FootprintPool:
    """Pre-allocated pool of footprints for entities."""
    
    ENTITY_FOOTPRINTS = {
        'player': 'Package_QFP:QFP-64_10x10mm_P0.5mm',
        'imp': 'Package_TO_SOT_SMD:SOT-23',
        'baron': 'Package_TO_THT:TO-220-3_Vertical',
        'cacodemon': 'Package_DIP:DIP-8_W7.62mm',
    }
    
    def __init__(self, board, max_size):
        self.board = board
        self.footprints = {}
        
        # Pre-load footprints for each entity type
        for entity_type, footprint_name in self.ENTITY_FOOTPRINTS.items():
            self.footprints[entity_type] = []
            
            lib_path, fp_name = footprint_name.rsplit(':', 1)
            lib_full_path = f"/usr/share/kicad/footprints/{lib_path}.pretty"
            
            # Pre-allocate multiple instances of each type
            for i in range(max_size // len(self.ENTITY_FOOTPRINTS)):
                fp = pcbnew.FootprintLoad(lib_full_path, fp_name)
                if fp:
                    fp.SetReference(f"{entity_type.upper()}{i}")
                    board.Add(fp)
                    self.footprints[entity_type].append(fp)
    
    def get(self, index, entity_type):
        """Get footprint for entity type at index."""
        if entity_type not in self.footprints:
            entity_type = 'imp'  # Fallback
        
        pool = self.footprints[entity_type]
        if index >= len(pool):
            return pool[0]  # Reuse first one if pool exhausted
        return pool[index]
    
    def hide_unused(self, used_count):
        """Move unused footprints off-screen."""
        # Set position to (-1000, -1000) mm (way off board)
        off_screen = pcbnew.VECTOR2I(-1000000000, -1000000000)
        for entity_type, pool in self.footprints.items():
            for i in range(used_count, len(pool)):
                pool[i].SetPosition(off_screen)

class ViaPool:
    """Pre-allocated pool of vias for projectiles."""
    
    def __init__(self, board, max_size):
        self.board = board
        self.vias = []
        
        for i in range(max_size):
            via = pcbnew.PCB_VIA(board)
            via.SetDrill(400000)
            via.SetWidth(600000)
            board.Add(via)
            self.vias.append(via)
    
    def get(self, index):
        if index >= len(self.vias):
            return self.vias[0]  # Reuse if exhausted
        return self.vias[index]
    
    def hide_unused(self, used_count):
        """Move unused vias off-screen."""
        off_screen = pcbnew.VECTOR2I(-1000000000, -1000000000)
        for i in range(used_count, len(self.vias)):
            self.vias[i].SetPosition(off_screen)
```

---

### Phase 3: DOOM ↔ Python Bridge

**Goal:** Enable C DOOM process to communicate with Python KiCad plugin.

**Architecture decision:**

We'll use **Unix domain sockets** for IPC because:
- Fast (in-memory, no network overhead)
- Python `socket` module (built-in)
- C `socket.h` (standard)
- Works on macOS and Linux

**Alternative considered:** Named pipes (rejected: more complex error handling)

**Protocol Design:**

```
Message format (binary):
[4 bytes: message type]
[4 bytes: payload length]
[N bytes: payload (JSON)]

Message types:
0x01: FRAME_DATA    (DOOM → Python)
0x02: KEY_EVENT     (Python → DOOM)
0x03: INIT_COMPLETE (Python → DOOM)
0x04: SHUTDOWN      (bidirectional)
```

**Python side (socket server):**

```python
# File: doom_bridge.py

import socket
import json
import threading
import struct

class DoomBridge:
    """
    Communication bridge between DOOM C process and Python KiCad plugin.
    
    Runs socket server in background thread to avoid blocking KiCad UI.
    """
    
    SOCKET_PATH = "/tmp/kicad_doom.sock"
    
    MSG_FRAME_DATA = 0x01
    MSG_KEY_EVENT = 0x02
    MSG_INIT_COMPLETE = 0x03
    MSG_SHUTDOWN = 0x04
    
    def __init__(self, renderer):
        self.renderer = renderer
        self.socket = None
        self.connection = None
        self.running = False
        self.thread = None
    
    def start(self):
        """Start socket server in background thread."""
        # Remove old socket file if exists
        try:
            os.unlink(self.SOCKET_PATH)
        except FileNotFoundError:
            pass
        
        # Create Unix socket
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.bind(self.SOCKET_PATH)
        self.socket.listen(1)
        
        print(f"Waiting for DOOM to connect on {self.SOCKET_PATH}...")
        
        # Accept connection (blocking)
        self.connection, _ = self.socket.accept()
        print("DOOM connected!")
        
        # Send init complete
        self._send_message(self.MSG_INIT_COMPLETE, {})
        
        # Start receive loop in thread
        self.running = True
        self.thread = threading.Thread(target=self._receive_loop)
        self.thread.daemon = True
        self.thread.start()
    
    def _receive_loop(self):
        """Receive messages from DOOM (runs in background thread)."""
        while self.running:
            try:
                # Read message header (8 bytes)
                header = self._recv_exactly(8)
                if not header:
                    break
                
                msg_type, payload_len = struct.unpack('II', header)
                
                # Read payload
                payload = self._recv_exactly(payload_len)
                if not payload:
                    break
                
                # Parse JSON
                data = json.loads(payload.decode('utf-8'))
                
                # Handle message
                if msg_type == self.MSG_FRAME_DATA:
                    # Render frame (this is the hot path)
                    self.renderer.render_frame(data)
                
                elif msg_type == self.MSG_SHUTDOWN:
                    print("DOOM requested shutdown")
                    self.running = False
                    break
            
            except Exception as e:
                print(f"Error in receive loop: {e}")
                break
        
        self.stop()
    
    def _recv_exactly(self, n):
        """Receive exactly n bytes (or None if connection closed)."""
        data = b''
        while len(data) < n:
            chunk = self.connection.recv(n - len(data))
            if not chunk:
                return None
            data += chunk
        return data
    
    def _send_message(self, msg_type, data):
        """Send message to DOOM."""
        payload = json.dumps(data).encode('utf-8')
        header = struct.pack('II', msg_type, len(payload))
        self.connection.sendall(header + payload)
    
    def send_key_event(self, pressed, key_code):
        """Send keyboard event to DOOM."""
        self._send_message(self.MSG_KEY_EVENT, {
            'pressed': pressed,
            'key': key_code
        })
    
    def stop(self):
        """Cleanup and close socket."""
        self.running = False
        if self.connection:
            self.connection.close()
        if self.socket:
            self.socket.close()
        try:
            os.unlink(self.SOCKET_PATH)
        except:
            pass
```

**C side (socket client):**

```c
// File: doom_socket.c

#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#include <stdint.h>
#include <string.h>
#include <stdio.h>

#define SOCKET_PATH "/tmp/kicad_doom.sock"
#define MSG_FRAME_DATA 0x01
#define MSG_KEY_EVENT 0x02
#define MSG_INIT_COMPLETE 0x03
#define MSG_SHUTDOWN 0x04

static int sock_fd = -1;

int doom_socket_connect() {
    struct sockaddr_un addr;
    
    sock_fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (sock_fd < 0) {
        perror("socket");
        return -1;
    }
    
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    strncpy(addr.sun_path, SOCKET_PATH, sizeof(addr.sun_path) - 1);
    
    if (connect(sock_fd, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
        perror("connect");
        return -1;
    }
    
    // Wait for init complete
    uint32_t msg_type, payload_len;
    if (read(sock_fd, &msg_type, 4) != 4 || 
        read(sock_fd, &payload_len, 4) != 4) {
        return -1;
    }
    
    if (msg_type != MSG_INIT_COMPLETE) {
        fprintf(stderr, "Expected INIT_COMPLETE, got %d\n", msg_type);
        return -1;
    }
    
    // Discard init payload
    char buf[payload_len];
    read(sock_fd, buf, payload_len);
    
    printf("Connected to KiCad!\n");
    return 0;
}

int doom_socket_send_frame(const char* json_data, size_t len) {
    uint32_t header[2] = {MSG_FRAME_DATA, (uint32_t)len};
    
    if (write(sock_fd, header, 8) != 8) {
        return -1;
    }
    
    if (write(sock_fd, json_data, len) != (ssize_t)len) {
        return -1;
    }
    
    return 0;
}

int doom_socket_recv_key(int* pressed, unsigned char* key) {
    // Non-blocking read (we'll use select with timeout)
    fd_set readfds;
    struct timeval tv = {0, 0};  // No wait
    
    FD_ZERO(&readfds);
    FD_SET(sock_fd, &readfds);
    
    int ret = select(sock_fd + 1, &readfds, NULL, NULL, &tv);
    if (ret <= 0) {
        return 0;  // No data available
    }
    
    // Read message
    uint32_t msg_type, payload_len;
    if (read(sock_fd, &msg_type, 4) != 4 || 
        read(sock_fd, &payload_len, 4) != 4) {
        return -1;
    }
    
    if (msg_type != MSG_KEY_EVENT) {
        // Skip unknown message
        char buf[payload_len];
        read(sock_fd, buf, payload_len);
        return 0;
    }
    
    // Parse JSON (simplified - in reality use a JSON library)
    char json[payload_len + 1];
    read(sock_fd, json, payload_len);
    json[payload_len] = '\0';
    
    // Parse: {"pressed": true, "key": 119}
    // (In real implementation, use cJSON or similar)
    
    return 1;  // Key event received
}

void doom_socket_close() {
    if (sock_fd >= 0) {
        uint32_t header[2] = {MSG_SHUTDOWN, 0};
        write(sock_fd, header, 8);
        close(sock_fd);
        sock_fd = -1;
    }
}
```

---

### Phase 4: Input Handling

**Challenge:** KiCad's Python plugin runs in a blocking context - we can't hook into the event loop to capture keyboard input during gameplay.

**Solution:** Use OS-level keyboard capture with `pynput` library.

```python
# File: input_handler.py

from pynput import keyboard

class DoomInputHandler:
    """
    Captures keyboard input at OS level and forwards to DOOM.
    
    Why pynput: Works outside of KiCad's event loop, captures global keyboard.
    """
    
    # DOOM key mappings
    KEY_MAP = {
        'w': 0x77,  # Forward
        's': 0x73,  # Backward
        'a': 0x61,  # Strafe left
        'd': 0x64,  # Strafe right
        keyboard.Key.left: 0xAC,   # Turn left
        keyboard.Key.right: 0xAE,  # Turn right
        keyboard.Key.ctrl: 0x9D,   # Fire
        keyboard.Key.space: 0x39,  # Use
        'e': 0x45,  # Use (alternate)
    }
    
    def __init__(self, bridge):
        self.bridge = bridge
        self.listener = None
        self.pressed_keys = set()
    
    def start(self):
        """Start keyboard listener in background."""
        self.listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release
        )
        self.listener.start()
        print("Input handler started (use WASD + arrows + Ctrl to play)")
    
    def _on_key_press(self, key):
        """Called when key is pressed."""
        try:
            # Get character or special key
            if hasattr(key, 'char'):
                key_char = key.char
            else:
                key_char = key
            
            # Check if mapped
            if key_char in self.KEY_MAP:
                doom_key = self.KEY_MAP[key_char]
                
                # Only send if not already pressed (avoid repeats)
                if doom_key not in self.pressed_keys:
                    self.pressed_keys.add(doom_key)
                    self.bridge.send_key_event(pressed=True, key_code=doom_key)
        
        except Exception as e:
            print(f"Key press error: {e}")
    
    def _on_key_release(self, key):
        """Called when key is released."""
        try:
            if hasattr(key, 'char'):
                key_char = key.char
            else:
                key_char = key
            
            if key_char in self.KEY_MAP:
                doom_key = self.KEY_MAP[key_char]
                
                if doom_key in self.pressed_keys:
                    self.pressed_keys.remove(doom_key)
                    self.bridge.send_key_event(pressed=False, key_code=doom_key)
        
        except Exception as e:
            print(f"Key release error: {e}")
    
    def stop(self):
        """Stop keyboard listener."""
        if self.listener:
            self.listener.stop()
```

**Important:** `pynput` captures keyboard globally (system-wide). This means:
- ⚠️ Will capture keys even when other apps are focused
- ⚠️ Might conflict with KiCad's shortcuts
- ✅ Works around KiCad's event loop limitations

**Mitigation:** Only start input handler when DOOM is actively running, stop it when done.

---

### Phase 5: Main Plugin Integration

**Goal:** Tie everything together into a KiCad action plugin.

```python
# File: doom_plugin_action.py

import pcbnew
import os
import subprocess
import time

class DoomKiCadPlugin(pcbnew.ActionPlugin):
    """
    KiCad action plugin to run DOOM on PCB traces.
    
    Usage:
    1. Open a PCB in KiCad
    2. Tools → External Plugins → DOOM on PCB
    3. Wait for DOOM to start
    4. Play using WASD + arrows + Ctrl
    5. Press ESC to quit
    """
    
    def defaults(self):
        self.name = "DOOM on PCB"
        self.category = "Demo"
        self.description = "Run DOOM using PCB traces as the display"
        self.show_toolbar_button = True
        self.icon_file_name = os.path.join(os.path.dirname(__file__), 'doom_icon.png')
    
    def Run(self):
        """Main entry point when plugin is activated."""
        board = pcbnew.GetBoard()
        
        # Validate board
        if not board:
            wx.MessageBox("No board loaded!", "Error", wx.OK | wx.ICON_ERROR)
            return
        
        print("=" * 60)
        print("DOOM on PCB - Starting...")
        print("=" * 60)
        
        # Configure board for performance
        self._configure_board_for_performance(board)
        
        # Create renderer
        from .pcb_renderer import DoomPCBRenderer
        renderer = DoomPCBRenderer(board)
        
        # Create bridge (socket server)
        from .doom_bridge import DoomBridge
        bridge = DoomBridge(renderer)
        
        # Start input handler
        from .input_handler import DoomInputHandler
        input_handler = DoomInputHandler(bridge)
        
        try:
            # Start socket server (waits for DOOM to connect)
            bridge.start()
            
            # Launch DOOM process
            doom_binary = os.path.join(os.path.dirname(__file__), 'doomgeneric_kicad')
            if not os.path.exists(doom_binary):
                print(f"ERROR: DOOM binary not found at {doom_binary}")
                print("You need to compile doomgeneric first!")
                return
            
            print(f"Launching DOOM: {doom_binary}")
            doom_process = subprocess.Popen([doom_binary])
            
            # Start input capture
            input_handler.start()
            
            print("\n" + "=" * 60)
            print("DOOM is running!")
            print("Controls: WASD = move, Arrows = turn, Ctrl = shoot")
            print("Press ESC in DOOM to quit")
            print("=" * 60 + "\n")
            
            # Wait for DOOM to exit
            doom_process.wait()
            
            print("\nDOOM exited")
        
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            # Cleanup
            input_handler.stop()
            bridge.stop()
            
            print("\n" + "=" * 60)
            print("Statistics:")
            print(f"  Total frames: {renderer.frame_count}")
            if renderer.frame_count > 0:
                avg_fps = renderer.frame_count / renderer.total_render_time
                print(f"  Average FPS: {avg_fps:.1f}")
                print(f"  Total runtime: {renderer.total_render_time:.1f}s")
            print("=" * 60)
    
    def _configure_board_for_performance(self, board):
        """Apply all performance optimizations to board."""
        print("Configuring board for optimal performance...")
        
        # 1. Set to 2-layer board
        settings = board.GetDesignSettings()
        settings.SetCopperLayerCount(2)
        board.SetDesignSettings(settings)
        
        # 2. Only enable F.Cu and B.Cu layers
        layer_set = pcbnew.LSET()
        layer_set.addLayer(pcbnew.F_Cu)
        layer_set.addLayer(pcbnew.B_Cu)
        layer_set.addLayer(pcbnew.Edge_Cuts)  # Keep board outline
        board.SetEnabledLayers(layer_set)
        board.SetVisibleLayers(layer_set)
        
        # 3. Clear any existing highlighting
        board.SetHighLightNet(-1)
        
        # 4. Warn user about manual settings
        print("\nIMPORTANT: For best performance, manually configure:")
        print("  1. View → Show Grid (uncheck)")
        print("  2. View → Ratsnest (uncheck)")
        print("  3. Preferences → Graphics → Antialiasing: Fast or Disabled")
        print("  4. Preferences → Display Options → Clearance: off\n")
        
        print("Board configuration complete")

# Register plugin
DoomKiCadPlugin().register()
```

---

## Known Pitfalls and Solutions

### Pitfall 1: Refresh() Blocks Python Execution

**Problem:** `pcbnew.Refresh()` is synchronous and blocks until the frame is rendered. If it takes 50ms, your entire Python script freezes for 50ms.

**Impact:** Can't process input or update game state while rendering.

**Solution:** This is actually okay for our use case:
- DOOM runs in separate C process (doesn't block)
- Input capture uses separate thread (doesn't block)
- Only the PCB update blocks, which is expected

**Mitigation:** If frame time exceeds budget (>50ms), consider:
- Reducing object count
- Skipping frames (render every 2nd or 3rd frame)
- Using lower resolution (fewer wall segments)

---

### Pitfall 2: Python/C++ Object Lifetime

**Problem:** PCB objects created in Python are managed by both Python's garbage collector AND KiCad's C++ memory management.

**Symptom:** Crashes, segfaults, or "use after free" errors.

**Example of bad code:**

```python
def render_frame_BAD():
    # Create trace
    track = pcbnew.PCB_TRACK(board)
    board.Add(track)
    # track goes out of scope here
    # Python might GC it, but KiCad still has a pointer!
```

**Solution:** Keep references to all created objects:

```python
class Renderer:
    def __init__(self):
        self.all_objects = []  # Keep alive
    
    def create_trace(self):
        track = pcbnew.PCB_TRACK(board)
        board.Add(track)
        self.all_objects.append(track)  # Prevent GC
        return track
```

**Better solution:** Use object pools (already in our design).

---

### Pitfall 3: KiCad API Version Differences

**Problem:** KiCad's Python API changes between versions (KiCad 5, 6, 7, 8).

**Symptoms:**
- `AttributeError: module 'pcbnew' has no attribute 'VECTOR2I'` (KiCad 5 uses `wxPoint`)
- Different layer constants
- Different units (KiCad 5: decimils, KiCad 6+: nanometers)

**Solution:** Add version detection and compatibility layer:

```python
# File: kicad_compat.py

import pcbnew

KICAD_VERSION = pcbnew.Version()

def create_point(x, y):
    """Create a point in KiCad coordinate system."""
    if KICAD_VERSION.startswith('5'):
        return pcbnew.wxPoint(x, y)
    else:
        return pcbnew.VECTOR2I(x, y)

def create_angle(degrees):
    """Create an angle."""
    if KICAD_VERSION.startswith('5'):
        return degrees * 10  # Decidegrees
    else:
        return pcbnew.EDA_ANGLE(degrees, pcbnew.DEGREES_T)

# Use in code:
track.SetStart(create_point(x, y))
footprint.SetOrientation(create_angle(45))
```

**Recommendation:** Target KiCad 7 or 8 (latest stable). Don't worry about KiCad 5 compatibility unless necessary.

---

### Pitfall 4: Coordinate System Confusion

**Problem:** Multiple coordinate systems in play:
- DOOM: (0,0) at top-left, Y increases downward, units are pixels (320×200)
- KiCad: (0,0) at arbitrary origin, Y increases upward, units are nanometers
- PCB: Usually centered, dimensions in millimeters

**Solution:** Clear coordinate transformation:

```python
class CoordinateTransform:
    """Handles all coordinate system conversions."""
    
    # DOOM screen dimensions
    DOOM_WIDTH = 320
    DOOM_HEIGHT = 200
    
    # Scale factor: DOOM units → mm → nm
    DOOM_TO_MM = 0.5  # 0.5mm per DOOM pixel
    MM_TO_NM = 1000000  # nanometers per mm
    SCALE = DOOM_TO_MM * MM_TO_NM  # 500,000 nm per DOOM pixel
    
    @staticmethod
    def doom_to_kicad(doom_x, doom_y):
        """
        Convert DOOM screen coordinates to KiCad board coordinates.
        
        DOOM: (0,0) = top-left, (320, 200) = bottom-right
        KiCad: (0,0) = board center, Y increases upward
        """
        # Center the DOOM screen on KiCad origin
        x_centered = doom_x - (CoordinateTransform.DOOM_WIDTH / 2)
        y_centered = doom_y - (CoordinateTransform.DOOM_HEIGHT / 2)
        
        # Flip Y axis (DOOM Y down, KiCad Y up)
        y_flipped = -y_centered
        
        # Scale to nanometers
        kicad_x = int(x_centered * CoordinateTransform.SCALE)
        kicad_y = int(y_flipped * CoordinateTransform.SCALE)
        
        return kicad_x, kicad_y
    
    @staticmethod
    def get_board_bounds():
        """
        Get the bounding box for DOOM screen in KiCad coordinates.
        Useful for setting board edge cuts.
        """
        # DOOM screen corners
        corners = [
            (0, 0),
            (CoordinateTransform.DOOM_WIDTH, 0),
            (CoordinateTransform.DOOM_WIDTH, CoordinateTransform.DOOM_HEIGHT),
            (0, CoordinateTransform.DOOM_HEIGHT)
        ]
        
        return [CoordinateTransform.doom_to_kicad(x, y) for x, y in corners]
```

**Use in renderer:**

```python
def _render_walls(self, walls):
    for wall in walls:
        doom_x1, doom_y1, doom_x2, doom_y2, distance = wall
        
        # Convert coordinates
        kicad_x1, kicad_y1 = CoordinateTransform.doom_to_kicad(doom_x1, doom_y1)
        kicad_x2, kicad_y2 = CoordinateTransform.doom_to_kicad(doom_x2, doom_y2)
        
        # Create trace
        trace.SetStart(pcbnew.VECTOR2I(kicad_x1, kicad_y1))
        trace.SetEnd(pcbnew.VECTOR2I(kicad_x2, kicad_y2))
```

---

### Pitfall 5: Socket Communication Reliability

**Problem:** Sockets can fail, timeout, or get out of sync.

**Scenarios:**
1. DOOM crashes → socket left open
2. Network buffer full → deadlock
3. Partial messages received → parsing errors

**Solution:** Robust error handling and timeouts:

```python
class DoomBridge:
    SOCKET_TIMEOUT = 5.0  # seconds
    
    def start(self):
        self.socket.settimeout(self.SOCKET_TIMEOUT)
        try:
            self.connection, _ = self.socket.accept()
        except socket.timeout:
            print("ERROR: DOOM didn't connect within timeout")
            raise
    
    def _receive_loop(self):
        while self.running:
            try:
                # Set timeout on receive
                self.connection.settimeout(1.0)
                header = self._recv_exactly(8)
                
                if not header:
                    print("Connection closed by DOOM")
                    break
                
                # ... process message ...
            
            except socket.timeout:
                # No data for 1 second, continue waiting
                continue
            
            except Exception as e:
                print(f"Socket error: {e}")
                break
        
        self.stop()
```

**Testing:** Always test with intentional crashes:
- Kill DOOM process mid-game
- Disconnect socket manually
- Send malformed data

---

### Pitfall 6: Performance Degradation Over Time

**Problem:** Frame time increases as game runs longer.

**Causes:**
1. Memory leaks (Python objects not freed)
2. Board object tree grows unbounded
3. GPU memory fragmentation

**Solution:** Periodic cleanup and monitoring:

```python
class DoomPCBRenderer:
    CLEANUP_INTERVAL = 500  # frames
    
    def render_frame(self, frame_data):
        # ... normal rendering ...
        
        # Periodic cleanup
        if self.frame_count % self.CLEANUP_INTERVAL == 0:
            self._cleanup()
    
    def _cleanup(self):
        """Periodic maintenance to prevent degradation."""
        import gc
        
        # Force Python garbage collection
        gc.collect()
        
        # Log memory usage
        import psutil
        process = psutil.Process(os.getpid())
        mem_mb = process.memory_info().rss / 1024 / 1024
        print(f"Memory usage: {mem_mb:.1f} MB")
        
        # Check for runaway object count
        track_count = len(list(self.board.GetTracks()))
        if track_count > 1000:
            print(f"WARNING: {track_count} tracks on board (expected < 1000)")
```

**Monitoring:** Track frame times and alert if they exceed threshold:

```python
if elapsed > 0.100:  # 100ms = 10 FPS
    print(f"WARNING: Slow frame: {elapsed*1000:.2f}ms")
```

---

### Pitfall 7: Footprint Library Loading

**Problem:** Loading footprints is slow (~10-50ms per footprint).

**Bad approach:**

```python
def render_entity(entity_type):
    # Loading footprint every frame - VERY SLOW
    fp = pcbnew.FootprintLoad(lib_path, footprint_name)
    board.Add(fp)
```

**Good approach:** Pre-load all footprints at initialization (already in our FootprintPool).

**Additional pitfall:** Footprint paths differ by OS:
- Linux: `/usr/share/kicad/footprints/`
- macOS: `/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/`
- Windows: `C:\Program Files\KiCad\share\kicad\footprints\`

**Solution:** Use KiCad's environment variables:

```python
def get_footprint_library_path():
    """Get footprint library path for current OS."""
    # KiCad provides KISYSMOD environment variable
    import os
    kisysmod = os.getenv('KISYSMOD')
    if kisysmod:
        return kisysmod
    
    # Fallback: detect by OS
    import platform
    system = platform.system()
    
    if system == 'Linux':
        return '/usr/share/kicad/footprints'
    elif system == 'Darwin':  # macOS
        return '/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints'
    elif system == 'Windows':
        return r'C:\Program Files\KiCad\share\kicad\footprints'
    
    raise RuntimeError("Could not find KiCad footprint library")
```

---

### Pitfall 8: DOOM WAD File Handling

**Problem:** DOOM needs a WAD file (game data). Where to put it?

**Options:**
1. Bundle doom1.wad (shareware) with plugin
2. Ask user to provide their own WAD
3. Download automatically

**Recommendation:** Bundle shareware WAD (doom1.wad is freely distributable).

**Implementation:**

```
kicad_doom_plugin/
├── doom/
│   ├── doomgeneric_kicad  (compiled binary)
│   └── doom1.wad           (game data)
└── ...
```

**C code:**

```c
// doomgeneric_kicad.c

void DG_Init() {
    // Set WAD path relative to binary
    char wad_path[256];
    snprintf(wad_path, sizeof(wad_path), "%s/doom1.wad", 
             get_executable_dir());
    
    // DOOM will load from this path
    myargv[myargc++] = "-iwad";
    myargv[myargc++] = wad_path;
}
```

---

## Testing and Benchmarking Strategy

### Test 1: Refresh Benchmark (Phase 0)

**Purpose:** Validate core assumption that we can hit 20 FPS.

**Method:** Create 200 static traces, update positions, measure refresh time.

**Success criteria:**
- < 50ms average = 20+ FPS (proceed with confidence)
- 50-100ms = 10-20 FPS (proceed with caution)
- \> 100ms = < 10 FPS (reconsider approach)

**Run this FIRST before implementing anything else.**

---

### Test 2: Object Pool Performance

**Purpose:** Verify that object reuse is faster than create/destroy.

**Method:** Compare two approaches over 100 frames:
- Approach A: Create 200 traces, render, delete all, repeat
- Approach B: Create 200 traces once, update positions, repeat

**Expected result:** Approach B should be 3-5x faster.

```python
def benchmark_object_reuse():
    import time
    
    # Approach A: Create/Destroy
    times_a = []
    for frame in range(100):
        start = time.time()
        
        traces = []
        for i in range(200):
            track = pcbnew.PCB_TRACK(board)
            track.SetStart(pcbnew.VECTOR2I(i * 100000, 0))
            track.SetEnd(pcbnew.VECTOR2I(i * 100000, 10000000))
            track.SetWidth(200000)
            track.SetLayer(pcbnew.F_Cu)
            board.Add(track)
            traces.append(track)
        
        pcbnew.Refresh()
        
        for track in traces:
            board.Remove(track)
        
        times_a.append(time.time() - start)
    
    # Approach B: Reuse
    traces = []
    for i in range(200):
        track = pcbnew.PCB_TRACK(board)
        track.SetWidth(200000)
        track.SetLayer(pcbnew.F_Cu)
        board.Add(track)
        traces.append(track)
    
    times_b = []
    for frame in range(100):
        start = time.time()
        
        for i, track in enumerate(traces):
            offset = (frame * 10000) % 1000000
            track.SetStart(pcbnew.VECTOR2I(i * 100000 + offset, 0))
            track.SetEnd(pcbnew.VECTOR2I(i * 100000 + offset, 10000000))
        
        pcbnew.Refresh()
        
        times_b.append(time.time() - start)
    
    print(f"Approach A (create/destroy): {sum(times_a)/len(times_a)*1000:.2f}ms avg")
    print(f"Approach B (reuse): {sum(times_b)/len(times_b)*1000:.2f}ms avg")
    print(f"Speedup: {sum(times_a)/sum(times_b):.2f}x")
```

---

### Test 3: Socket Communication Latency

**Purpose:** Measure overhead of sending frame data from C to Python.

**Method:** 
1. Send 100 dummy frames (JSON with ~1KB data)
2. Measure round-trip time
3. Ensure < 5ms per frame

**Expected result:** Socket communication should be negligible compared to rendering time.

---

### Test 4: End-to-End Integration

**Purpose:** Run actual DOOM for 60 seconds, collect statistics.

**Metrics to collect:**
- Frame times (min, max, average, p95, p99)
- FPS over time (check for degradation)
- Memory usage over time (check for leaks)
- Socket errors / dropped frames

**Success criteria:**
- Average FPS > 10
- No crashes
- Memory usage stable (< 10% growth over 60s)

---

## Code Structure

### Final Directory Layout

```
kicad_doom_plugin/
├── __init__.py                      # Plugin registration
├── doom_plugin_action.py            # Main plugin entry point
├── pcb_renderer.py                  # PCB rendering logic
├── doom_bridge.py                   # Socket communication
├── input_handler.py                 # Keyboard capture
├── object_pool.py                   # Pre-allocated object pools
├── coordinate_transform.py          # Coordinate system conversions
├── kicad_compat.py                  # KiCad version compatibility
├── config.py                        # Configuration constants
├── doom_icon.png                    # Plugin toolbar icon
├── doom/
│   ├── doomgeneric_kicad            # Compiled DOOM binary
│   ├── doom1.wad                    # DOOM shareware data
│   └── source/
│       ├── doomgeneric_kicad.c      # Platform implementation
│       ├── doom_socket.c            # Socket client code
│       └── Makefile                 # Build configuration
└── tests/
    ├── benchmark_refresh.py         # Phase 0 benchmark
    ├── benchmark_object_pool.py     # Object reuse test
    └── benchmark_socket.py          # Communication latency test
```

---

## API Reference and Gotchas

### Essential KiCad Python API Calls

**Board access:**
```python
board = pcbnew.GetBoard()  # Get current PCB board
```

**Creating traces:**
```python
track = pcbnew.PCB_TRACK(board)
track.SetStart(pcbnew.VECTOR2I(x1, y1))  # Start point (nanometers)
track.SetEnd(pcbnew.VECTOR2I(x2, y2))    # End point (nanometers)
track.SetWidth(200000)                    # Width (200,000 nm = 0.2mm)
track.SetLayer(pcbnew.F_Cu)              # Layer (front copper)
track.SetNet(net)                         # Electrical net
board.Add(track)                          # Add to board
```

**Creating vias:**
```python
via = pcbnew.PCB_VIA(board)
via.SetPosition(pcbnew.VECTOR2I(x, y))
via.SetDrill(400000)      # Drill diameter (0.4mm)
via.SetWidth(600000)      # Pad diameter (0.6mm)
via.SetNet(net)
board.Add(via)
```

**Loading footprints:**
```python
# Path to library (OS-specific)
lib_path = "/usr/share/kicad/footprints/Package_QFP.pretty"
footprint_name = "QFP-64_10x10mm_P0.5mm"

footprint = pcbnew.FootprintLoad(lib_path, footprint_name)
footprint.SetReference("U1")
footprint.SetValue("PLAYER")
footprint.SetPosition(pcbnew.VECTOR2I(x, y))
footprint.SetOrientation(pcbnew.EDA_ANGLE(angle, pcbnew.DEGREES_T))
board.Add(footprint)
```

**Creating nets:**
```python
net = pcbnew.NETINFO_ITEM(board, "NET_NAME")
board.Add(net)
# Use: track.SetNet(net)
```

**Layer management:**
```python
# Common layers
pcbnew.F_Cu      # Front copper (red)
pcbnew.B_Cu      # Back copper (cyan)
pcbnew.In1_Cu    # Inner layer 1 (blue)
pcbnew.In2_Cu    # Inner layer 2 (green)
pcbnew.F_SilkS   # Front silkscreen (white)
pcbnew.Edge_Cuts # Board outline

# Set visible layers
layer_set = pcbnew.LSET()
layer_set.addLayer(pcbnew.F_Cu)
layer_set.addLayer(pcbnew.B_Cu)
board.SetVisibleLayers(layer_set)
board.SetEnabledLayers(layer_set)
```

**Refreshing display:**
```python
pcbnew.Refresh()  # Update PCB display (slow, blocks execution)
```

**Board settings:**
```python
settings = board.GetDesignSettings()
settings.SetCopperLayerCount(2)  # 2-layer board
board.SetDesignSettings(settings)
```

### Common API Gotchas

**1. Units are nanometers, not millimeters**
```python
# WRONG
track.SetWidth(0.2)  # This is 0.2 nanometers (way too small)

# RIGHT
track.SetWidth(200000)  # 200,000 nm = 0.2 mm
```

**2. Y axis is inverted**
```python
# KiCad Y increases upward (math convention)
# DOOM Y increases downward (screen convention)
# Must flip when converting
```

**3. VECTOR2I vs wxPoint (version dependent)**
```python
# KiCad 6+
point = pcbnew.VECTOR2I(x, y)

# KiCad 5
point = pcbnew.wxPoint(x, y)
```

**4. Angles in KiCad 6+ use EDA_ANGLE**
```python
# KiCad 6+
angle = pcbnew.EDA_ANGLE(45, pcbnew.DEGREES_T)
footprint.SetOrientation(angle)

# KiCad 5
footprint.SetOrientation(450)  # Decidegrees (45.0 degrees)
```

**5. Board.Add() doesn't return anything**
```python
track = pcbnew.PCB_TRACK(board)
board.Add(track)
# track is already added, no return value
```

**6. Removing objects requires keeping reference**
```python
# WRONG
board.Add(pcbnew.PCB_TRACK(board))
# Can't remove later - no reference!

# RIGHT
track = pcbnew.PCB_TRACK(board)
board.Add(track)
# Later:
board.Remove(track)
```

**7. Footprints must exist in library**
```python
# Will return None if footprint doesn't exist
fp = pcbnew.FootprintLoad(lib, name)
if not fp:
    print(f"Footprint {name} not found!")
```

**8. Net names must be unique**
```python
# Creating net with existing name returns existing net
net1 = pcbnew.NETINFO_ITEM(board, "VCC")
board.Add(net1)
net2 = pcbnew.NETINFO_ITEM(board, "VCC")  # Same name!
board.Add(net2)
# net1 and net2 point to same net
```

---

## Performance Optimization Checklist

Before running DOOM, verify all optimizations are applied:

### Manual UI Settings (Critical)

- [ ] View → Show Grid: **OFF**
- [ ] View → High Contrast Mode: **OFF**
- [ ] View → Ratsnest: **OFF**
- [ ] Preferences → PCB Editor → Display Options:
  - [ ] Clearance outlines: **OFF**
  - [ ] Pad/Via holes: **Do not show**
  - [ ] Track width indicators: **OFF**
  - [ ] Via size indicators: **OFF**
- [ ] Preferences → Common → Graphics:
  - [ ] Antialiasing: **Fast** or **Disabled**
  - [ ] Rendering engine: **Accelerated**

### Code-Level Optimizations (Automatic)

- [ ] 2-layer board (F.Cu + B.Cu only)
- [ ] Single shared net (no ratsnest calculation)
- [ ] Pre-allocated object pools (no create/destroy in loop)
- [ ] Object reuse (update positions, don't recreate)
- [ ] Minimal layer visibility
- [ ] No DRC during gameplay
- [ ] Hide unused objects (off-screen, not deleted)

### Hardware Considerations

- [ ] Close other applications (free RAM)
- [ ] Disable compositor (Linux: reduces vsync overhead)
- [ ] Run on AC power (not battery)
- [ ] Ensure GPU drivers are up to date

---

## Build Instructions

### Compiling doomgeneric for KiCad

**Prerequisites:**
- GCC or Clang
- Make
- SDL2 (for sound only, optional)

**Steps:**

```bash
# 1. Clone doomgeneric
git clone https://github.com/ozkl/doomgeneric.git
cd doomgeneric/doomgeneric

# 2. Copy our platform files
cp /path/to/plugin/doom/source/doomgeneric_kicad.c .
cp /path/to/plugin/doom/source/doom_socket.c .
cp /path/to/plugin/doom/source/Makefile.kicad .

# 3. Build
make -f Makefile.kicad

# 4. Copy binary to plugin
cp doomgeneric_kicad /path/to/plugin/doom/

# 5. Copy WAD file
cp doom1.wad /path/to/plugin/doom/
```

**Makefile.kicad example:**

```makefile
# Makefile for KiCad platform

DOOM_GENERIC = .
DOOM_SRC = $(DOOM_GENERIC)/../../doom

CC = gcc
CFLAGS += -Wall -I$(DOOM_GENERIC) -I$(DOOM_SRC)
LDFLAGS += -lm

# Add socket code
OBJS += doomgeneric_kicad.o doom_socket.o

# Include doomgeneric common makefile
include $(DOOM_GENERIC)/Makefile.doomgeneric

# Output binary
TARGET = doomgeneric_kicad

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CC) $(CFLAGS) $(OBJS) -o $@ $(LDFLAGS)

clean:
	rm -f $(TARGET) *.o
```

---

## Expected Results

### Performance Targets

**Target FPS by hardware:**
- M1 MacBook Pro: 15-25 FPS
- Dell XPS (i7 12th gen, RTX 3050 Ti): 18-28 FPS
- Older hardware (i5, integrated GPU): 8-15 FPS

**Visual quality:**
- Wireframe rendering (wall outlines only)
- 2 "colors" (red/cyan for depth)
- Text-based HUD
- Smooth enough to play (but not AAA smooth)

### What It Will Look Like

Imagine DOOM rendered as:
- Electrical schematic come to life
- Vector arcade game (Asteroids, Battlezone)
- Oscilloscope display
- CAD wireframe render

**In 2D editor view:**
- Red traces = close walls
- Cyan traces = far walls / floor
- Footprints moving around = enemies
- Small circles (vias) = bullets
- White text = HUD

**In 3D viewer (if recorded):**
- Actual depth separation
- Layered rendering
- More visually impressive

---

## Troubleshooting Guide

### Problem: Plugin doesn't appear in KiCad

**Check:**
1. Plugin files in correct directory (`Tools → External Plugins → Open Plugin Directory`)
2. `__init__.py` imports and registers plugin
3. No Python syntax errors (check KiCad's scripting console)
4. KiCad version supports Python plugins (v6+)

**Debug:**
```python
# Add debug prints to __init__.py
print("Loading DOOM plugin...")
from .doom_plugin_action import DoomKiCadPlugin
print("Registering plugin...")
DoomKiCadPlugin().register()
print("Plugin registered!")
```

---

### Problem: Benchmark shows < 5 FPS

**Possible causes:**
1. Grid still enabled (10-20ms penalty)
2. Antialiasing enabled (5-15ms penalty)
3. Ratsnest enabled (20-40ms penalty)
4. Too many layers visible
5. Integrated GPU (slower than discrete)

**Solutions:**
- Double-check all manual settings
- Reduce object count (test with 100 traces instead of 200)
- Check `htop` for CPU usage (should be high)
- Check GPU usage (should be moderate)

---

### Problem: Socket connection fails

**Symptoms:**
- "Connection refused"
- "No such file or directory"
- Timeout

**Debug:**
```bash
# Check if socket file exists
ls -l /tmp/kicad_doom.sock

# Check if DOOM binary is running
ps aux | grep doomgeneric

# Try connecting manually
nc -U /tmp/kicad_doom.sock
```

**Solutions:**
- Ensure Python starts socket server BEFORE launching DOOM
- Check socket path matches in both Python and C
- Verify socket file permissions
- Try absolute path instead of relative

---

### Problem: Input doesn't work

**Symptoms:**
- Key presses not captured
- Player doesn't move

**Debug:**
```python
# Add prints to input handler
def _on_key_press(self, key):
    print(f"Key pressed: {key}")
    # ... rest of code
```

**Solutions:**
- Ensure `pynput` is installed (`pip install pynput`)
- Check if KiCad window has focus (might need to click on it)
- Try running KiCad from terminal (see debug prints)
- On macOS: Grant accessibility permissions to Terminal/KiCad

---

### Problem: Performance degrades over time

**Symptoms:**
- Starts at 20 FPS, drops to 5 FPS after 1 minute

**Possible causes:**
1. Memory leak (objects not being reused)
2. Board object tree growing unbounded
3. Python GC not running

**Debug:**
```python
# Add memory monitoring
import psutil
process = psutil.Process(os.getpid())
print(f"Frame {frame_num}: {process.memory_info().rss / 1024 / 1024:.1f} MB")
```

**Solutions:**
- Verify object pools are being used (not creating new objects)
- Force GC periodically (`gc.collect()`)
- Check board object count (`len(list(board.GetTracks()))`)
- Reduce max pool sizes if running out of memory

---

### Problem: Crashes / Segfaults

**Symptoms:**
- KiCad crashes
- Python exception: "Segmentation fault"
- "Use after free" error

**Possible causes:**
1. PCB object deleted while still in use
2. Invalid pointer access
3. KiCad API misuse

**Debug:**
- Run KiCad from terminal to see crash logs
- Use Python debugger (`import pdb; pdb.set_trace()`)
- Add try/except around all API calls

**Solutions:**
- Keep references to all created objects
- Never call `board.Remove()` during rendering
- Use object pools (don't create/destroy in loop)

---

## Future Enhancements

### If Basic Version Works

1. **Color via layers**: Use 4 copper layers for better depth encoding
2. **Textured walls**: Use filled zones with hatching patterns
3. **Smooth animation**: Interpolate positions between frames
4. **Sound**: Play audio through system (Python `pygame` or similar)
5. **Multiplayer**: Multiple boards, each player has their own PCB

### If Performance is Good (>25 FPS)

1. **Higher resolution**: 480×300 instead of 320×200
2. **More complex geometry**: Render sprites as filled shapes
3. **3D viewer mode**: Real-time updates in 3D view (if API permits)

### Advanced Features

1. **Gerber export**: Export each frame as fabricatable PCB
2. **DRC report**: Generate hilarious design rule violations
3. **BOM generation**: "1x DOOMGUY, 5x IMP, 1x SHOTGUN"
4. **Schematic view**: Show game state as circuit diagram

---

## Conclusion

This plan provides a complete roadmap for implementing DOOM on KiCad PCB traces. The approach is technically sound, with realistic performance expectations (10-25 FPS) and clear optimization strategies.

**Critical success factors:**
1. Phase 0 benchmark validates assumptions
2. Object reuse eliminates allocation overhead
3. All UI optimizations applied
4. Robust error handling for socket communication

**This is genuinely feasible.** With your hardware (M1 MacBook Pro / Dell XPS i7), you should hit 15-25 FPS, which is playable for a tech demo.

**Next step:** Run the Phase 0 benchmark. If it shows promising results (< 50ms per frame), proceed with full implementation.

Good luck, and may your traces be ever in your favor! 🎮⚡