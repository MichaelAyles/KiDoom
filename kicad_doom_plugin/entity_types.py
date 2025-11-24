"""
DOOM entity type mappings for footprint selection.

Maps DOOM's MT_* (mobj type) enum values to PCB footprint categories.

Categories:
- COLLECTIBLE: Health, ammo, weapons, powerups -> SOT-23 (small, 3-pin)
- DECORATION: Barrels, bodies, decorative items -> SOIC-8, TSSOP-16 (medium)
- ENEMY: Zombies, demons, monsters -> QFP-64, QFP-100 (complex)

Reference: DOOM source code info.h / info.c for complete MT_* enum
"""

# Footprint categories
CATEGORY_COLLECTIBLE = 0  # Small simple packages
CATEGORY_DECORATION = 1   # Medium flat packages
CATEGORY_ENEMY = 2        # Complex multi-pin packages
CATEGORY_UNKNOWN = 3      # Fallback

# DOOM MT_* enum values (from info.h)
# These are the actual integer values used in DOOM's mobjtype_t enum

MT_PLAYER = 0

# Enemies (20-49)
MT_POSSESSED = 1      # Zombieman
MT_SHOTGUY = 2        # Shotgun guy
MT_VILE = 3           # Arch-vile
MT_FIRE = 4           # Arch-vile fire
MT_UNDEAD = 5         # Revenant
MT_TRACER = 6         # Revenant tracer
MT_SMOKE = 7          # Smoke
MT_FATSO = 8          # Mancubus
MT_FATSHOT = 9        # Mancubus fireball
MT_CHAINGUY = 10      # Chaingunner
MT_TROOP = 11         # Imp
MT_SERGEANT = 12      # Demon
MT_SHADOWS = 13       # Spectre
MT_HEAD = 14          # Cacodemon
MT_BRUISER = 15       # Baron of Hell
MT_BRUISERSHOT = 16   # Baron fireball
MT_KNIGHT = 17        # Hell Knight
MT_SKULL = 18         # Lost Soul
MT_SPIDER = 19        # Spider Mastermind
MT_BABY = 20          # Arachnotron
MT_CYBORG = 21        # Cyberdemon
MT_PAIN = 22          # Pain Elemental

# Projectiles (skipped - rendered as vias, not footprints)
MT_ROCKET = 23
MT_PLASMA = 24
MT_BFG = 25
MT_ARACHPLAZ = 26
MT_PUFF = 27
MT_BLOOD = 28
MT_TFOG = 29
MT_IFOG = 30
MT_TELEPORTMAN = 31
MT_EXTRABFG = 32

# Items - Health & Armor (50-59)
MT_MISC0 = 33   # Armor bonus
MT_MISC1 = 34   # Green armor
MT_MISC2 = 35   # Blue armor
MT_MISC3 = 36   # Mega armor
MT_MISC10 = 37  # Stimpack
MT_MISC11 = 38  # Medikit
MT_MISC12 = 39  # Soul sphere
MT_INV = 40     # Invulnerability
MT_MISC13 = 41  # Berserk

# Items - Powerups (60-69)
MT_INS = 42     # Invisibility
MT_MISC14 = 43  # Radiation suit
MT_MISC15 = 44  # Computer map
MT_MISC16 = 45  # Light amp goggles

# Items - Keys (70-79)
MT_MISC4 = 46   # Blue keycard
MT_MISC5 = 47   # Red keycard
MT_MISC6 = 48   # Yellow keycard
MT_MISC7 = 49   # Yellow skull key
MT_MISC8 = 50   # Red skull key
MT_MISC9 = 51   # Blue skull key

# Items - Ammo (80-89)
MT_CLIP = 52    # Ammo clip
MT_MISC17 = 53  # Box of ammo
MT_MISC18 = 54  # Rocket
MT_MISC19 = 55  # Box of rockets
MT_MISC20 = 56  # Cell charge
MT_MISC21 = 57  # Cell pack
MT_MISC22 = 58  # Shells
MT_MISC23 = 59  # Box of shells
MT_MISC24 = 60  # Backpack

# Weapons (90-99)
MT_MISC25 = 61  # BFG 9000
MT_CHAINGUN = 62  # Chaingun
MT_MISC26 = 63  # Chainsaw
MT_MISC27 = 64  # Rocket launcher
MT_MISC28 = 65  # Plasma rifle
MT_SHOTGUN = 66  # Shotgun
MT_SUPERSHOTGUN = 67  # Super shotgun

