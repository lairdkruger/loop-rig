"""
Shared between LoopPad (Launchpad X) and LoopKeys (Launchkey MK2):
track names, genre definitions, and preset loading.

Each genre has built-in starting sounds (below). To use your own, save a
preset anywhere in your User Library named <genre number>-<part>[-<slot>],
optionally followed by a label after a space:

    "1-keys-1"               genre 1 (House/DnB), keys sound 1 (Launchkey pad 1)
    "1-keys-2 Reese"         genre 1, keys sound 2, labelled "Reese"
    "3-kit" or "3-pads"      genre 3 (Jazz) drum kit on the Launchpad pads
    "4-guitar"               genre 4 (Surf) Guitar effects (Audio Effect Rack)

Genres are numbered in pad order: 1 House/DnB, 2 Hip Hop, 3 Jazz, 4 Surf.
The older "Hip Hop - 1 Bass" style still works. A saved preset replaces the
built-in one in the same slot. New presets are picked up the next time you
press a genre pad on the Launchpad or a sound pad on the Launchkey.
"""

import os
import re
import Live
from . import mix

GUITAR_TRACK_NAME = "Guitar"
PADS_TRACK_NAME = "Pads"   # Drum Rack played from the Launchpad
KIT_TRACK_NAME = "Kit"     # old Alesis Nitro drum track, then Sub, now turned into Sampler
SUB_TRACK_NAME = "Sub"     # old sub bass track, now turned into Sampler
SAMPLER_TRACK_NAME = "Sampler"  # the 8 sample chops (Launchpad), optionally pitched from the Launchkey
KEYS_TRACK_NAME = "Keys"
LOOP_TRACK_NAMES = ["Loop %d" % (i + 1) for i in range(4)]

# Novation palette indices: bright colour; the dim version is colour + 2
ORANGE, YELLOW, GREEN, CYAN, BLUE, PURPLE, PINK, RED = 9, 13, 21, 37, 45, 49, 57, 5

# Launchkey pad colour for keys sounds 1-4
KEY_COLORS = [PURPLE, CYAN, PINK, YELLOW]
MAX_KEYS = 4

# Sidechain shared by every genre: 2.5:1, clamp instantly (Attack 0 sets the
# Compressor's minimum), recover in 40 ms. (Much under ~30 ms release starts
# to distort low bass notes.) Each genre sets its own threshold.
FAST_DUCK = [("Ratio", 2.5), ("Attack", 0.0), ("Release", 40.0), ("Auto Release On/Off", False)]

# Old-school sampler bass (Premier / Pete Rock era): squash it for punch,
# saturate, crush to SP-1200-ish 12 bit / 26 kHz, roll off the top.
GRIMY_BASS_FX = [
    ("Compressor", [("Threshold", -22.0), ("Ratio", 4.0), ("Attack", 12.0),
                    ("Release", 70.0), ("Output", 4.0)]),
    ("Saturator", [("Drive", 9.0), ("Output", -4.0)]),
    ("Redux", [("Bit Depth", 12.0), ("Sample Rate", 26000.0)]),
    ("Auto Filter", [("Frequency", 2500.0)]),
]

# Heavy 808: driven harder for harmonics that cut through on small speakers
HEAVY_808_FX = [
    ("Saturator", [("Drive", 6.0), ("Output", -4.0)]),
]

# Dusty record: keys that sound sampled off vinyl (Madlib / Dilla style).
# Warm drive, a 10 bit / 22 kHz crush mixed in, and the top rolled off.
DUSTY_FX = [
    ("Saturator", [("Drive", 6.0), ("Output", -3.0)]),
    ("Redux", [("Bit Depth", 10.0), ("Sample Rate", 22000.0), ("Dry/Wet", 60.0)]),
    ("Auto Filter", [("Filter Type", "Low"), ("Frequency", 4500.0), ("Resonance", 0.0)]),
]

# 60s garage texture for the surf keys: valve-ish drive, top end of an old amp
SURF_KEYS_FX = [
    ("Saturator", [("Drive", 5.0), ("Output", -3.0)]),
    ("Auto Filter", [("Filter Type", "Low"), ("Frequency", 6500.0), ("Resonance", 0.0)]),
]

