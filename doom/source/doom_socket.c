/**
 * doom_socket.c
 *
 * Implementation of socket communication layer for DOOM <-> KiCad bridge.
 * Handles Unix domain socket connection, message framing, and data transfer.
 */

#include "doom_socket.h"

#include <sys/socket.h>
#include <sys/un.h>
#include <sys/select.h>
#include <unistd.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <errno.h>

/* Global socket file descriptor */
static int g_socket_fd = -1;

/**
 * Helper: Read exactly n bytes from socket.
 * Handles partial reads by looping until all bytes received.
 *
 * Returns: 0 on success, -1 on error or connection closed
 */
static int recv_exactly(int fd, void* buffer, size_t n) {
    size_t total_read = 0;
    unsigned char* buf = (unsigned char*)buffer;

    while (total_read < n) {
        ssize_t bytes_read = read(fd, buf + total_read, n - total_read);

        if (bytes_read <= 0) {
            if (bytes_read < 0) {
                perror("recv_exactly: read");
            } else {
                fprintf(stderr, "recv_exactly: connection closed\n");
            }
            return -1;
        }

        total_read += bytes_read;
    }

    return 0;
}

/**
 * Helper: Send exactly n bytes to socket.
 * Handles partial writes by looping until all bytes sent.
 *
 * Returns: 0 on success, -1 on error
 */
static int send_exactly(int fd, const void* buffer, size_t n) {
    size_t total_sent = 0;
    const unsigned char* buf = (const unsigned char*)buffer;

    while (total_sent < n) {
        ssize_t bytes_sent = write(fd, buf + total_sent, n - total_sent);

        if (bytes_sent <= 0) {
            perror("send_exactly: write");
            return -1;
        }

        total_sent += bytes_sent;
    }

    return 0;
}

