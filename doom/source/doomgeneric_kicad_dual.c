/**
 * doomgeneric_kicad_dual.c - Version 3 (DUAL MODE: SDL + Vectors)
 *
 * DOOM platform implementation for KiCad PCB rendering.
 *
 * This version extracts EVERYTHING from DOOM's screen-space rendering:
 * - Walls: ceilingclip[] / floorclip[] arrays (actual screen coordinates)
 * - Sprites: vissprites[] array (with perspective scaling)
 * - Floors/Ceilings: visplanes[] array (horizontal surfaces)
 * - HUD: Weapon sprites
 *
 * DUAL MODE: Shows SDL window AND sends vectors to Python renderer
 *
 * All data is POST-PROJECTION screen-space coordinates!
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
#include "r_plane.h"   /* For visplanes */
#include "p_pspr.h"    /* For weapon sprites */
#include "doomstat.h"  /* For players[] array */
#include "m_fixed.h"   /* For FixedMul */

/* Declare external DOOM variables */
extern drawseg_t drawsegs[MAXDRAWSEGS];
extern drawseg_t* ds_p;

extern vissprite_t vissprites[MAXVISSPRITES];
extern vissprite_t* vissprite_p;

/* Visplanes extraction disabled for now - complex to access */
/* extern visplane_t* visplanes[MAXVISPLANES]; */
/* extern visplane_t* lastvisplane; */

extern short ceilingclip[SCREENWIDTH];
extern short floorclip[SCREENWIDTH];

extern int viewheight;
extern int viewwidth;

extern player_t players[MAXPLAYERS];
extern int consoleplayer;

extern fixed_t centeryfrac;

/* SDL state */
static SDL_Window* g_sdl_window = NULL;
static SDL_Renderer* g_sdl_renderer = NULL;
static SDL_Texture* g_sdl_texture = NULL;

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
 * Helper: Convert SDL key to DOOM key.
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
        case SDLK_LALT:
        case SDLK_RALT: return KEY_LALT;
        case SDLK_F2: return KEY_F2;
        case SDLK_F3: return KEY_F3;
        case SDLK_F4: return KEY_F4;
        case SDLK_F5: return KEY_F5;
        case SDLK_F6: return KEY_F6;
        case SDLK_F7: return KEY_F7;
        case SDLK_F8: return KEY_F8;
        case SDLK_F9: return KEY_F9;
        case SDLK_F10: return KEY_F10;
        case SDLK_F11: return KEY_F11;
        case SDLK_EQUALS:
        case SDLK_PLUS: return KEY_EQUALS;
        case SDLK_MINUS: return KEY_MINUS;
        default:
            if (key >= SDLK_a && key <= SDLK_z) {
                return key;  /* a-z */
            }
            if (key >= SDLK_0 && key <= SDLK_9) {
                return key;  /* 0-9 */
            }
            return 0;
    }
}

/**
 * Extract complete screen-space vectors to JSON.
 *
 * Extracts:
 * 1. Walls (using ceilingclip/floorclip - actual rendered coordinates)
 * 2. Sprites (perspective-scaled entities)
 * 3. Planes (floors/ceilings)
 * 4. Weapon sprite
 */