# Clean, deep, smooth jazz guitar: highs rolled off like a turned-down tone
# knob, gentle compression to even it out, and a small warm room
JAZZ_GUITAR = [
    ("Auto Filter", [("Filter Type", "Low"), ("Frequency", 3200.0), ("Resonance", 0.0)]),
    ("Compressor", [("Threshold", -22.0), ("Ratio", 2.5), ("Attack", 15.0), ("Release", 150.0),
                    ("Output", 3.0)]),
    ("Reverb", [("Predelay", 12.0), ("Decay Time", 1100.0), ("Room Size", 40.0), ("Dry/Wet", 18.0)]),
]

# The jazz guitar, then sampled off a record: drive and a light crush
DUSTY_GUITAR = JAZZ_GUITAR[:2] + [
    ("Saturator", [("Drive", 7.0), ("Output", -3.0)]),
    ("Redux", [("Bit Depth", 12.0), ("Sample Rate", 26000.0), ("Dry/Wet", 50.0)]),
    ("Reverb", [("Predelay", 8.0), ("Decay Time", 900.0), ("Room Size", 30.0), ("Dry/Wet", 15.0)]),
]

# Surf: a Fender amp just breaking up, gentle tremolo, slapback echo and a
# drippy spring (small, bright, long tail, lots of it)
SURF_GUITAR = [
    ("Saturator", [("Drive", 4.0), ("Output", -2.0)]),
    ("Auto Pan-Tremolo", [("Mode", "Tremolo"), ("LFO Synced", False), ("LFO Amount", 25.0),
                          ("LFO Freq", 5.5)]),
    ("Delay", [("L Sync", False), ("R Sync", False), ("L Time", 110.0), ("R Time", 125.0),
               ("Feedback", 15.0), ("Dry/Wet", 20.0)]),
    ("Reverb", [("Predelay", 2.0), ("Decay Time", 2800.0), ("Room Size", 20.0),
                ("Diff. Hi On", False), ("Dry/Wet", 40.0)]),
]

