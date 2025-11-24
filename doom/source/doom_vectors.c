/**
 * doom_vectors.c
 *
 * Proper vector extraction from DOOM's rendering pipeline.
 *
 * Instead of scanning the pixel buffer for edges (slow, inaccurate),
 * this hooks into DOOM's actual rendering functions to extract the
 * real wall segments and sprite positions BEFORE rasterization.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#include "doom_vectors.h"

/* Maximum vectors to track per frame */
#define MAX_WALLS 500
#define MAX_ENTITIES 128

/* Storage for extracted vectors */
static wall_segment_t g_walls[MAX_WALLS];
static int g_wall_count = 0;

static entity_t g_entities[MAX_ENTITIES];
static int g_entity_count = 0;

/* Frame counter */
static int g_frame_number = 0;

/**
 * Reset vector storage for new frame.
 * Called at start of each frame before rendering.
 */
void DV_BeginFrame(void) {
    g_wall_count = 0;
    g_entity_count = 0;
    g_frame_number++;
}

/**
 * Add a wall segment.
 * Called during wall rendering phase.
 */
void DV_AddWall(int x1, int y1, int x2, int y2, int distance, int height) {
    if (g_wall_count >= MAX_WALLS) {
        return;  /* At capacity */
    }

    wall_segment_t* wall = &g_walls[g_wall_count++];
    wall->x1 = x1;
    wall->y1 = y1;
    wall->x2 = x2;
    wall->y2 = y2;
    wall->distance = distance;
    wall->height = height;
}

/**
 * Add an entity (sprite).
 * Called during sprite rendering phase.
 */
void DV_AddEntity(int x, int y, int type, int angle, int distance) {
    if (g_entity_count >= MAX_ENTITIES) {
        return;  /* At capacity */
    }

    entity_t* entity = &g_entities[g_entity_count++];
    entity->x = x;
    entity->y = y;
    entity->type = type;
    entity->angle = angle;
    entity->distance = distance;
}

/**
 * Convert extracted vectors to JSON.
 * Called at end of frame to generate data for socket transmission.
 */
char* DV_GenerateJSON(size_t* out_len) {
    static char json_buf[131072];  /* 128KB buffer */
    int offset = 0;

    /* Start JSON object */
    offset += snprintf(json_buf + offset, sizeof(json_buf) - offset,
                      "{\"frame\":%d,\"walls\":[", g_frame_number);

    /* Add walls */
    for (int i = 0; i < g_wall_count; i++) {
        wall_segment_t* wall = &g_walls[i];

        if (i > 0) {
            offset += snprintf(json_buf + offset, sizeof(json_buf) - offset, ",");
        }

        offset += snprintf(json_buf + offset, sizeof(json_buf) - offset,
                          "{\"x1\":%d,\"y1\":%d,\"x2\":%d,\"y2\":%d,\"distance\":%d,\"height\":%d}",
                          wall->x1, wall->y1, wall->x2, wall->y2,
                          wall->distance, wall->height);
    }

    offset += snprintf(json_buf + offset, sizeof(json_buf) - offset, "],\"entities\":[");

    /* Add entities */
    for (int i = 0; i < g_entity_count; i++) {
        entity_t* entity = &g_entities[i];

        if (i > 0) {
            offset += snprintf(json_buf + offset, sizeof(json_buf) - offset, ",");
        }

        offset += snprintf(json_buf + offset, sizeof(json_buf) - offset,
                          "{\"x\":%d,\"y\":%d,\"type\":%d,\"angle\":%d,\"distance\":%d}",
                          entity->x, entity->y, entity->type,
                          entity->angle, entity->distance);
    }

    /* Close JSON */
    offset += snprintf(json_buf + offset, sizeof(json_buf) - offset, "]}");

    *out_len = offset;
    return json_buf;
}

/**
 * Get statistics about current frame.
 */
void DV_GetStats(int* wall_count, int* entity_count) {
    *wall_count = g_wall_count;
    *entity_count = g_entity_count;
}