static char* extract_vectors_to_json(size_t* out_len) {
    static char json_buf[262144];  /* 256KB buffer for more data */
    int offset = 0;

    /* Start JSON */
    offset += snprintf(json_buf + offset, sizeof(json_buf) - offset,
                      "{\"frame\":%d,\"walls\":[", g_frame_count);

    /* ========================================================================
     * WALLS - Extract from drawsegs using ceilingclip/floorclip arrays
     * ======================================================================== */
    int wall_count = ds_p - drawsegs;
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

        /* Get sector information */
        seg_t* seg = ds->curline;
        if (seg == NULL || seg->frontsector == NULL) {
            continue;  /* Skip segments without valid sector data */
        }

        sector_t* sector = seg->frontsector;

        /* DOOM's scale is in fixed point - DON'T shift by FRACBITS yet! */
        fixed_t scale1 = ds->scale1;
        fixed_t scale2 = ds->scale2;

        if (scale1 <= 0) scale1 = 1;
        if (scale2 <= 0) scale2 = 1;

        /* Calculate distance for depth sorting
         * In DOOM: scale is inversely proportional to distance
         * Larger scale = closer, smaller scale = farther
         * We normalize to 0-999 range where 0=closest, 999=farthest
         *
         * Scale range is typically 0x400 (very far) to 0x40000 (very close)
         * We invert it: distance = (MAX_SCALE - scale) / SCALE_DIVISOR
         */
        int distance;
        if (scale1 > 0x20000) {  /* Very close */
            distance = 0;
        } else if (scale1 < 0x800) {  /* Very far */
            distance = 999;
        } else {
            /* Map scale 0x800-0x20000 to distance 999-0 */
            /* Invert: higher scale = lower distance */
            distance = 999 - ((scale1 - 0x800) * 999) / (0x20000 - 0x800);
        }
        if (distance < 0) distance = 0;
        if (distance > 999) distance = 999;

        /* Get sector ceiling and floor heights (keep as fixed point) */
        fixed_t ceiling_height = sector->ceilingheight;
        fixed_t floor_height = sector->floorheight;

        /* DOOM's actual projection formula:
         * screen_y = centeryfrac - FixedMul(height_in_world, scale)
         * where centeryfrac is the center of the screen in fixed point
         */

        /* Calculate top of wall (ceiling) at both ends */
        fixed_t fy1_top = centeryfrac - FixedMul(ceiling_height, scale1);
        fixed_t fy2_top = centeryfrac - FixedMul(ceiling_height, scale2);

        /* Calculate bottom of wall (floor) at both ends */
        fixed_t fy1_bottom = centeryfrac - FixedMul(floor_height, scale1);
        fixed_t fy2_bottom = centeryfrac - FixedMul(floor_height, scale2);

        /* Convert to integer screen coordinates */
        int y1_top = fy1_top >> FRACBITS;
        int y1_bottom = fy1_bottom >> FRACBITS;
        int y2_top = fy2_top >> FRACBITS;
        int y2_bottom = fy2_bottom >> FRACBITS;

        /* Final clamping */
        if (y1_top < 0) y1_top = 0;
        if (y1_top >= viewheight) y1_top = viewheight - 1;
        if (y1_bottom < 0) y1_bottom = 0;
        if (y1_bottom >= viewheight) y1_bottom = viewheight - 1;
        if (y2_top < 0) y2_top = 0;
        if (y2_top >= viewheight) y2_top = viewheight - 1;
        if (y2_bottom < 0) y2_bottom = 0;
        if (y2_bottom >= viewheight) y2_bottom = viewheight - 1;

        /* Debug first frame */
        if (g_frame_count == 1 && wall_output == 0) {
            printf("DEBUG: First wall: scale[0x%x,0x%x] dist:%d y1[%d,%d] y2[%d,%d]\n",
                   scale1, scale2, distance, y1_top, y1_bottom, y2_top, y2_bottom);
        }

        if (wall_output > 0) {
            offset += snprintf(json_buf + offset, sizeof(json_buf) - offset, ",");
        }

        /* Output wall quad with ACTUAL screen coordinates */
        /* Format: [x1, y1_top, y1_bottom, x2, y2_top, y2_bottom, distance] */
        offset += snprintf(json_buf + offset, sizeof(json_buf) - offset,
                          "[%d,%d,%d,%d,%d,%d,%d]",
                          x1, y1_top, y1_bottom, x2, y2_top, y2_bottom, distance);
        wall_output++;
    }

    offset += snprintf(json_buf + offset, sizeof(json_buf) - offset, "],\"entities\":[");

    /* ========================================================================
     * SPRITES/ENTITIES - Already screen-projected with perspective
     * ======================================================================== */
    int sprite_count = vissprite_p - vissprites;

    for (int i = 0; i < sprite_count && i < MAXVISSPRITES; i++) {
        vissprite_t* vis = &vissprites[i];

        /* Screen position */
        int x1 = vis->x1;
        int x2 = vis->x2;

        if (x1 < 0 || x2 < 0 || x1 >= viewwidth || x2 >= viewwidth) {
            continue;
        }

        int x = (x1 + x2) / 2;

        /* Get sprite scale (in fixed point) */
        fixed_t sprite_scale = vis->scale;
        if (sprite_scale <= 0) sprite_scale = 1;

        /* Calculate distance using same method as walls */
        int distance;
        if (sprite_scale > 0x20000) {  /* Very close */
            distance = 0;
        } else if (sprite_scale < 0x800) {  /* Very far */
            distance = 999;
        } else {
            /* Map scale 0x800-0x20000 to distance 999-0 */
            distance = 999 - ((sprite_scale - 0x800) * 999) / (0x20000 - 0x800);
        }
        if (distance < 0) distance = 0;
        if (distance > 999) distance = 999;

        /* Project sprite to screen coordinates using DOOM's formula
         * gzt is the Z position of the sprite's top
         * gz is the Z position of the sprite's bottom
         * DOOM already calculates these for us!
         */
        fixed_t gzt = vis->gzt;  /* Top of sprite in world Z */
        fixed_t gz = vis->gz;     /* Bottom of sprite in world Z */

        /* Calculate screen Y coordinates using DOOM's projection */
        fixed_t fy_top = centeryfrac - FixedMul(gzt, sprite_scale);
        fixed_t fy_bottom = centeryfrac - FixedMul(gz, sprite_scale);

        /* Convert to integer screen coordinates */
        int y_top = fy_top >> FRACBITS;
        int y_bottom = fy_bottom >> FRACBITS;

        /* Clamp */
        if (y_top < 0) y_top = 0;
        if (y_top >= viewheight) y_top = viewheight - 1;
        if (y_bottom < 0) y_bottom = 0;
        if (y_bottom >= viewheight) y_bottom = viewheight - 1;

        int sprite_height = y_bottom - y_top;
        if (sprite_height < 5) sprite_height = 5;

        int type = i % 8;

        if (i > 0) {
            offset += snprintf(json_buf + offset, sizeof(json_buf) - offset, ",");
        }

        offset += snprintf(json_buf + offset, sizeof(json_buf) - offset,
                          "{\"x\":%d,\"y_top\":%d,\"y_bottom\":%d,\"height\":%d,\"type\":%d,\"distance\":%d}",
                          x, y_top, y_bottom, sprite_height, type, distance);
    }

    /* No planes needed - walls define the visible space naturally */
    offset += snprintf(json_buf + offset, sizeof(json_buf) - offset, "],\"weapon\":");

    /* ========================================================================
     * WEAPON SPRITE (HUD)
     * ======================================================================== */
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