int doom_socket_connect(void) {
    struct sockaddr_un addr;
    uint32_t msg_type, payload_len;

    /* Create socket */
    g_socket_fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (g_socket_fd < 0) {
        perror("doom_socket_connect: socket");
        return -1;
    }

    /* Set large socket buffers to prevent blocking on large frame data */
    int bufsize = 1048576;  /* 1MB buffer */
    setsockopt(g_socket_fd, SOL_SOCKET, SO_SNDBUF, &bufsize, sizeof(bufsize));
    setsockopt(g_socket_fd, SOL_SOCKET, SO_RCVBUF, &bufsize, sizeof(bufsize));

    /* Setup address */
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    strncpy(addr.sun_path, SOCKET_PATH, sizeof(addr.sun_path) - 1);

    /* Connect to Python server */
    printf("Connecting to KiCad Python at %s...\n", SOCKET_PATH);
    if (connect(g_socket_fd, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
        perror("doom_socket_connect: connect");
        fprintf(stderr, "Make sure KiCad plugin is running and socket server started!\n");
        close(g_socket_fd);
        g_socket_fd = -1;
        return -1;
    }

    /* Wait for INIT_COMPLETE message */
    printf("Waiting for INIT_COMPLETE from Python...\n");

    if (recv_exactly(g_socket_fd, &msg_type, sizeof(msg_type)) < 0) {
        fprintf(stderr, "doom_socket_connect: failed to read message type\n");
        close(g_socket_fd);
        g_socket_fd = -1;
        return -1;
    }

    if (recv_exactly(g_socket_fd, &payload_len, sizeof(payload_len)) < 0) {
        fprintf(stderr, "doom_socket_connect: failed to read payload length\n");
        close(g_socket_fd);
        g_socket_fd = -1;
        return -1;
    }

    if (msg_type != MSG_INIT_COMPLETE) {
        fprintf(stderr, "doom_socket_connect: expected INIT_COMPLETE (0x%02x), got 0x%02x\n",
                MSG_INIT_COMPLETE, msg_type);
        close(g_socket_fd);
        g_socket_fd = -1;
        return -1;
    }

    /* Discard init payload (empty JSON or acknowledgment) */
    if (payload_len > 0) {
        char* discard_buf = malloc(payload_len);
        if (discard_buf) {
            recv_exactly(g_socket_fd, discard_buf, payload_len);
            free(discard_buf);
        }
    }

    printf("Connected to KiCad successfully!\n");
    return 0;
}

int doom_socket_send_frame(const char* json_data, size_t len) {
    uint32_t header[2];

    if (g_socket_fd < 0) {
        fprintf(stderr, "doom_socket_send_frame: not connected\n");
        return -1;
    }

    /* Build message header */
    header[0] = MSG_FRAME_DATA;
    header[1] = (uint32_t)len;

    /* Send header */
    if (send_exactly(g_socket_fd, header, sizeof(header)) < 0) {
        fprintf(stderr, "doom_socket_send_frame: failed to send header\n");
        return -1;
    }

    /* Send JSON payload */
    if (send_exactly(g_socket_fd, json_data, len) < 0) {
        fprintf(stderr, "doom_socket_send_frame: failed to send payload\n");
        return -1;
    }

    return 0;
}

int doom_socket_recv_key(int* pressed, unsigned char* key) {
    fd_set readfds;
    struct timeval tv;
    uint32_t msg_type, payload_len;
    char json_buf[256];  /* Key events are small */
    int ret;

    if (g_socket_fd < 0) {
        return 0;  /* Not connected, no keys */
    }

    /* Non-blocking check for data (zero timeout) */
    FD_ZERO(&readfds);
    FD_SET(g_socket_fd, &readfds);
    tv.tv_sec = 0;
    tv.tv_usec = 0;

    ret = select(g_socket_fd + 1, &readfds, NULL, NULL, &tv);
    if (ret <= 0) {
        /* No data available or error */
        return 0;
    }

    /* Data available - read message header */
    if (recv_exactly(g_socket_fd, &msg_type, sizeof(msg_type)) < 0) {
        return -1;
    }

    if (recv_exactly(g_socket_fd, &payload_len, sizeof(payload_len)) < 0) {
        return -1;
    }

    /* Check message type */
    if (msg_type == MSG_SHUTDOWN) {
        printf("Received SHUTDOWN message from Python\n");
        return -1;
    }

    if (msg_type != MSG_KEY_EVENT) {
        /* Unknown message type - discard payload and continue */
        if (payload_len > 0 && payload_len < 65536) {
            char* discard_buf = malloc(payload_len);
            if (discard_buf) {
                recv_exactly(g_socket_fd, discard_buf, payload_len);
                free(discard_buf);
            }
        }
        return 0;
    }

    /* Read key event payload */
    if (payload_len >= sizeof(json_buf)) {
        fprintf(stderr, "doom_socket_recv_key: payload too large (%u bytes)\n", payload_len);
        return -1;
    }

    if (recv_exactly(g_socket_fd, json_buf, payload_len) < 0) {
        return -1;
    }
    json_buf[payload_len] = '\0';

    /* Parse JSON: {"pressed": true/false, "key": <code>} */
    /* Simple parsing - in production would use cJSON library */
    int pressed_val = 0;
    int key_val = 0;

    /* Look for "pressed": true or "pressed": false */
    const char* pressed_str = strstr(json_buf, "\"pressed\":");
    if (pressed_str) {
        if (strstr(pressed_str, "true")) {
            pressed_val = 1;
        } else {
            pressed_val = 0;
        }
    }

    /* Look for "key": <number> */
    const char* key_str = strstr(json_buf, "\"key\":");
    if (key_str) {
        /* Skip past "key": and any whitespace */
        key_str += 6;
        while (*key_str == ' ' || *key_str == '\t') key_str++;

        /* Parse integer */
        key_val = atoi(key_str);
    }

    /* Output values */
    *pressed = pressed_val;
    *key = (unsigned char)key_val;

    return 1;  /* Key event received */
}

void doom_socket_close(void) {
    if (g_socket_fd >= 0) {
        /* Send shutdown message */
        uint32_t header[2] = {MSG_SHUTDOWN, 0};
        write(g_socket_fd, header, sizeof(header));

        /* Close socket */
        close(g_socket_fd);
        g_socket_fd = -1;

        printf("Socket connection closed\n");
    }
}

int doom_socket_is_connected(void) {
    return (g_socket_fd >= 0) ? 1 : 0;
}

int doom_socket_send_message(uint32_t msg_type, const char* json_data, size_t len) {
    uint32_t header[2];

    if (g_socket_fd < 0) {
        fprintf(stderr, "doom_socket_send_message: not connected\n");
        return -1;
    }

    /* Build message header */
    header[0] = msg_type;
    header[1] = (uint32_t)len;

    /* Send header */
    if (send_exactly(g_socket_fd, header, sizeof(header)) < 0) {
        fprintf(stderr, "doom_socket_send_message: failed to send header\n");
        return -1;
    }

    /* Send JSON payload */
    if (send_exactly(g_socket_fd, json_data, len) < 0) {
        fprintf(stderr, "doom_socket_send_message: failed to send payload\n");
        return -1;
    }

    return 0;
}
