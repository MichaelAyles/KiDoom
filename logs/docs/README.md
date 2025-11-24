# Documentation Timeline

This directory contains all documentation files created during the development of KiDoom, organized chronologically to tell the story of how we got here.

## File Naming Convention

Files are named: `NN_YYYYMMDD_HHMMSS_ORIGINAL_NAME.md`

Where:
- `NN` = Sequential number showing order of creation
- `YYYYMMDD_HHMMSS` = Timestamp when file was last modified
- `ORIGINAL_NAME` = Original filename

## The Story

### Phase 1: Initial Implementation (Files 01-04)
- Planning and architecture
- Phase 2 completion (Python KiCad plugin)
- Phase 3 integration setup
- Quick start guides

### Phase 2: Debugging Crashes (Files 05-11)
- Plugin debugging on macOS
- Manual load testing
- Crash fix attempts (V1, V2, V3)
- Threading fixes for macOS compatibility

### Phase 3: Isolation Testing (Files 12-15)
- Smiley face test plugin (simpler test case)
- Integration of test into main plugin
- Quick test procedures

### Phase 4: Standalone Development (Files 16-18)
- Standalone vector renderer (testing without KiCad)
- Implementation details
- Test procedures

## Key Insights

Each document represents a step in solving the macOS threading challenges and improving the vector extraction system. Reading them in order shows:

1. **The Problem**: KiCad crashes on macOS with background threads
2. **The Attempts**: Multiple threading/timer/queue approaches (V1, V2, V3)
3. **The Isolation**: Creating simpler test cases (smiley face)
4. **The Solution**: Standalone renderer + improved vector extraction

## Current State

The project now works with:
- **Standalone Renderer**: Pure Python pygame renderer for testing
- **Dual Output**: SDL window (original graphics) + vector socket
- **Direct Vector Extraction**: Reading from DOOM's internal drawsegs[] and vissprites[] arrays
