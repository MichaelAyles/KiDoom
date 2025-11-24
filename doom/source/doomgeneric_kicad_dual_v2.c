/**
 * doomgeneric_kicad_dual.c - Dual Mode (SDL + Vector Extraction)
 *
 * Based on working doomgeneric_sdl.c with vector extraction added
 */

#include "doomgeneric.h"
#include "doomkeys.h"
#include "doom_socket.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/time.h>
#include <unistd.h>
#include <SDL.h>

/* Import DOOM's internal rendering structures for vector extraction */
#include "r_defs.h"
#include "r_bsp.h"
#include "r_state.h"
#include "r_things.h"
#include "r_plane.h"
#include "p_pspr.h"
#include "doomstat.h"
#include "m_fixed.h"

/* Declare external DOOM variables for vector extraction */
extern drawseg_t drawsegs[MAXDRAWSEGS];
extern drawseg_t* ds_p;
extern vissprite_t vissprites[MAXVISSPRITES];
extern vissprite_t* vissprite_p;
extern short ceilingclip[SCREENWIDTH];
extern short floorclip[SCREENWIDTH];
extern int viewheight;
extern int viewwidth;
extern player_t players[MAXPLAYERS];
extern int consoleplayer;
extern fixed_t centeryfrac;

/* SDL state */
SDL_Window* window = NULL;
SDL_Renderer* renderer = NULL;
SDL_Texture* texture = NULL;

/* Internal state */
static uint32_t g_start_time_ms = 0;
static int g_frame_count = 0;

/* Keyboard queue */
#define KEYQUEUE_SIZE 16
static unsigned short s_KeyQueue[KEYQUEUE_SIZE];
static unsigned int s_KeyQueueWriteIndex = 0;
static unsigned int s_KeyQueueReadIndex = 0;

static uint32_t get_time_ms(void) {
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return (tv.tv_sec * 1000) + (tv.tv_usec / 1000);
}

static unsigned char convertToDoomKey(unsigned int key){
  switch (key)
    {
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
    default: return tolower(key);
    }
}

static void addKeyToQueue(int pressed, unsigned int keyCode){
  unsigned char key = convertToDoomKey(keyCode);
  unsigned short keyData = (pressed << 8) | key;
  s_KeyQueue[s_KeyQueueWriteIndex] = keyData;
  s_KeyQueueWriteIndex++;
  s_KeyQueueWriteIndex %= KEYQUEUE_SIZE;
}

static void handleKeyInput(){
  SDL_Event e;
  while (SDL_PollEvent(&e)){
    if (e.type == SDL_QUIT){
      puts("Quit requested");
      atexit(SDL_Quit);
      exit(1);
    }
    if (e.type == SDL_KEYDOWN) {
      addKeyToQueue(1, e.key.keysym.sym);
    } else if (e.type == SDL_KEYUP) {
      addKeyToQueue(0, e.key.keysym.sym);
    }
  }
}

