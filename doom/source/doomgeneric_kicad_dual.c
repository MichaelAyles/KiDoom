/**
 * doomgeneric_kicad_dual.c
 *
 * Dual-output version:
 * 1. Shows original DOOM graphics in SDL window
 * 2. Sends vectors to standalone renderer via socket
 *
 * Perfect for side-by-side comparison!
 */

#include "doomgeneric.h"
#include "doom_socket.h"
#include "doomkeys.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/time.h>
#include <unistd.h>
#include <SDL.h>

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
extern int consoleplayer;

/* SDL state */
static SDL_Window* window = NULL;
static SDL_Renderer* renderer = NULL;
static SDL_Texture* texture = NULL;

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
 * Helper: Convert SDL key to DOOM key
 */
static unsigned char sdl_to_doom_key(SDL_Keycode key) {
    switch (key) {
        case SDLK_RETURN: return KEY_ENTER;
        case SDLK_ESCAPE: return KEY_ESCAPE;
        case SDLK_LEFT: return KEY_LEFTARROW;
        case SDLK_RIGHT: return KEY_RIGHTARROW;
        case SDLK_UP: return KEY_UPARROW;
        case SDLK_DOWN: return KEY_DOWNARROW;
        case SDLK_LCTRL:
        case SDLK_RCTRL: return KEY_FIRE;
        case SDLK_SPACE: return KEY_USE;
        case SDLK_LSHIFT:
        case SDLK_RSHIFT: return KEY_RSHIFT;
        default: return tolower(key);
    }
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
 * Extract vectors from DOOM's internal data structures.
 */
static char* extract_vectors_to_json(size_t* out_len) {
    static char json_buf[131072];  /* 128KB buffer */
    int offset = 0;

    /* Start JSON */
    offset += snprintf(json_buf + offset, sizeof(json_buf) - offset,
                      "{\"frame\":%d,\"walls\":[", g_frame_count);

    /* Extract wall segments from drawsegs[] array */
    int wall_count = ds_p - drawsegs;
    int wall_output = 0;

    for (int i = 0; i < wall_count && i < MAXDRAWSEGS; i++) {
        drawseg_t* ds = &drawsegs[i];

        int x1 = ds->x1;
        int x2 = ds->x2;

        if (x1 < 0 || x2 < 0 || x1 >= viewwidth || x2 >= viewwidth || x1 > x2) {
            continue;
        }

        int scale1 = (ds->scale1 >> FRACBITS);
        int scale2 = (ds->scale2 >> FRACBITS);
        int distance = (scale1 > 0) ? (1000 / scale1) : 999;
        if (distance < 0) distance = 999;
        if (distance > 999) distance = 999;

        /* Use actual clipping arrays if available */
        int y1_top, y1_bottom, y2_top, y2_bottom;

        if (ds->sprtopclip != NULL && ds->sprbottomclip != NULL) {
            y1_top = ds->sprtopclip[0];
            y1_bottom = ds->sprbottomclip[0];

            int width = x2 - x1;
            if (width > 0) {
                y2_top = ds->sprtopclip[width];
                y2_bottom = ds->sprbottomclip[width];
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

        /* Output wall as quadrilateral (two edges) */
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

        int x1 = vis->x1;
        int x2 = vis->x2;

        if (x1 < 0 || x2 < 0 || x1 >= viewwidth || x2 >= viewwidth) {
            continue;
        }

        int x = (x1 + x2) / 2;
        int y = viewheight / 2;

        int scale = (vis->scale >> FRACBITS);
        int distance = (scale > 0) ? (1000 / scale) : 999;
        if (distance < 0) distance = 999;
        if (distance > 999) distance = 999;

        int size = scale / 10;
        if (size < 3) size = 3;
        if (size > 50) size = 50;

        int type = i % 8;  /* Use index modulo 8 for color variety */

        if (i > 0) {
            offset += snprintf(json_buf + offset, sizeof(json_buf) - offset, ",");
        }

        offset += snprintf(json_buf + offset, sizeof(json_buf) - offset,
                          "{\"x\":%d,\"y\":%d,\"size\":%d,\"type\":%d,\"distance\":%d,\"angle\":0}",
                          x, y, size, type, distance);
    }

    /* Close entities array */
    offset += snprintf(json_buf + offset, sizeof(json_buf) - offset, "],\"weapon\":");

    /* Extract player's weapon sprite */
    player_t* player = &players[consoleplayer];
    pspdef_t* weapon_psp = &player->psprites[ps_weapon];

    if (weapon_psp->state != NULL) {
        int wx = (weapon_psp->sx >> FRACBITS) + (viewwidth / 2);
        int wy = (weapon_psp->sy >> FRACBITS) + viewheight - 32;

        if (wx < 0) wx = 0;
        if (wx >= viewwidth) wx = viewwidth - 1;
        if (wy < 0) wy = 0;
        if (wy >= viewheight) wy = viewheight - 1;

        offset += snprintf(json_buf + offset, sizeof(json_buf) - offset,
                          "{\"x\":%d,\"y\":%d,\"visible\":true}", wx, wy);
    } else {
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
 * DG_Init() - Initialize both SDL window and socket
 */
void DG_Init(void) {
    printf("\n");
    printf("========================================\n");
    printf("  DOOM Dual Output Mode\n");
    printf("  SDL Window + Vector Socket\n");
    printf("========================================\n");
    printf("\n");

    g_start_time_ms = get_time_ms();

    /* Initialize SDL */
    if (SDL_Init(SDL_INIT_VIDEO) < 0) {
        fprintf(stderr, "SDL_Init failed: %s\n", SDL_GetError());
        exit(1);
    }

    window = SDL_CreateWindow("DOOM (Original Graphics)",
                              SDL_WINDOWPOS_UNDEFINED,
                              SDL_WINDOWPOS_UNDEFINED,
                              DOOMGENERIC_RESX * 2,
                              DOOMGENERIC_RESY * 2,
                              SDL_WINDOW_SHOWN);

    if (!window) {
        fprintf(stderr, "SDL_CreateWindow failed: %s\n", SDL_GetError());
        exit(1);
    }

    renderer = SDL_CreateRenderer(window, -1, SDL_RENDERER_ACCELERATED);

    texture = SDL_CreateTexture(renderer,
                                SDL_PIXELFORMAT_RGB888,
                                SDL_TEXTUREACCESS_TARGET,
                                DOOMGENERIC_RESX,
                                DOOMGENERIC_RESY);

    printf("✓ SDL window created (320x200 scaled to 640x400)\n");

    /* Connect to socket server */
    printf("Connecting to vector renderer socket...\n");
    if (doom_socket_connect() < 0) {
        fprintf(stderr, "WARNING: Socket connection failed\n");
        fprintf(stderr, "Continuing with SDL window only.\n");
        fprintf(stderr, "Start standalone renderer first if you want vectors.\n\n");
    } else {
        printf("✓ Connected to vector renderer!\n");
    }

    printf("\nDual output initialized!\n");
    printf("- SDL window shows original DOOM graphics\n");
    printf("- Socket sends vectors to standalone renderer\n\n");
}

/**
 * DG_DrawFrame() - Render to SDL AND send vectors
 */
void DG_DrawFrame(void) {
    /* 1. Update SDL window with pixel buffer */
    SDL_UpdateTexture(texture, NULL, DG_ScreenBuffer, DOOMGENERIC_RESX * sizeof(uint32_t));
    SDL_RenderClear(renderer);
    SDL_RenderCopy(renderer, texture, NULL, NULL);
    SDL_RenderPresent(renderer);

    /* 2. Send vectors to socket */
    size_t json_len;
    char* json_data = extract_vectors_to_json(&json_len);

    /* Don't exit if socket fails - keep SDL window running */
    doom_socket_send_frame(json_data, json_len);

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

    /* Poll SDL events for keyboard */
    SDL_Event e;
    while (SDL_PollEvent(&e)) {
        if (e.type == SDL_QUIT) {
            exit(0);
        }
        else if (e.type == SDL_KEYDOWN) {
            unsigned char doom_key = sdl_to_doom_key(e.key.keysym.sym);
            enqueue_key(1, doom_key);
        }
        else if (e.type == SDL_KEYUP) {
            unsigned char doom_key = sdl_to_doom_key(e.key.keysym.sym);
            enqueue_key(0, doom_key);
        }
    }

    /* Also poll socket for keyboard (if standalone renderer sends keys) */
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
    SDL_Delay(ms);
}

/**
 * DG_GetTicksMs() - Get milliseconds since init
 */
uint32_t DG_GetTicksMs(void) {
    return SDL_GetTicks();
}

/**
 * DG_GetKey() - Get keyboard input
 */
int DG_GetKey(int* pressed, unsigned char* key) {
    return dequeue_key(pressed, key);
}

/**
 * DG_SetWindowTitle() - Set SDL window title
 */
void DG_SetWindowTitle(const char* title) {
    if (window) {
        SDL_SetWindowTitle(window, title);
    }
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