void DG_Init(void) {
    printf("\n");
    printf("========================================\n");
    printf("  DOOM DUAL MODE V3\n");
    printf("  (SDL Window + Vector Extraction)\n");
    printf("========================================\n");
    printf("\n");

    g_start_time_ms = get_time_ms();

    /* Initialize SDL */
    printf("Initializing SDL...\n");
    if (SDL_Init(SDL_INIT_VIDEO) < 0) {
        fprintf(stderr, "ERROR: SDL_Init failed: %s\n", SDL_GetError());
        exit(1);
    }

    /* Set rendering hints for pixel-perfect display */
    SDL_SetHint(SDL_HINT_RENDER_SCALE_QUALITY, "0");  /* Nearest neighbor (no filtering) */
    SDL_SetHint(SDL_HINT_RENDER_VSYNC, "1");          /* Enable vsync */

    /* Create SDL window (positioned below Python renderer)
     * Native 320x200 resolution, no scaling
     */
    g_sdl_window = SDL_CreateWindow("DOOM (SDL)",
                                     0,              /* X position */
                                     420,            /* Y position (below 400px renderer) */
                                     320,            /* Native DOOM width */
                                     200,            /* Native DOOM height */
                                     SDL_WINDOW_SHOWN);
    if (!g_sdl_window) {
        fprintf(stderr, "ERROR: SDL_CreateWindow failed: %s\n", SDL_GetError());
        exit(1);
    }

    /* Create SDL renderer - use software for compatibility */
    g_sdl_renderer = SDL_CreateRenderer(g_sdl_window, -1, SDL_RENDERER_SOFTWARE);
    if (!g_sdl_renderer) {
        fprintf(stderr, "ERROR: SDL_CreateRenderer failed: %s\n", SDL_GetError());
        exit(1);
    }

    /* Set logical size to match framebuffer for 1:1 pixel mapping */
    SDL_RenderSetLogicalSize(g_sdl_renderer, 320, 200);

    /* Create texture for framebuffer
     * IMPORTANT: Texture must be 320x200 (DOOM's native resolution)
     * Using ARGB8888 format to match DOOM's framebuffer layout
     */
    g_sdl_texture = SDL_CreateTexture(g_sdl_renderer,
                                      SDL_PIXELFORMAT_ARGB8888,  /* Match doomgeneric format */
                                      SDL_TEXTUREACCESS_STREAMING,
                                      320,  /* DOOM native width */
                                      200); /* DOOM native height */
    if (!g_sdl_texture) {
        fprintf(stderr, "ERROR: SDL_CreateTexture failed: %s\n", SDL_GetError());
        exit(1);
    }

    printf("✓ SDL texture created: 320x200, ARGB8888\n");

    SDL_RenderClear(g_sdl_renderer);
    SDL_RenderPresent(g_sdl_renderer);

    printf("✓ SDL initialized (320x200 native resolution at 0,420)\n");

    /* Connect to vector socket */
    printf("Connecting to socket server...\n");
    if (doom_socket_connect() < 0) {
        fprintf(stderr, "\nERROR: Failed to connect!\n");
        fprintf(stderr, "Make sure standalone renderer is running.\n\n");
        exit(1);
    }

    printf("\n✓ Dual Mode Active:\n");
    printf("  - SDL Window: 320x200 (native, no scaling)\n");
    printf("  - Vector extraction: V3 (screen-space)\n");
    printf("  - Walls: projection + sector heights\n");
    printf("  - Sprites: proper scaling by distance\n\n");
}