# Built-in starting sounds (Core Library). Keys are (label, preset) or
# (label, preset, effects) where effects is a chain added after it.
# Every preset here uses only devices and effects Live Lite has, and its
# samples ship with Lite.
# guitar is a list of (audio effect, [(parameter, displayed value)]), or the
# older (audio effect, {parameter: raw value}).
# mix: Drum Buss amount on the drum tracks, the Keys sidechain ("Duck")
# compressor, and how much of everything goes to the Space reverb return.
GENRES = [
    {
        "name": "House/DnB",
        "color": CYAN,
        "kit": "909 Core Kit",
        # House, DnB, future, dub, techno: two basses, a dub chord pad, a lead.
        # Slot 1 is your saved "1-keys-1 Bass" (Wavetable); Analog Bass if it's missing.
        "keys": [("Sub Bass", "Analog Bass"),            # deep sub
                 ("Plain Bass", "Plain Bass"),           # punchier, grittier bass
                 ("Dub Pad", "Echo Pad"),                # chord pad with dub delay
                 ("Lead", "Superstring Lead")],          # wide supersaw-style lead
        "guitar": [("Chorus-Ensemble", {}), ("Reverb", {"Dry/Wet": 0.3})],
        "mix": {"drum_glue": 30.0,  # Drum Buss dry/wet %
                "duck": [("Threshold", -20.0)] + FAST_DUCK,  # medium sidechain
                "space_send": -14.0, "space_decay": 1800.0,  # send dB, reverb decay ms
                "kit_trim": 4.0},  # kit level dB, evens out the kits' built-in levels
    },
    {
        "name": "Hip Hop",
        "color": ORANGE,
        "kit": "Boom Bap Kit",
        # Grimy, dusty sampled sounds: everything sounds lifted off a record
        "keys": [("808", "808 BNYX Stopper", HEAVY_808_FX),           # heavy sub 808
                 ("Dusty Rhodes", "E-Piano Roads", DUSTY_FX),       # crushed Rhodes
                 ("Dusty Strings", "Ac Strings Orch", DUSTY_FX),    # Wu-Tang style string sample
                 ("Grime Lead", "Grime Lead", DUSTY_FX[:1])],       # lo-fi square lead, driven
        "guitar": DUSTY_GUITAR,
        "mix": {"drum_glue": 40.0,  # Drum Buss dry/wet %
                "duck": [("Threshold", -24.0)] + FAST_DUCK,  # heavy sidechain, for the 808
                "space_send": -18.0, "space_decay": 1200.0,  # send dB, reverb decay ms
                "kit_trim": 0.0},  # kit level dB, evens out the kits' built-in levels
    },
    {
        "name": "Jazz",
        "color": PURPLE,
        "kit": "Ahlimba Kit",  # brushed ride, hats and toms, shuffle kick/snare, congas
        # Berlioz-style jazz house: bass, Rhodes, strings, and a smooth horn
        # (Lite has no sax; the flugelhorn is its smoothest sampled horn)
        "keys": [("Dirty Bass", "Electric Bass Raw", GRIMY_BASS_FX),  # sampler-style grimy bass
                 ("Rhodes", "E-Piano Roads"),            # sampled Rhodes-style e-piano
                 ("Strings", "Ac Strings Orch"),         # sampled string section
                 ("Flugelhorn", "Ac Flugelhorn")],       # mellow sampled horn
        "guitar": JAZZ_GUITAR,
        "mix": {"drum_glue": 20.0,  # Drum Buss dry/wet %
                "duck": [("Threshold", -12.0)] + FAST_DUCK,  # light sidechain
                "space_send": -14.0, "space_decay": 2200.0,  # send dB, reverb decay ms
                "kit_trim": -4.0},  # kit level dB, evens out the kits' built-in levels
    },
    {
        "name": "Surf",
        "color": YELLOW,
        "kit": "Corvaire Kit",  # vintage acoustic kit: felt kick, stick snare, roomy
        # 60s surf to Skegss / Surf Curse: picked bass, cheap combo organ,
        # a twangy keys guitar and vibes, all with old-amp texture
        "keys": [("Bass", "Electric Bass Raw", SURF_KEYS_FX[:1]),     # picked bass, driven
                 ("Combo Organ", "Organ LoFi", SURF_KEYS_FX),          # Farfisa-ish organ
                 ("Twang", "Guitar Electric Clean", SURF_KEYS_FX),     # clean surf guitar on keys
                 ("Vibes", "Vibraphone", SURF_KEYS_FX[1:])],           # exotica vibes
        "guitar": SURF_GUITAR,
        "mix": {"drum_glue": 35.0,  # Drum Buss dry/wet %
                "duck": [("Threshold", -12.0)] + FAST_DUCK,  # light sidechain
                "space_send": -12.0, "space_decay": 2500.0,  # send dB, reverb decay ms
                "kit_trim": 1.0},  # kit level dB, evens out the kits' built-in levels
    },
]

GENRE_KEY = "looppad_genre"
SOUND_KEY = "looppad_sound"
LOAD_COUNT_KEY = "looppad_genre_loads"  # bumped on every genre load so LoopKeys re-resolves

# User Library folders that never hold presets (skipped to keep the scan quick)
SKIP_FOLDERS = {"samples", "clips", "remote scripts", "grooves", "templates", "tunings",
                "midi tools", "defaults", "icon"}


def _browser():
    return Live.Application.get_application().browser


def find_track(song, name):
    for track in song.tracks:
        if track.name.strip().lower() == name.lower():
            return track
    return None


def find_device_deep(devices, class_names):
    """The first device of one of class_names, looking inside racks too."""
    for device in devices:
        if device.class_name in class_names:
            return device
        if device.can_have_chains:
            for chain in device.chains:
                found = find_device_deep(chain.devices, class_names)
                if found is not None:
                    return found
    return None


def find_drum_rack(devices):
    """The first Drum Rack, looking inside Instrument Racks too (some kits,
    like Ahlimba and Corvaire, wrap their Drum Rack in one)."""
    for device in devices:
        if device.can_have_drum_pads:
            return device
    for device in devices:
        if device.can_have_chains:
            for chain in device.chains:
                rack = find_drum_rack(chain.devices)
                if rack is not None:
                    return rack
    return None


# PITCH (LoopPad toggles it, LoopPitch follows it): while on, the key you hold
# on the Launchkey transposes the chops (C3 = the sample's own pitch)
PITCH_KEY = "looppad_pitch"
PITCH_ROOT_NOTE = 60  # C3
CHOP_CHAIN_PREFIX = "Chop "


