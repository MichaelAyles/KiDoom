/**
 * doom_vectors.h
 *
 * Header for vector extraction system.
 */

#ifndef DOOM_VECTORS_H
#define DOOM_VECTORS_H

#include <stddef.h>

/* Vector data structures */
typedef struct {
    int x1, y1;      /* Start point */
    int x2, y2;      /* End point */
    int distance;    /* Distance from player (for depth sorting) */
    int height;      /* Wall height (for visual interest) */
} wall_segment_t;

typedef struct {
    int x, y;        /* Screen position */
    int type;        /* Entity type (player=0, enemy=1, item=2, etc.) */
    int angle;       /* Facing direction (degrees) */
    int distance;    /* Distance from player */
} entity_t;

/* API functions */
void DV_BeginFrame(void);
void DV_AddWall(int x1, int y1, int x2, int y2, int distance, int height);
void DV_AddEntity(int x, int y, int type, int angle, int distance);
char* DV_GenerateJSON(size_t* out_len);
void DV_GetStats(int* wall_count, int* entity_count);

#endif /* DOOM_VECTORS_H */