void DG_DrawFrame(void) {
    size_t json_len;
    char* json_data;

    /* Send vectors to Python renderer */
    json_data = extract_vectors_to_json(&json_len);
    if (doom_socket_send_frame(json_data, json_len) < 0) {
        fprintf(stderr, "ERROR: Failed to send frame\n");
        exit(1);
    }

    /* Update SDL window with framebuffer using proper stride */
    int pitch = 320 * 4;  /* 320 pixels * 4 bytes per pixel (RGB888) */

    if (SDL_UpdateTexture(g_sdl_texture, NULL, DG_ScreenBuffer, pitch) < 0) {
        fprintf(stderr, "ERROR: SDL_UpdateTexture failed: %s\n", SDL_GetError());
    }

    if (SDL_RenderClear(g_sdl_renderer) < 0) {
        fprintf(stderr, "ERROR: SDL_RenderClear failed: %s\n", SDL_GetError());
    }

    if (SDL_RenderCopy(g_sdl_renderer, g_sdl_texture, NULL, NULL) < 0) {
        fprintf(stderr, "ERROR: SDL_RenderCopy failed: %s\n", SDL_GetError());
    }

    SDL_RenderPresent(g_sdl_renderer);

    /* Handle SDL events (including keyboard input) */
    SDL_Event event;
    while (SDL_PollEvent(&event)) {
        if (event.type == SDL_QUIT) {
            printf("SDL quit requested\n");
            exit(0);
        } else if (event.type == SDL_KEYDOWN) {
            unsigned char doom_key = sdl_to_doom_key(event.key.keysym.sym);
            if (doom_key != 0) {
                enqueue_key(1, doom_key);  /* Key pressed */
            }
        } else if (event.type == SDL_KEYUP) {
            unsigned char doom_key = sdl_to_doom_key(event.key.keysym.sym);
            if (doom_key != 0) {
                enqueue_key(0, doom_key);  /* Key released */
            }
        }
    }

    g_frame_count++;

    if (g_frame_count % 100 == 0) {
        uint32_t elapsed_ms = get_time_ms() - g_start_time_ms;
        float fps = (g_frame_count * 1000.0f) / elapsed_ms;

        int wall_count = ds_p - drawsegs;
        int sprite_count = vissprite_p - vissprites;

        printf("Frame %d: %.1f FPS | Walls: %d | Sprites: %d\n",
               g_frame_count, fps, wall_count, sprite_count);
    }

    /* Receive key events from Python renderer via socket */
    int pressed;
    unsigned char key;
    while (doom_socket_recv_key(&pressed, &key) > 0) {
        enqueue_key(pressed, key);
    }
}

void DG_SleepMs(uint32_t ms) {
    SDL_Delay(ms);
}

uint32_t DG_GetTicksMs(void) {
    return SDL_GetTicks();
}

int DG_GetKey(int* pressed, unsigned char* key) {
    return dequeue_key(pressed, key);
}

void DG_SetWindowTitle(const char* title) {
    /* Not applicable */
}

int main(int argc, char **argv) {
    doomgeneric_Create(argc, argv);

    while (1) {
        doomgeneric_Tick();
    }

    return 0;
}