# Decorations (100-119)
MT_BARREL = 68        # Exploding barrel
MT_TROOPSHOT = 69     # Imp fireball
MT_HEADSHOT = 70      # Cacodemon fireball
MT_MISC29 = 71        # Green pillar
MT_MISC30 = 72        # Short green pillar
MT_MISC31 = 73        # Tall red pillar
MT_MISC32 = 74        # Short red pillar
MT_MISC33 = 75        # Skull on a pole
MT_MISC34 = 76        # 5 skulls shishkebab
MT_MISC35 = 77        # Pile of skulls/candles
MT_MISC36 = 78        # Tall techno pillar
MT_MISC37 = 79        # Short techno pillar
MT_MISC38 = 80        # Tall green pillar
MT_MISC39 = 81        # Short green pillar
MT_MISC40 = 82        # Tall red pillar
MT_MISC41 = 83        # Short red pillar
MT_MISC42 = 84        # Short pillar
MT_MISC43 = 85        # Tall pillar
MT_MISC44 = 86        # Evil eye
MT_MISC45 = 87        # Floating skull
MT_MISC46 = 88        # Torch tree
MT_MISC47 = 89        # Blue torch
MT_MISC48 = 90        # Green torch
MT_MISC49 = 91        # Red torch
MT_MISC50 = 92        # Short blue torch
MT_MISC51 = 93        # Short green torch
MT_MISC52 = 94        # Short red torch
MT_MISC53 = 95        # Dead player
MT_MISC54 = 96        # Dead zombieman
MT_MISC55 = 97        # Dead demon
MT_MISC56 = 98        # Dead cacodemon
MT_MISC57 = 99        # Dead imp
MT_MISC58 = 100       # Dead sergeant
MT_MISC59 = 101       # Bloody mess 1
MT_MISC60 = 102       # Bloody mess 2
MT_MISC61 = 103       # Pool of blood
MT_MISC62 = 104       # Impaled human
MT_MISC63 = 105       # Twitching impaled human
MT_MISC64 = 106       # Skull on a pole
MT_MISC65 = 107       # 5 skulls shishkebab
MT_MISC66 = 108       # Pile of skulls/candles
MT_MISC67 = 109       # Hanging victim, twitching
MT_MISC68 = 110       # Hanging victim, arms out
MT_MISC69 = 111       # Hanging victim, 1-legged
MT_MISC70 = 112       # Hanging pair of legs
MT_MISC71 = 113       # Hanging victim, arms out
MT_MISC72 = 114       # Hanging leg
MT_MISC73 = 115       # Hanging victim, arms out
MT_MISC74 = 116       # Hanging torso, looking down
MT_MISC75 = 117       # Hanging torso, open skull
MT_MISC76 = 118       # Hanging torso, looking up
MT_MISC77 = 119       # Hanging torso, brain removed
MT_MISC78 = 120       # Pool of blood and flesh
MT_MISC79 = 121       # Burning barrel
MT_MISC80 = 122       # Hanging victim, guts removed
MT_MISC81 = 123       # Hanging victim, guts and brain removed
MT_MISC82 = 124       # Hanging torso, looking down
MT_MISC83 = 125       # Hanging torso, open skull
MT_MISC84 = 126       # Hanging torso, looking up
MT_MISC85 = 127       # Hanging torso, brain removed
MT_MISC86 = 128       # Large brown tree


