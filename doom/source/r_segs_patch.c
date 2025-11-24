/**
 * r_segs_patch.c
 *
 * Patch code to add to r_segs.c for wall extraction.
 *
 * ADD THIS TO THE END OF R_StoreWallRange() function in r_segs.c:
 *
 * After line ~700 (before the closing brace of R_StoreWallRange):
 */

#ifdef KICAD_VECTOR_EXTRACTION
    /* Extract wall segment for KiCad rendering */
    {
        extern void DV_AddWall(int x1, int y1, int x2, int y2, int distance, int height);

        /* Calculate screen coordinates */
        int screen_x1 = rw_x;
        int screen_x2 = rw_stopx;
        int screen_y = viewheight / 2;  /* Middle of screen */

        /* Calculate distance (using rw_distance from BSP traversal) */
        extern fixed_t rw_distance;
        int dist = rw_distance >> FRACBITS;  /* Convert from fixed point */

        /* Calculate wall height based on scale */
        extern fixed_t rw_scale;
        int height = (rw_scale >> FRACBITS) / 2;

        DV_AddWall(screen_x1, screen_y, screen_x2, screen_y, dist, height);
    }
#endif
