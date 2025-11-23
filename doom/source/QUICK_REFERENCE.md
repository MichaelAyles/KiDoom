# Quick Reference - KiDoom C Implementation

## File Overview

| File | Purpose | Lines |
|------|---------|-------|
| `doomgeneric_kicad.c` | Platform implementation | ~300 |
| `doom_socket.c` | Socket communication | ~250 |
| `doom_socket.h` | Socket API | ~70 |
| `Makefile.kicad` | Build config | ~80 |

## Build Commands

```bash
# Automated build (recommended)
./build.sh

# Manual build
git clone https://github.com/ozkl/doomgeneric.git
cd doomgeneric/doomgeneric
cp /path/to/source/*.{c,h} .
cp /path/to/source/Makefile.kicad .
make -f Makefile.kicad
```

## Protocol Quick Reference

### Message Types (4 bytes, little-endian)

| Value | Name | Direction | Purpose |
|-------|------|-----------|---------|
| `0x01` | FRAME_DATA | C → Python | Frame vectors |
| `0x02` | KEY_EVENT | Python → C | Keyboard |
| `0x03` | INIT_COMPLETE | Python → C | Handshake |
| `0x04` | SHUTDOWN | Both | Clean exit |

### Message Format

```
Byte Offset: 0        4        8                N
            ┌────────┬────────┬──────────────────┐
            │ type   │ length │ JSON payload     │
            │ uint32 │ uint32 │ char[length]     │
            └────────┴────────┴──────────────────┘
```

### Example Messages

**INIT_COMPLETE (Python → C):**
```
0x03 0x00 0x00 0x00  0x02 0x00 0x00 0x00  '{}'
└─ type=3           └─ len=2           └─ payload
```

**FRAME_DATA (C → Python):**
```
0x01 0x00 0x00 0x00  0x64 0x00 0x00 0x00  '{"walls":[...]}'
└─ type=1           └─ len=100          └─ JSON (100 bytes)
```

**KEY_EVENT (Python → C):**
```
0x02 0x00 0x00 0x00  0x1A 0x00 0x00 0x00  '{"pressed":true,"key":119}'
└─ type=2           └─ len=26           └─ JSON
```

## JSON Format

### Frame Data (C → Python)

```json
{
  "walls": [
    {
      "x1": 10,
      "y1": 50,
      "x2": 100,
      "y2": 50,
      "distance": 80
    }
  ],
  "entities": [
    {
      "x": 160,
      "y": 100,
      "type": "player",
      "angle": 0
    }
  ],
  "frame": 1234
}
```

**Size:** ~50-100 bytes per wall segment

### Key Event (Python → C)

```json
{
  "pressed": true,
  "key": 119
}
```

**Key codes:** Standard DOOM key codes (see input mapping)

## API Functions

### Socket Layer (`doom_socket.h`)

```c
/* Connect to Python server */
int doom_socket_connect(void);
// Returns: 0 on success, -1 on error
// Blocks until connection established

/* Send frame data */
int doom_socket_send_frame(const char* json, size_t len);
// Returns: 0 on success, -1 on error

/* Receive key (non-blocking) */
int doom_socket_recv_key(int* pressed, unsigned char* key);
// Returns: 1 if key received, 0 if no data, -1 on error

/* Close connection */
void doom_socket_close(void);

/* Check connection status */
int doom_socket_is_connected(void);
// Returns: 1 if connected, 0 if not
```

### Platform Layer (`doomgeneric_kicad.c`)

```c
/* Initialize platform (called once) */
void DG_Init(void);

/* Render frame (called 35/sec) */
void DG_DrawFrame(void);

/* Sleep for milliseconds */
void DG_SleepMs(uint32_t ms);

/* Get elapsed time in ms */
uint32_t DG_GetTicksMs(void);

/* Get keyboard input */
int DG_GetKey(int* pressed, unsigned char* key);
// Returns: 1 if key available, 0 if none
```

## Common Tasks

### Adding Debug Logging

```c
// In doomgeneric_kicad.c
void DG_DrawFrame(void) {
    printf("[DEBUG] Frame %d: %d walls\n", g_frame_count, wall_count);
    // ... rest of function
}
```

### Dumping Frame Data

```c
// Add to DG_DrawFrame()
if (g_frame_count == 100) {
    FILE* f = fopen("/tmp/frame_100.json", "w");
    fwrite(json_data, 1, json_len, f);
    fclose(f);
}
```

### Changing Vector Limit

```c
// In convert_frame_to_json()
for (int y = 0; y < DOOMGENERIC_RESY && wall_count < 500; y += 4) {
//                                                      ^^^ increase limit
```

### Adding Connection Timeout

```c
// In doom_socket_connect()
struct timeval timeout = {.tv_sec = 5, .tv_usec = 0};
setsockopt(g_socket_fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
```

## Performance Tuning

### Current Timings (M1 Mac)

| Operation | Time | Optimization |
|-----------|------|--------------|
| Vector extraction | 0.44ms | Sample every 4th row |
| JSON serialization | 0.05ms | Static buffer |
| Socket send | 0.05ms | Unix socket |
| **Total** | **~0.5ms** | **96% headroom** |

### Optimization Knobs

```c
// Reduce scan density (faster, less accurate)
for (int y = 0; y < DOOMGENERIC_RESY; y += 8) {  // was: y += 4
//                                          ^^ larger step

// Reduce wall limit (faster send)
wall_count < 150  // was: 200

// Increase edge threshold (fewer false positives)
const int EDGE_THRESHOLD = 50;  // was: 30
```