# Category mapping: MT_* -> footprint category
ENTITY_CATEGORIES = {
    # Player (special - large distinctive package)
    MT_PLAYER: CATEGORY_ENEMY,  # Treat player as enemy for QFP-64

    # Enemies -> QFP packages (complex, aggressive-looking)
    MT_POSSESSED: CATEGORY_ENEMY,
    MT_SHOTGUY: CATEGORY_ENEMY,
    MT_VILE: CATEGORY_ENEMY,
    MT_UNDEAD: CATEGORY_ENEMY,
    MT_FATSO: CATEGORY_ENEMY,
    MT_CHAINGUY: CATEGORY_ENEMY,
    MT_TROOP: CATEGORY_ENEMY,
    MT_SERGEANT: CATEGORY_ENEMY,
    MT_SHADOWS: CATEGORY_ENEMY,
    MT_HEAD: CATEGORY_ENEMY,
    MT_BRUISER: CATEGORY_ENEMY,
    MT_KNIGHT: CATEGORY_ENEMY,
    MT_SKULL: CATEGORY_ENEMY,
    MT_SPIDER: CATEGORY_ENEMY,
    MT_BABY: CATEGORY_ENEMY,
    MT_CYBORG: CATEGORY_ENEMY,
    MT_PAIN: CATEGORY_ENEMY,

    # Collectibles -> SOT-23 (small, simple)
    # Health
    MT_MISC0: CATEGORY_COLLECTIBLE,   # Armor bonus
    MT_MISC1: CATEGORY_COLLECTIBLE,   # Green armor
    MT_MISC2: CATEGORY_COLLECTIBLE,   # Blue armor
    MT_MISC3: CATEGORY_COLLECTIBLE,   # Mega armor
    MT_MISC10: CATEGORY_COLLECTIBLE,  # Stimpack
    MT_MISC11: CATEGORY_COLLECTIBLE,  # Medikit
    MT_MISC12: CATEGORY_COLLECTIBLE,  # Soul sphere
    MT_INV: CATEGORY_COLLECTIBLE,     # Invulnerability
    MT_MISC13: CATEGORY_COLLECTIBLE,  # Berserk
    # Powerups
    MT_INS: CATEGORY_COLLECTIBLE,     # Invisibility
    MT_MISC14: CATEGORY_COLLECTIBLE,  # Radiation suit
    MT_MISC15: CATEGORY_COLLECTIBLE,  # Computer map
    MT_MISC16: CATEGORY_COLLECTIBLE,  # Light amp goggles
    # Keys
    MT_MISC4: CATEGORY_COLLECTIBLE,   # Blue keycard
    MT_MISC5: CATEGORY_COLLECTIBLE,   # Red keycard
    MT_MISC6: CATEGORY_COLLECTIBLE,   # Yellow keycard
    MT_MISC7: CATEGORY_COLLECTIBLE,   # Yellow skull key
    MT_MISC8: CATEGORY_COLLECTIBLE,   # Red skull key
    MT_MISC9: CATEGORY_COLLECTIBLE,   # Blue skull key
    # Ammo
    MT_CLIP: CATEGORY_COLLECTIBLE,    # Ammo clip
    MT_MISC17: CATEGORY_COLLECTIBLE,  # Box of ammo
    MT_MISC18: CATEGORY_COLLECTIBLE,  # Rocket
    MT_MISC19: CATEGORY_COLLECTIBLE,  # Box of rockets
    MT_MISC20: CATEGORY_COLLECTIBLE,  # Cell charge
    MT_MISC21: CATEGORY_COLLECTIBLE,  # Cell pack
    MT_MISC22: CATEGORY_COLLECTIBLE,  # Shells
    MT_MISC23: CATEGORY_COLLECTIBLE,  # Box of shells
    MT_MISC24: CATEGORY_COLLECTIBLE,  # Backpack
    # Weapons
    MT_MISC25: CATEGORY_COLLECTIBLE,  # BFG 9000
    MT_CHAINGUN: CATEGORY_COLLECTIBLE,  # Chaingun
    MT_MISC26: CATEGORY_COLLECTIBLE,  # Chainsaw
    MT_MISC27: CATEGORY_COLLECTIBLE,  # Rocket launcher
    MT_MISC28: CATEGORY_COLLECTIBLE,  # Plasma rifle
    MT_SHOTGUN: CATEGORY_COLLECTIBLE,  # Shotgun
    MT_SUPERSHOTGUN: CATEGORY_COLLECTIBLE,  # Super shotgun

    # Decorations -> SOIC/TSSOP (medium, flat)
    MT_BARREL: CATEGORY_DECORATION,   # Exploding barrel
    MT_MISC29: CATEGORY_DECORATION,   # Green pillar
    MT_MISC30: CATEGORY_DECORATION,   # Short green pillar
    MT_MISC31: CATEGORY_DECORATION,   # Tall red pillar
    MT_MISC32: CATEGORY_DECORATION,   # Short red pillar
    MT_MISC33: CATEGORY_DECORATION,   # Skull on a pole
    MT_MISC34: CATEGORY_DECORATION,   # 5 skulls shishkebab
    MT_MISC35: CATEGORY_DECORATION,   # Pile of skulls/candles
    MT_MISC36: CATEGORY_DECORATION,   # Tall techno pillar
    MT_MISC37: CATEGORY_DECORATION,   # Short techno pillar
    MT_MISC38: CATEGORY_DECORATION,   # Tall green pillar
    MT_MISC39: CATEGORY_DECORATION,   # Short green pillar
    MT_MISC40: CATEGORY_DECORATION,   # Tall red pillar
    MT_MISC41: CATEGORY_DECORATION,   # Short red pillar
    MT_MISC42: CATEGORY_DECORATION,   # Short pillar
    MT_MISC43: CATEGORY_DECORATION,   # Tall pillar
    MT_MISC44: CATEGORY_DECORATION,   # Evil eye
    MT_MISC45: CATEGORY_DECORATION,   # Floating skull
    MT_MISC46: CATEGORY_DECORATION,   # Torch tree
    MT_MISC47: CATEGORY_DECORATION,   # Blue torch
    MT_MISC48: CATEGORY_DECORATION,   # Green torch
    MT_MISC49: CATEGORY_DECORATION,   # Red torch
    MT_MISC50: CATEGORY_DECORATION,   # Short blue torch
    MT_MISC51: CATEGORY_DECORATION,   # Short green torch
    MT_MISC52: CATEGORY_DECORATION,   # Short red torch
    # Dead bodies
    MT_MISC53: CATEGORY_DECORATION,   # Dead player
    MT_MISC54: CATEGORY_DECORATION,   # Dead zombieman
    MT_MISC55: CATEGORY_DECORATION,   # Dead demon
    MT_MISC56: CATEGORY_DECORATION,   # Dead cacodemon
    MT_MISC57: CATEGORY_DECORATION,   # Dead imp
    MT_MISC58: CATEGORY_DECORATION,   # Dead sergeant
    MT_MISC59: CATEGORY_DECORATION,   # Bloody mess 1
    MT_MISC60: CATEGORY_DECORATION,   # Bloody mess 2
    MT_MISC61: CATEGORY_DECORATION,   # Pool of blood
    # Hanging decorations
    MT_MISC62: CATEGORY_DECORATION,   # Impaled human
    MT_MISC63: CATEGORY_DECORATION,   # Twitching impaled human
    MT_MISC64: CATEGORY_DECORATION,   # Skull on a pole
    MT_MISC65: CATEGORY_DECORATION,   # 5 skulls shishkebab
    MT_MISC66: CATEGORY_DECORATION,   # Pile of skulls/candles
    MT_MISC67: CATEGORY_DECORATION,   # Hanging victim, twitching
    MT_MISC68: CATEGORY_DECORATION,   # Hanging victim, arms out
    MT_MISC69: CATEGORY_DECORATION,   # Hanging victim, 1-legged
    MT_MISC70: CATEGORY_DECORATION,   # Hanging pair of legs
    MT_MISC71: CATEGORY_DECORATION,   # Hanging victim, arms out
    MT_MISC72: CATEGORY_DECORATION,   # Hanging leg
    MT_MISC73: CATEGORY_DECORATION,   # Hanging victim, arms out
    MT_MISC74: CATEGORY_DECORATION,   # Hanging torso, looking down
    MT_MISC75: CATEGORY_DECORATION,   # Hanging torso, open skull
    MT_MISC76: CATEGORY_DECORATION,   # Hanging torso, looking up
    MT_MISC77: CATEGORY_DECORATION,   # Hanging torso, brain removed
    MT_MISC78: CATEGORY_DECORATION,   # Pool of blood and flesh
    MT_MISC79: CATEGORY_DECORATION,   # Burning barrel
    MT_MISC80: CATEGORY_DECORATION,   # Hanging victim, guts removed
    MT_MISC81: CATEGORY_DECORATION,   # Hanging victim, guts and brain removed
    MT_MISC82: CATEGORY_DECORATION,   # Hanging torso, looking down
    MT_MISC83: CATEGORY_DECORATION,   # Hanging torso, open skull
    MT_MISC84: CATEGORY_DECORATION,   # Hanging torso, looking up
    MT_MISC85: CATEGORY_DECORATION,   # Hanging torso, brain removed
    MT_MISC86: CATEGORY_DECORATION,   # Large brown tree
}