/* Vector extraction function (from our working code) */
static char* extract_vectors_to_json(size_t* out_len) {
    static char json_buf[262144];
    int offset = 0;

    offset += snprintf(json_buf + offset, sizeof(json_buf) - offset,
                      "{\"frame\":%d,\"walls\":[", g_frame_count);

    /* Extract walls */
    int wall_count = ds_p - drawsegs;
    int wall_output = 0;

    for (int i = 0; i < wall_count && i < MAXDRAWSEGS; i++) {
        drawseg_t* ds = &drawsegs[i];
        int x1 = ds->x1;
        int x2 = ds->x2;

        if (x1 < 0 || x2 < 0 || x1 >= viewwidth || x2 >= viewwidth || x1 > x2) {
            continue;
        }

        seg_t* seg = ds->curline;
        if (seg == NULL || seg->frontsector == NULL) {
            continue;
        }

        sector_t* sector = seg->frontsector;
        fixed_t scale1 = ds->scale1;
        fixed_t scale2 = ds->scale2;

        if (scale1 <= 0) scale1 = 1;
        if (scale2 <= 0) scale2 = 1;

        int distance;
        if (scale1 > 0x20000) {
            distance = 0;
        } else if (scale1 < 0x800) {
            distance = 999;
        } else {
            distance = 999 - ((scale1 - 0x800) * 999) / (0x20000 - 0x800);
        }
        if (distance < 0) distance = 0;
        if (distance > 999) distance = 999;

        fixed_t ceiling_height = sector->ceilingheight;
        fixed_t floor_height = sector->floorheight;

        fixed_t fy1_top = centeryfrac - FixedMul(ceiling_height, scale1);
        fixed_t fy2_top = centeryfrac - FixedMul(ceiling_height, scale2);
        fixed_t fy1_bottom = centeryfrac - FixedMul(floor_height, scale1);
        fixed_t fy2_bottom = centeryfrac - FixedMul(floor_height, scale2);

        int y1_top = fy1_top >> FRACBITS;
        int y1_bottom = fy1_bottom >> FRACBITS;
        int y2_top = fy2_top >> FRACBITS;
        int y2_bottom = fy2_bottom >> FRACBITS;

        if (y1_top < 0) y1_top = 0;
        if (y1_top >= viewheight) y1_top = viewheight - 1;
        if (y1_bottom < 0) y1_bottom = 0;
        if (y1_bottom >= viewheight) y1_bottom = viewheight - 1;
        if (y2_top < 0) y2_top = 0;
        if (y2_top >= viewheight) y2_top = viewheight - 1;
        if (y2_bottom < 0) y2_bottom = 0;
        if (y2_bottom >= viewheight) y2_bottom = viewheight - 1;

        if (wall_output > 0) {
            offset += snprintf(json_buf + offset, sizeof(json_buf) - offset, ",");
        }

        offset += snprintf(json_buf + offset, sizeof(json_buf) - offset,
                          "[%d,%d,%d,%d,%d,%d,%d]",
                          x1, y1_top, y1_bottom, x2, y2_top, y2_bottom, distance);
        wall_output++;
    }

    offset += snprintf(json_buf + offset, sizeof(json_buf) - offset, "],\"entities\":[");

    /* Extract sprites */
    int sprite_count = vissprite_p - vissprites;

    for (int i = 0; i < sprite_count && i < MAXVISSPRITES; i++) {
        vissprite_t* vis = &vissprites[i];
        int x1 = vis->x1;
        int x2 = vis->x2;

        if (x1 < 0 || x2 < 0 || x1 >= viewwidth || x2 >= viewwidth) {
            continue;
        }

        int x = (x1 + x2) / 2;
        fixed_t sprite_scale = vis->scale;
        if (sprite_scale <= 0) sprite_scale = 1;

        int distance;
        if (sprite_scale > 0x20000) {
            distance = 0;
        } else if (sprite_scale < 0x800) {
            distance = 999;
        } else {
            distance = 999 - ((sprite_scale - 0x800) * 999) / (0x20000 - 0x800);
        }
        if (distance < 0) distance = 0;
        if (distance > 999) distance = 999;

        fixed_t gzt = vis->gzt;
        fixed_t gz = vis->gz;
        fixed_t fy_top = centeryfrac - FixedMul(gzt, sprite_scale);
        fixed_t fy_bottom = centeryfrac - FixedMul(gz, sprite_scale);

        int y_top = fy_top >> FRACBITS;
        int y_bottom = fy_bottom >> FRACBITS;

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

    offset += snprintf(json_buf + offset, sizeof(json_buf) - offset, "],\"weapon\":");

    /* Weapon sprite */
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

    offset += snprintf(json_buf + offset, sizeof(json_buf) - offset, "}");

    *out_len = offset;
    return json_buf;
}

void DG_Init(){
  printf("\n========================================\n");
  printf("  DOOM DUAL MODE (SDL + Vectors)\n");
  printf("========================================\n\n");

  g_start_time_ms = get_time_ms();

  /* Standard SDL initialization */
  window = SDL_CreateWindow("DOOM (SDL)",
                            0,                    /* X position */
                            420,                  /* Y position (below Python renderer) */
                            DOOMGENERIC_RESX,
                            DOOMGENERIC_RESY,
                            SDL_WINDOW_SHOWN);

  renderer = SDL_CreateRenderer(window, -1, SDL_RENDERER_ACCELERATED);
  SDL_RenderClear(renderer);
  SDL_RenderPresent(renderer);

  texture = SDL_CreateTexture(renderer, SDL_PIXELFORMAT_RGB888, SDL_TEXTUREACCESS_TARGET, DOOMGENERIC_RESX, DOOMGENERIC_RESY);

  printf("✓ SDL initialized: %dx%d\n", DOOMGENERIC_RESX, DOOMGENERIC_RESY);

  /* Connect to vector socket */
  printf("Connecting to socket server...\n");
  if (doom_socket_connect() < 0) {
      fprintf(stderr, "\nERROR: Failed to connect!\n");
      fprintf(stderr, "Make sure standalone renderer is running.\n\n");
      exit(1);
  }

  printf("\n✓ Dual Mode Active\n");
  printf("  - SDL: Standard doomgeneric display\n");
  printf("  - Vectors: Sent to Python renderer\n\n");
}

void DG_DrawFrame()
{
  /* Send vectors to Python renderer */
  size_t json_len;
  char* json_data = extract_vectors_to_json(&json_len);
  if (doom_socket_send_frame(json_data, json_len) < 0) {
      fprintf(stderr, "ERROR: Failed to send frame\n");
      exit(1);
  }

  /* Standard SDL rendering (known to work) */
  SDL_UpdateTexture(texture, NULL, DG_ScreenBuffer, DOOMGENERIC_RESX*sizeof(uint32_t));
  SDL_RenderClear(renderer);
  SDL_RenderCopy(renderer, texture, NULL, NULL);
  SDL_RenderPresent(renderer);

  handleKeyInput();

  g_frame_count++;

  if (g_frame_count % 100 == 0) {
      uint32_t elapsed_ms = get_time_ms() - g_start_time_ms;
      float fps = (g_frame_count * 1000.0f) / elapsed_ms;
      int wall_count = ds_p - drawsegs;
      int sprite_count = vissprite_p - vissprites;
      printf("Frame %d: %.1f FPS | Walls: %d | Sprites: %d\n",
             g_frame_count, fps, wall_count, sprite_count);
  }
}

void DG_SleepMs(uint32_t ms)
{
  SDL_Delay(ms);
}

uint32_t DG_GetTicksMs()
{
  return SDL_GetTicks();
}

int DG_GetKey(int* pressed, unsigned char* doomKey)
{
  if (s_KeyQueueReadIndex == s_KeyQueueWriteIndex){
    return 0;
  }else{
    unsigned short keyData = s_KeyQueue[s_KeyQueueReadIndex];
    s_KeyQueueReadIndex++;
    s_KeyQueueReadIndex %= KEYQUEUE_SIZE;

    *pressed = keyData >> 8;
    *doomKey = keyData & 0xFF;

    return 1;
  }

  return 0;
}

void DG_SetWindowTitle(const char * title)
{
  if (window != NULL){
    SDL_SetWindowTitle(window, title);
  }
}

int main(int argc, char **argv)
{
    doomgeneric_Create(argc, argv);

    for (int i = 0; ; i++)
    {
        doomgeneric_Tick();
    }

    return 0;
}