def set_chop_transpose(song, semitones):
    """Set Transpose on every chop Simpler on the Sampler track. Tape-style:
    the chops aren't warped, so higher also plays faster."""
    track = find_track(song, SAMPLER_TRACK_NAME)
    rack = find_drum_rack(track.devices) if track is not None else None
    if rack is None:
        return
    for chain in rack.chains:
        if not chain.name.startswith(CHOP_CHAIN_PREFIX):
            continue
        for device in chain.devices:
            p = mix.find_param(device, "Transpose")  # Simpler's, in semitones
            if p is not None:
                value = max(p.min, min(p.max, float(semitones)))
                if p.value != value:
                    p.value = value


def current_genre(song):
    index = song.get_data(GENRE_KEY, 0)
    return index if 0 <= index < len(GENRES) else 0


def current_sound(song):
    return song.get_data(SOUND_KEY, 0)


def _stem(name):
    for ext in (".adg", ".adv", ".amxd"):
        if name.lower().endswith(ext):
            return name[:-len(ext)]
    return name


def _norm(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())


_item_cache = {}


def find_browser_item(root, name, max_depth=4):
    """Breadth-first search of a browser folder for a loadable item by name."""
    key = (root.name, name.lower())
    if key in _item_cache:
        return _item_cache[key]
    level = list(root.children)
    for _ in range(max_depth):
        next_level = []
        for item in level:
            if item.is_loadable and _stem(item.name).lower() == name.lower():
                _item_cache[key] = item
                return item
            # Devices like "Drift" hold their presets as children but aren't folders
            next_level.extend(item.children)
        level = next_level
    return None


# ------------------------------------------------------------ user presets ---

_user_presets = None  # list of (stem, item), scanned on demand
_last_seen = {}       # stem -> item from earlier scans, for when the browser comes back short
_missing = set()      # preset stems on disk that neither this scan nor an earlier one found

# Remote Scripts/LoopPad/shared.py -> the User Library folder
USER_LIBRARY_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _disk_presets():
    """Stems of the genre presets saved in the User Library folder on disk."""
    stems = set()
    for root, dirs, files in os.walk(USER_LIBRARY_PATH):
        dirs[:] = [d for d in dirs if d.lower() not in SKIP_FOLDERS]
        for name in files:
            stem = _stem(name)
            if stem != name and _parse_preset_name(stem) is not None:
                stems.add(stem)
    return stems


def _scan_with_fallback():
    """Scan the browser's User Library. While Live is re-indexing it (after
    any file in it changes) the browser can come back short: fill gaps from
    earlier scans, and note presets on disk that are still missing."""
    global _missing
    found = _scan_user_library()
    for stem, item in found:
        _last_seen[stem] = item
    stems = set(stem for stem, _ in found)
    try:
        on_disk = _disk_presets()
    except OSError:
        on_disk = stems
    for stem in on_disk - stems:
        if stem in _last_seen:
            found.append((stem, _last_seen[stem]))
    _missing = set(stem for stem in on_disk if stem not in stems and stem not in _last_seen)
    return found


def missing_presets(index):
    """Presets for genre index that are saved on disk but Live's browser hasn't
    listed yet (it's still indexing): try loading the genre again shortly."""
    return sorted(stem for stem in _missing
                  if (_parse_preset_name(stem) or (None,))[0] == index)


def _scan_user_library(max_depth=8):
    found = []
    level = [i for i in _browser().user_library.children
             if i.name.lower() not in SKIP_FOLDERS]
    for _ in range(max_depth):
        next_level = []
        for item in level:
            if item.is_loadable and _parse_preset_name(_stem(item.name)) is not None:
                found.append((_stem(item.name), item))
            if item.is_folder:
                next_level.extend(item.children)
        level = next_level
    return found


def refresh_user_presets(song=None):
    """Re-scan the User Library and forget resolved genres (picks up new presets).
    Pass the song to tell the other script to do the same."""
    global _user_presets
    if song is not None:
        song.set_data(LOAD_COUNT_KEY, song.get_data(LOAD_COUNT_KEY, 0) + 1)
    _user_presets = None
    _resolved.clear()


_NEW_NAME = re.compile(r"^(\d+)\s*-\s*(keys|kit|pads|guitar)(?:\s*-\s*(\d+))?(?:\s+(.*))?$", re.I)
_OLD_NAME = re.compile(r"^(.+?) - (kit|guitar|(\d+)\s*(.*))$", re.I)