def get_footprint_category(mobj_type):
    """
    Get footprint category for a given DOOM entity type.

    Args:
        mobj_type: DOOM mobjtype_t enum value (MT_* constant)

    Returns:
        CATEGORY_* constant (COLLECTIBLE, DECORATION, ENEMY, or UNKNOWN)

    Example:
        >>> get_footprint_category(MT_SHOTGUY)
        2  # CATEGORY_ENEMY

        >>> get_footprint_category(MT_MISC11)
        0  # CATEGORY_COLLECTIBLE (medikit)
    """
    return ENTITY_CATEGORIES.get(mobj_type, CATEGORY_UNKNOWN)


def get_footprint_name(category):
    """
    Get footprint package name for a category.

    Args:
        category: CATEGORY_* constant

    Returns:
        str: Footprint package name (e.g., "SOT-23", "QFP-64")

    Example:
        >>> get_footprint_name(CATEGORY_COLLECTIBLE)
        "SOT-23"
    """
    if category == CATEGORY_COLLECTIBLE:
        return "SOT-23"  # Small 3-pin package
    elif category == CATEGORY_DECORATION:
        return "SOIC-8"  # Medium 8-pin flat package
    elif category == CATEGORY_ENEMY:
        return "QFP-64"  # Large 64-pin complex package
    else:
        return "SOIC-8"  # Default fallback
