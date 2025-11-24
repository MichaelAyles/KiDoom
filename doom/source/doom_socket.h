/**
 * doom_socket.h
 *
 * Socket communication layer for DOOM <-> KiCad Python bridge.
 * Provides functions to connect to Python socket server, send frame data,
 * and receive keyboard input.
 *
 * Protocol: Binary messages over Unix domain socket
 * Format: [4 bytes: msg_type][4 bytes: payload_len][N bytes: JSON payload]
 */

#ifndef DOOM_SOCKET_H
#define DOOM_SOCKET_H

#include <stdint.h>
#include <stddef.h>

/* Message type constants (must match Python side) */
#define MSG_FRAME_DATA    0x01  /* DOOM → Python: Frame rendering data */
#define MSG_KEY_EVENT     0x02  /* Python → DOOM: Keyboard event */
#define MSG_INIT_COMPLETE 0x03  /* Python → DOOM: Connection established */
#define MSG_SHUTDOWN      0x04  /* Bidirectional: Clean shutdown */
#define MSG_SCREENSHOT    0x05  /* DOOM → Python: SDL screenshot saved, request combine */

/* Socket path (must match Python side) */
#define SOCKET_PATH "/tmp/kicad_doom.sock"

/**
 * Connect to Python KiCad socket server.
 * Blocks until connection is established and INIT_COMPLETE is received.
 *
 * Returns: 0 on success, -1 on error
 */
int doom_socket_connect(void);

/**
 * Send frame data to Python renderer.
 * Frame data must be formatted as JSON string.
 *
 * Args:
 *   json_data: JSON string containing frame data
 *   len: Length of json_data in bytes
 *
 * Returns: 0 on success, -1 on error
 */
int doom_socket_send_frame(const char* json_data, size_t len);

/**
 * Receive keyboard event from Python (non-blocking).
 * Uses select() with zero timeout - returns immediately if no data available.
 *
 * Args:
 *   pressed: Output - 1 if key pressed, 0 if released
 *   key: Output - Key code (DOOM key code format)
 *
 * Returns: 1 if key event received, 0 if no data, -1 on error
 */
int doom_socket_recv_key(int* pressed, unsigned char* key);

/**
 * Close socket connection and send shutdown message.
 * Safe to call multiple times.
 */
void doom_socket_close(void);

/**
 * Check if socket is currently connected.
 *
 * Returns: 1 if connected, 0 if not
 */
int doom_socket_is_connected(void);

/**
 * Send generic message with JSON payload.
 * Used for non-frame messages like screenshot notifications.
 *
 * Args:
 *   msg_type: Message type constant (e.g. MSG_SCREENSHOT)
 *   json_data: JSON string payload
 *   len: Length of json_data in bytes
 *
 * Returns: 0 on success, -1 on error
 */
int doom_socket_send_message(uint32_t msg_type, const char* json_data, size_t len);

#endif /* DOOM_SOCKET_H */