def _parse_preset_name(stem):
    """Preset name -> (genre index, part, slot index or None, label), or None.
    Accepts "1-keys-2 Rhodes" and the older "Hip Hop - 2 Rhodes"."""
    stem = stem.strip()
    m = _NEW_NAME.match(stem)
    if m:
        part = m.group(2).lower()
        if part == "pads":
            part = "kit"  # the kit plays on the Pads track, so either name works
        slot = int(m.group(3)) - 1 if m.group(3) else None
        if part == "keys" and slot is None:
            return None
        return int(m.group(1)) - 1, part, slot, (m.group(4) or "").strip()
    m = _OLD_NAME.match(stem)
    if m:
        index = next((i for i, g in enumerate(GENRES) if _norm(g["name"]) == _norm(m.group(1))), None)
        if index is None:
            return None
        if m.group(3):
            return index, "keys", int(m.group(3)) - 1, m.group(4).strip()
        return index, m.group(2).lower(), None, ""
    return None


def _presets_for(index):
    """This genre's saved presets: {"kit": item, "guitar": item, ("keys", slot): (label, item)}"""
    global _user_presets
    if _user_presets is None:
        _user_presets = _scan_with_fallback()
    result = {}
    for stem, item in _user_presets:
        parsed = _parse_preset_name(stem)
        if parsed is None or parsed[0] != index:
            continue
        _, part, slot, label = parsed
        if part == "keys":
            result[("keys", slot)] = (label or "Sound %d" % (slot + 1), item)
        else:
            result[part] = item
    return result


# ------------------------------------------------------- resolved genres ---

_resolved = {}


def resolve_genre(index):
    """The genre's sounds, with User Library presets taking priority:
    {"kit": item, "keys": [(label, item) or None per slot], "guitar": item or None}"""
    if index in _resolved:
        return _resolved[index]
    genre = GENRES[index]
    user = _presets_for(index)
    browser = _browser()

    kit = user.get("kit") or find_browser_item(browser.drums, genre["kit"])

    keys = []
    for slot in range(MAX_KEYS):
        entry = None
        if ("keys", slot) in user:
            label, item = user[("keys", slot)]
            entry = (label, item, [])
        if entry is None and slot < len(genre["keys"]):
            label, preset = genre["keys"][slot][:2]
            fx = genre["keys"][slot][2] if len(genre["keys"][slot]) > 2 else []
            item = find_browser_item(browser.instruments, preset)
            if item is not None:
                entry = (label, item, fx)
        keys.append(entry)  # None keeps the slot empty, so pads stay in place

    guitar = user.get("guitar")
    resolved = {"kit": kit, "keys": keys, "guitar": guitar}
    _resolved[index] = resolved
    return resolved


def replace_instrument(song, track, item):
    """Remove the track's instrument (keeping its audio effects) and load item."""
    for i in reversed(range(len(track.devices))):
        if track.devices[i].type == Live.Device.DeviceType.instrument:
            track.delete_device(i)
    song.view.selected_track = track
    _browser().load_item(item)


def load_keys_sound(song, sound_index, log):
    keys = resolve_genre(current_genre(song))["keys"]
    if not 0 <= sound_index < len(keys) or keys[sound_index] is None:
        return False
    label, item, fx = keys[sound_index]
    track = find_track(song, KEYS_TRACK_NAME)
    if track is None:
        log("no '%s' track" % KEYS_TRACK_NAME)
        return False
    # Drop the previous sound's effect chain (everything but the instrument and Duck)
    duck = mix.find_duck(track)
    for i in reversed(range(len(track.devices))):
        device = track.devices[i]
        if device.type != Live.Device.DeviceType.instrument and device != duck:
            track.delete_device(i)
    replace_instrument(song, track, item)
    # This sound's own chain goes just before Duck
    for device_name, params in fx:
        index = list(track.devices).index(duck) if duck is not None else len(track.devices)
        device = mix.insert(track, device_name, index, log)
        if device is not None:
            mix.set_params(device, params, log)
    song.set_data(SOUND_KEY, sound_index)
    log("keys sound %s (%s)" % (label, item.name))
    return True
