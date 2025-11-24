/**
 * doomgeneric_kicad.c - Version 2
 *
 * DOOM platform implementation for KiCad PCB rendering.
 *
 * This version extracts vectors DIRECTLY from DOOM's internal data structures:
 * - drawsegs[] array for wall segments
 * - vissprites[] array for entities/sprites
 *
 * No pixel buffer scanning - pure vector extraction!
 */

#include "doomgeneric.h"
#include "doom_socket.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/time.h>
#include <unistd.h>

/* Import DOOM's internal rendering structures */
#include "r_defs.h"
#include "r_bsp.h"
#include "r_state.h"

/* Declare external DOOM variables */
extern drawseg_t drawsegs[MAXDRAWSEGS];
extern drawseg_t* ds_p;

extern vissprite_t vissprites[MAXVISSPRITES];
extern vissprite_t* vissprite_p;

extern int viewheight;
extern int viewwidth;

/* Internal state */
static uint32_t g_start_time_ms = 0;
static int g_frame_count = 0;

/* Keyboard state buffer */
#define MAX_QUEUED_KEYS 16
static struct {
    int pressed;
    unsigned char key;
} g_key_queue[MAX_QUEUED_KEYS];
static int g_key_queue_head = 0;
static int g_key_queue_tail = 0;

/**
 * Helper: Get current time in milliseconds.
 */
static uint32_t get_time_ms(void) {
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return (tv.tv_sec * 1000) + (tv.tv_usec / 1000);
}

/**
 * Helper: Add key to queue.
 */
static void enqueue_key(int pressed, unsigned char key) {
    int next = (g_key_queue_tail + 1) % MAX_QUEUED_KEYS;
    if (next != g_key_queue_head) {
        g_key_queue[g_key_queue_tail].pressed = pressed;
        g_key_queue[g_key_queue_tail].key = key;
        g_key_queue_tail = next;
    }
}

/**
 * Helper: Remove key from queue.
 */
static int dequeue_key(int* pressed, unsigned char* key) {
    if (g_key_queue_head == g_key_queue_tail) {
        return 0;
    }

    *pressed = g_key_queue[g_key_queue_head].pressed;
    *key = g_key_queue[g_key_queue_head].key;
    g_key_queue_head = (g_key_queue_head + 1) % MAX_QUEUED_KEYS;

    return 1;
}

/**
 * Convert DOOM's internal vectors to JSON.
 *
 * This directly reads from drawsegs[] and vissprites[] arrays!
 */
static char* extract_vectors_to_json(size_t* out_len) {
    static char json_buf[131072];  /* 128KB buffer */
    int offset = 0;

    /* Start JSON */
    offset += snprintf(json_buf + offset, sizeof(json_buf) - offset,
                      "{\"frame\":%d,\"walls\":[", g_frame_count);

    /* Extract wall segments from drawsegs[] array */
    int wall_count = ds_p - drawsegs;  /* Number of drawn segments this frame */

    for (int i = 0; i < wall_count && i < MAXDRAWSEGS; i++) {
        drawseg_t* ds = &drawsegs[i];

        /* Screen column range */
        int x1 = ds->x1;
        int x2 = ds->x2;

        /* Skip invalid segments */
        if (x1 < 0 || x2 < 0 || x1 >= viewwidth || x2 >= viewwidth || x1 > x2) {
            continue;
        }

        /* Calculate depth from scale (closer = larger scale) */
        /* scale1 is fixed-point (16.16), larger values = closer */
        int scale = (ds->scale1 >> FRACBITS);  /* Convert to integer */
        int distance = (scale > 0) ? (1000 / scale) : 999;  /* Inverse for distance */
        if (distance < 0) distance = 999;
        if (distance > 999) distance = 999;

        /* Calculate wall height from scale */
        int height = scale / 2;
        if (height < 1) height = 1;
        if (height > 200) height = 200;

        /* Calculate y position (center of screen, adjusted by height) */
        int y = viewheight / 2;

        if (i > 0) {
            offset += snprintf(json_buf + offset, sizeof(json_buf) - offset, ",");
        }

        /* Output as line segment */
        offset += snprintf(json_buf + offset, sizeof(json_buf) - offset,
                          "[%d,%d,%d,%d,%d]",
                          x1, y, x2, y, distance);
    }

    offset += snprintf(json_buf + offset, sizeof(json_buf) - offset, "],\"entities\":[");

    /* Extract entities from vissprites[] array */
    int sprite_count = vissprite_p - vissprites;

    for (int i = 0; i < sprite_count && i < MAXVISSPRITES; i++) {
        vissprite_t* vis = &vissprites[i];

        /* Screen position */
        int x1 = vis->x1;
        int x2 = vis->x2;

        /* Skip invalid sprites */
        if (x1 < 0 || x2 < 0 || x1 >= viewwidth || x2 >= viewwidth) {
            continue;
        }

        /* Center position */
        int x = (x1 + x2) / 2;
        int y = viewheight / 2;  /* Simplified - could use gz for actual height */

        /* Calculate distance from scale */
        int scale = (vis->scale >> FRACBITS);
        int distance = (scale > 0) ? (1000 / scale) : 999;
        if (distance < 0) distance = 999;
        if (distance > 999) distance = 999;

        /* Size based on scale */
        int size = scale / 10;
        if (size < 3) size = 3;
        if (size > 50) size = 50;

        /* Sprite type (simplified - could decode from patch/colormap) */
        int type = 1;  /* Default to enemy/object */

        if (i > 0) {
            offset += snprintf(json_buf + offset, sizeof(json_buf) - offset, ",");
        }

        offset += snprintf(json_buf + offset, sizeof(json_buf) - offset,
                          "{\"x\":%d,\"y\":%d,\"size\":%d,\"type\":%d,\"angle\":0}",
                          x, y, size, type);
    }

    /* Close JSON */
    offset += snprintf(json_buf + offset, sizeof(json_buf) - offset, "]}");

    *out_len = offset;
    return json_buf;
}