## Error Handling

### Connection Failures

```c
if (doom_socket_connect() < 0) {
    fprintf(stderr, "ERROR: Cannot connect to KiCad\n");
    fprintf(stderr, "Check that:\n");
    fprintf(stderr, "  1. KiCad is running\n");
    fprintf(stderr, "  2. Plugin started socket server\n");
    fprintf(stderr, "  3. Socket path: %s\n", SOCKET_PATH);
    exit(1);
}
```

### Send Failures

```c
if (doom_socket_send_frame(json, len) < 0) {
    static int error_count = 0;
    if (++error_count > 10) {
        fprintf(stderr, "Too many send errors - exiting\n");
        exit(1);
    }
}
```

## Debugging

### Enable Verbose Logging

```c
// Add at top of doom_socket.c
#define DEBUG_SOCKET 1

#ifdef DEBUG_SOCKET
#define DLOG(...) printf("[SOCKET] " __VA_ARGS__)
#else
#define DLOG(...)
#endif

// Use in code:
DLOG("Sending %zu bytes\n", len);
```

### GDB Breakpoints

```bash
gdb ./doomgeneric_kicad

# Set breakpoints
(gdb) break DG_DrawFrame
(gdb) break doom_socket_send_frame
(gdb) break doom_socket_recv_key

# Run
(gdb) run

# Inspect variables
(gdb) print g_frame_count
(gdb) print json_data
(gdb) x/100c json_data  # print 100 chars
```

### Valgrind Memory Check

```bash
valgrind --leak-check=full ./doomgeneric_kicad
```

## Testing

### Unit Test: Socket Connection

```bash
# Terminal 1: Mock Python server
python3 << 'EOF'
import socket, struct, os
os.unlink("/tmp/kicad_doom.sock") if os.path.exists("/tmp/kicad_doom.sock") else None
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.bind("/tmp/kicad_doom.sock")
s.listen(1)
c, _ = s.accept()
c.sendall(struct.pack('II', 0x03, 2) + b'{}')
print("INIT sent")
while True:
    h = c.recv(8)
    if len(h) < 8: break
    t, l = struct.unpack('II', h)
    p = c.recv(l)
    print(f"Received type={t:02x} len={l}")
EOF

# Terminal 2: Run DOOM
./doomgeneric_kicad
```

### Integration Test: Full Loop

```bash
# Requires Phase 2 Python plugin
cd /Users/tribune/Desktop/KiDoom
python3 -m kicad_doom_plugin.test_integration
```

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| "Connection refused" | Python not running | Start KiCad plugin first |
| "doom1.wad not found" | Missing WAD | Place in same dir as binary |
| Crashes on startup | Bad socket path | Check `/tmp/kicad_doom.sock` |
| No keyboard input | Keys not sent | Check Python input_handler |
| Slow frame rate | Too many vectors | Reduce wall_count limit |
| "Undefined reference" | Missing libs | Add `-lm` to LDFLAGS |

## Constants

```c
/* Screen dimensions */
#define DOOMGENERIC_RESX 320
#define DOOMGENERIC_RESY 200

/* Socket path */
#define SOCKET_PATH "/tmp/kicad_doom.sock"

/* Message types */
#define MSG_FRAME_DATA    0x01
#define MSG_KEY_EVENT     0x02
#define MSG_INIT_COMPLETE 0x03
#define MSG_SHUTDOWN      0x04

/* Limits */
#define MAX_QUEUED_KEYS   16
#define MAX_WALL_SEGMENTS 200
#define EDGE_THRESHOLD    30
```

## Key Mappings (DOOM Codes)

| Key | Code | DOOM Action |
|-----|------|-------------|
| W | 0x77 | Forward |
| S | 0x73 | Backward |
| A | 0x61 | Strafe left |
| D | 0x64 | Strafe right |
| ← | 0xAC | Turn left |
| → | 0xAE | Turn right |
| Ctrl | 0x9D | Fire |
| Space | 0x39 | Use/Open |
| Esc | 0x1B | Menu |

## Quick Fixes

### Fix: Increase JSON Buffer

```c
// In convert_frame_to_json()
static char json_buf[131072];  // was: 65536 (double size)
```

### Fix: Non-blocking Send

```c
// In doom_socket_connect()
int flags = fcntl(g_socket_fd, F_GETFL, 0);
fcntl(g_socket_fd, F_SETFL, flags | O_NONBLOCK);
```

### Fix: Better Error Messages

```c
// In doom_socket_send_frame()
if (send_exactly(g_socket_fd, json_data, len) < 0) {
    fprintf(stderr, "Send failed: %s (errno=%d)\n", strerror(errno), errno);
    return -1;
}
```

## Resources

- **Source code:** `/Users/tribune/Desktop/KiDoom/doom/source/`
- **Build output:** `/Users/tribune/Desktop/KiDoom/doom/doomgeneric_kicad`
- **Socket path:** `/tmp/kicad_doom.sock`
- **Full docs:** `README.md`, `VECTOR_EXTRACTION.md`
- **Benchmarks:** `/Users/tribune/Desktop/KiDoom/tests/BENCHMARK_RESULTS.md`

---

**Quick Start:** `./build.sh` then read `README.md` for next steps.
