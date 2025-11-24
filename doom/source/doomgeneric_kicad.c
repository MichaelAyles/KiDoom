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
#include "r_things.h"
#include "p_pspr.h"    /* For weapon sprites */
#include "doomstat.h"  /* For players[] array */

/* Declare external DOOM variables */
extern drawseg_t drawsegs[MAXDRAWSEGS];
extern drawseg_t* ds_p;

extern vissprite_t vissprites[MAXVISSPRITES];
extern vissprite_t* vissprite_p;

extern int viewheight;
extern int viewwidth;

extern player_t players[MAXPLAYERS];
extern int consoleplayer;  /* Current player index */

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
    int wall_output = 0;

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
        int scale1 = (ds->scale1 >> FRACBITS);
        int scale2 = (ds->scale2 >> FRACBITS);
        int distance = (scale1 > 0) ? (1000 / scale1) : 999;
        if (distance < 0) distance = 999;
        if (distance > 999) distance = 999;

        /* Use actual clipping arrays if available, otherwise estimate */
        int y1_top, y1_bottom, y2_top, y2_bottom;

        if (ds->sprtopclip != NULL && ds->sprbottomclip != NULL) {
            /* Use DOOM's actual calculated screen coordinates! */
            y1_top = ds->sprtopclip[0];  /* Top at left edge */
            y1_bottom = ds->sprbottomclip[0];  /* Bottom at left edge */

            int width = x2 - x1;
            if (width > 0) {
                y2_top = ds->sprtopclip[width];  /* Top at right edge */
                y2_bottom = ds->sprbottomclip[width];  /* Bottom at right edge */
            } else {
                y2_top = y1_top;
                y2_bottom = y1_bottom;
            }
        } else {
            /* Fallback: estimate from scale */
            int height1 = scale1;
            if (height1 < 10) height1 = 10;
            if (height1 > viewheight) height1 = viewheight;

            int height2 = scale2;
            if (height2 < 10) height2 = 10;
            if (height2 > viewheight) height2 = viewheight;

            int y_center = viewheight / 2;
            y1_top = y_center - (height1 / 2);
            y1_bottom = y_center + (height1 / 2);
            y2_top = y_center - (height2 / 2);
            y2_bottom = y_center + (height2 / 2);
        }

        /* Clamp to screen bounds */
        if (y1_top < 0) y1_top = 0;
        if (y1_bottom >= viewheight) y1_bottom = viewheight - 1;
        if (y2_top < 0) y2_top = 0;
        if (y2_bottom >= viewheight) y2_bottom = viewheight - 1;

        if (wall_output > 0) {
            offset += snprintf(json_buf + offset, sizeof(json_buf) - offset, ",");
        }

        /* Output wall as two vertical lines (left and right edges) */
        /* Format: [x1, y1_top, y1_bottom, x2, y2_top, y2_bottom, distance] */
        offset += snprintf(json_buf + offset, sizeof(json_buf) - offset,
                          "[%d,%d,%d,%d,%d,%d,%d]",
                          x1, y1_top, y1_bottom, x2, y2_top, y2_bottom, distance);
        wall_output++;
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

        /* Center X position */
        int x = (x1 + x2) / 2;

        /* Calculate distance from scale */
        int scale = (vis->scale >> FRACBITS);
        if (scale <= 0) scale = 1;
        int distance = 1000 / scale;
        if (distance < 0) distance = 999;
        if (distance > 999) distance = 999;

        /* Calculate sprite screen height using DOOM's projection math */
        /* gzt is the top of the sprite in world space (fixed point) */
        /* Convert to screen Y coordinate using the same math DOOM uses */
        fixed_t gzt = vis->gzt;
        fixed_t gz = gzt - (vis->scale * 64);  /* Approximate bottom (64 unit tall sprite) */

        /* Project world Z to screen Y using centeryfrac and scale */
        /* centeryfrac = viewheight/2 in fixed point */
        extern fixed_t centeryfrac;
        int y_top = (centeryfrac - (gzt * vis->scale)) >> FRACBITS;
        int y_bottom = (centeryfrac - (gz * vis->scale)) >> FRACBITS;

        /* Clamp to screen bounds */
        if (y_top < 0) y_top = 0;
        if (y_top >= viewheight) y_top = viewheight - 1;
        if (y_bottom < 0) y_bottom = 0;
        if (y_bottom >= viewheight) y_bottom = viewheight - 1;

        int sprite_height = y_bottom - y_top;
        if (sprite_height < 5) sprite_height = 5;

        /* Sprite type - use sprite index for unique identification */
        int type = i % 8;  /* Use index modulo 8 for color variety */

        if (i > 0) {
            offset += snprintf(json_buf + offset, sizeof(json_buf) - offset, ",");
        }

        offset += snprintf(json_buf + offset, sizeof(json_buf) - offset,
                          "{\"x\":%d,\"y_top\":%d,\"y_bottom\":%d,\"height\":%d,\"type\":%d,\"distance\":%d,\"angle\":0}",
                          x, y_top, y_bottom, sprite_height, type, distance);
    }

    /* Close entities array */
    offset += snprintf(json_buf + offset, sizeof(json_buf) - offset, "],\"weapon\":");

    /* Extract player's weapon sprite (psprite) */
    player_t* player = &players[consoleplayer];
    pspdef_t* weapon_psp = &player->psprites[ps_weapon];

    if (weapon_psp->state != NULL) {
        /* Weapon sprite is active */
        /* Convert fixed-point position to screen coordinates */
        int wx = (weapon_psp->sx >> FRACBITS) + (viewwidth / 2);
        int wy = (weapon_psp->sy >> FRACBITS) + viewheight - 32;  /* Bottom of screen */

        /* Clamp to screen bounds */
        if (wx < 0) wx = 0;
        if (wx >= viewwidth) wx = viewwidth - 1;
        if (wy < 0) wy = 0;
        if (wy >= viewheight) wy = viewheight - 1;

        offset += snprintf(json_buf + offset, sizeof(json_buf) - offset,
                          "{\"x\":%d,\"y\":%d,\"visible\":true}", wx, wy);
    } else {
        /* No weapon visible */
        offset += snprintf(json_buf + offset, sizeof(json_buf) - offset,
                          "{\"visible\":false}");
    }

    /* Close JSON */
    offset += snprintf(json_buf + offset, sizeof(json_buf) - offset, "}");

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

/**
 * main() - Entry point
 */
int main(int argc, char **argv) {
    doomgeneric_Create(argc, argv);

    /* Main game loop */
    while (1) {
        doomgeneric_Tick();
    }

    return 0;
}
