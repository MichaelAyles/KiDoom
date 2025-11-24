# KiDoom Plugin Loading Instructions

## Current Status

I've fixed the plugin loading issue. The problem was that KiCad needs plugin files directly in the `plugins/` directory, not in subdirectories.

## What I Fixed

1. **Created main plugin file:** `kidoom_plugin.py` in the plugins directory
2. **Fixed icon loading:** Made icon optional (won't fail if missing)
3. **Added debug output:** Shows loading progress in KiCad console
4. **Updated plugin name:** Now shows as "KiDoom - DOOM on PCB"

## File Structure

```
~/Documents/KiCad/9.0/scripting/plugins/
├── kidoom_plugin.py              ← Main plugin file (loads on startup)
├── test_plugin.py                ← Simple test plugin (for verification)
└── kicad_doom_plugin/            ← Plugin modules (imported by kidoom_plugin.py)
    ├── doom_plugin_action.py
    ├── pcb_renderer.py
    ├── doom_bridge.py
    ├── etc...
```

## How to Load the Plugin

### Method 1: Restart KiCad (Recommended)

1. **Completely quit KiCad** (Cmd+Q on macOS)
2. **Reopen KiCad PCBnew**
3. **Open any PCB** (or create new one)
4. **Check the console output:**
   - Tools → Scripting Console
   - You should see:
     ```
     ======================================================================
     KiDoom plugin loading...
     ======================================================================
     Plugin directory: /Users/tribune/Documents/KiCad/9.0/scripting/plugins/kicad_doom_plugin
     Added to sys.path
     Importing DoomKiCadPlugin...
     Registering plugin with KiCad...
     ✓ KiDoom plugin registered successfully!
       Look for 'KiDoom - DOOM on PCB' in Tools → External Plugins
     ======================================================================
     ```

5. **Look for the plugin:**
   - Tools → External Plugins → **KiDoom - DOOM on PCB**

### Method 2: Manual Loading (If Auto-load Fails)

If the plugin doesn't auto-load, manually load it in the scripting console:

1. Tools → Scripting Console
2. Run:
   ```python
   exec(open('/Users/tribune/Documents/KiCad/9.0/scripting/plugins/kidoom_plugin.py').read())
   ```

3. You should see the loading output, then the plugin will appear in the menu.

### Method 3: Test Plugin First

To verify plugin loading works at all:

1. Tools → Scripting Console
2. Run:
   ```python
   exec(open('/Users/tribune/Documents/KiCad/9.0/scripting/plugins/test_plugin.py').read())
   ```

3. Look for "Test Plugin" in Tools → External Plugins
4. Click it - should print "TEST PLUGIN RUNNING!" in console
5. If this works, KiDoom should work too

## Troubleshooting

### Plugin Still Not Showing Up

**Check console for errors:**
1. Tools → Scripting Console
2. Look for error messages when KiCad starts
3. Common issues:
   - Import errors (missing dependencies)
   - Python syntax errors
   - Permission issues

**Verify files are in place:**
```bash
ls -la ~/Documents/KiCad/9.0/scripting/plugins/kidoom_plugin.py
ls -la ~/Documents/KiCad/9.0/scripting/plugins/kicad_doom_plugin/
```

**Check Python path:**
In KiCad console:
```python
import sys
print('\n'.join(sys.path))
```

### "No module named 'pynput'" Error

If you see this in the console:
```bash
pip3 install pynput
```

Then restart KiCad.

### Plugin Loads But Doesn't Appear in Menu

**Force refresh plugins:**
In KiCad console:
```python
import pcbnew
pcbnew.Refresh()
```

Or restart KiCad completely.

### Check What Plugins Are Registered

In KiCad console:
```python
import pcbnew

# Get all registered action plugins
from pcbnew import GetActionPlugins

plugins = GetActionPlugins()
print(f"\nFound {len(plugins)} plugins:")
for p in plugins:
    print(f"  - {p.GetName()}")
```

Should show "KiDoom - DOOM on PCB" in the list.

## Expected Console Output on Startup

When KiCad starts with the plugin installed, you should see:

```
======================================================================
KiDoom plugin loading...
======================================================================
Plugin directory: /Users/tribune/Documents/KiCad/9.0/scripting/plugins/kicad_doom_plugin
Added to sys.path
Importing DoomKiCadPlugin...
Registering plugin with KiCad...
✓ KiDoom plugin registered successfully!
  Look for 'KiDoom - DOOM on PCB' in Tools → External Plugins
======================================================================
```

If you see this, the plugin is loaded and should appear in the menu.

## Next Steps After Plugin Loads

1. **Open test PCB:**
   ```bash
   open ~/Desktop/KiDoom/kicad_source/blank_project/blank_project.kicad_pcb
   ```

2. **Optimize settings:**
   - View → Show Grid: OFF
   - View → Ratsnest: OFF
   - Preferences → Graphics → Antialiasing: Fast

3. **Click the plugin:**
   - Tools → External Plugins → KiDoom - DOOM on PCB
   - Should launch DOOM and start rendering

4. **Watch the console:**
   - Will show startup messages, socket connection, frame rendering

## Files Modified

I updated these files to fix the loading issue:

1. **`kidoom_plugin.py`** - Main loader with debug output
2. **`doom_plugin_action.py`** - Fixed icon loading (line 49-52)
3. **`test_plugin.py`** - Added for verification

## Testing Checklist

- [ ] Restart KiCad completely (Cmd+Q then reopen)
- [ ] Open Tools → Scripting Console
- [ ] Look for "KiDoom plugin loading..." message
- [ ] Check Tools → External Plugins menu
- [ ] See "KiDoom - DOOM on PCB" in list
- [ ] If not, try Method 2 (manual loading)
- [ ] If still fails, check console for specific error

---

**Current Status:** Plugin files updated and ready for testing.

**Next Action:** Restart KiCad and check if plugin appears in menu.

If you still have issues after restarting, please share:
1. The console output from KiCad (Tools → Scripting Console)
2. Any error messages you see
3. Whether test_plugin.py works