/* ========================================================================
 * DOOMGENERIC REQUIRED FUNCTIONS
 * ======================================================================== */

/**
 * DG_Init() - Initialize platform
 */
void DG_Init(void) {
    printf("\n");
    printf("========================================\n");
    printf("  DOOM on KiCad PCB (Vector Mode V2)\n");
    printf("========================================\n");
    printf("\n");

    g_start_time_ms = get_time_ms();

    printf("Connecting to socket server...\n");
    if (doom_socket_connect() < 0) {
        fprintf(stderr, "\nERROR: Failed to connect!\n");
        fprintf(stderr, "Make sure standalone renderer or KiCad plugin is running.\n\n");
        exit(1);
    }

    printf("\nInitialization complete!\n");
    printf("Extracting vectors directly from DOOM's drawsegs[] and vissprites[]!\n\n");
}

/**
 * DG_DrawFrame() - Send frame vectors
 */
void DG_DrawFrame(void) {
    size_t json_len;
    char* json_data;

    /* Extract vectors from DOOM's internal arrays */
    json_data = extract_vectors_to_json(&json_len);

    /* Send to renderer */
    if (doom_socket_send_frame(json_data, json_len) < 0) {
        fprintf(stderr, "ERROR: Failed to send frame\n");
        exit(1);
    }

    g_frame_count++;

    /* Print stats every 100 frames */
    if (g_frame_count % 100 == 0) {
        uint32_t elapsed_ms = get_time_ms() - g_start_time_ms;
        float fps = (g_frame_count * 1000.0f) / elapsed_ms;

        int wall_count = ds_p - drawsegs;
        int sprite_count = vissprite_p - vissprites;

        printf("Frame %d: %.1f FPS | Walls: %d | Sprites: %d\n",
               g_frame_count, fps, wall_count, sprite_count);
    }

    /* Poll for keyboard input */
    int pressed;
    unsigned char key;
    while (doom_socket_recv_key(&pressed, &key) > 0) {
        enqueue_key(pressed, key);
    }
}

/**
 * DG_SleepMs() - Sleep for milliseconds
 */
void DG_SleepMs(uint32_t ms) {
    usleep(ms * 1000);
}

/**
 * DG_GetTicksMs() - Get milliseconds since init
 */
uint32_t DG_GetTicksMs(void) {
    return get_time_ms() - g_start_time_ms;
}

/**
 * DG_GetKey() - Get keyboard input
 */
int DG_GetKey(int* pressed, unsigned char* key) {
    return dequeue_key(pressed, key);
}

/**
 * DG_SetWindowTitle() - Set window title (unused for KiCad)
 */
void DG_SetWindowTitle(const char* title) {
    /* Not applicable for KiCad rendering */
}
