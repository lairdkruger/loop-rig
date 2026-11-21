"""
Mix setup for LoopPad: master chain, the "Space" reverb/delay return, drum glue,
and the sidechain ("Duck") compressor on Keys.

Parameters are set by their displayed value (dB, Hz, ms, %, ratio) so the
numbers below read like Live's own UI. The first time each device type is
inserted its parameter names are written to Log.txt, to make fixing a renamed
parameter easy.
"""

import re
import Live

SPACE_NAME = "Space"
DUCK_NAME = "Duck"
KIT_TRIM_NAME = "Kit Trim"

_logged_devices = set()


# --------------------------------------------------------------- params ---

def _parse(text):
    """Displayed parameter text -> number in base units (Hz, ms, dB, %, ratio)."""
    t = text.strip().lower()
    if "inf" in t:
        return -1000.0 if "-" in t else 1000.0
    m = re.search(r"-?\d+(\.\d+)?", t)
    if m is None:
        return None
    value = float(m.group(0))
    rest = t[m.end():].strip()
    if rest.startswith("khz"):
        value *= 1000.0
    elif rest.startswith("s") and not rest.startswith("st"):
        value *= 1000.0  # seconds -> ms
    return value


def find_param(device, name):
    for p in device.parameters:
        if p.name.lower() == name.lower():
            return p
    return None


def set_param(device, name, target, log):
    """Set a parameter by its displayed value. Strings pick a named option
    (e.g. "Low Pass"); True/False switch an on/off parameter."""
    p = find_param(device, name)
    if p is None:
        log("%s has no parameter %r" % (device.name, name))
        return False
    return set_value(p, target, "%s %s" % (device.name, name), log)


def set_value(p, target, label, log):
    try:
        if isinstance(target, bool):
            p.value = p.max if target else p.min
            return True
        if isinstance(target, str):
            items = [str(i).lower() for i in p.value_items]
            for i, item in enumerate(items):
                if item == target.lower() or item.startswith(target.lower()):
                    p.value = p.min + i
                    return True
            log("%s: no option %r in %r" % (label, target, list(p.value_items)))
            return False
        # Numeric: bisect on the displayed value
        lo, hi = p.min, p.max
        v_lo, v_hi = _parse(p.str_for_value(lo)), _parse(p.str_for_value(hi))
        if v_lo is None or v_hi is None:
            log("%s: can't read display %r" % (label, p.str_for_value(lo)))
            return False
        rising = v_hi >= v_lo
        target = max(min(target, max(v_lo, v_hi)), min(v_lo, v_hi))
        for _ in range(40):
            mid = (lo + hi) / 2.0
            v = _parse(p.str_for_value(mid))
            if v is None:
                break
            if (v < target) == rising:
                lo = mid
            else:
                hi = mid
        p.value = (lo + hi) / 2.0
        return True
    except Exception as e:
        log("%s: couldn't set %r: %r" % (label, target, e))
        return False


def set_params(device, params, log):
    for name, target in params:
        set_param(device, name, target, log)


# -------------------------------------------------------------- devices ---

def insert(track, device_name, index, log):
    """Insert a built-in device; None if Lite doesn't have it."""
    try:
        index = min(index, len(track.devices))
        track.insert_device(device_name, index)
        device = track.devices[index]
    except Exception as e:
        log("device %s unavailable on %s: %r" % (device_name, track.name, e))
        return None
    if device.class_name not in _logged_devices:
        _logged_devices.add(device.class_name)
        log("%s parameters: %s" % (device_name, ", ".join(p.name for p in device.parameters)))
    return device


def find_device(track, class_names):
    for device in track.devices:
        if device.class_name in class_names:
            return device
    return None


COMPRESSOR = ("Compressor2",)
GLUE = ("GlueCompressor",)
LIMITER = ("Limiter",)
DRUM_BUSS = ("DrumBuss",)
REVERB = ("Reverb",)
DELAY = ("Delay",)


def find_duck(track):
    """The sidechain compressor on Keys: the one named Duck, else the last Compressor."""
    found = None
    for device in track.devices:
        if device.class_name in COMPRESSOR:
            found = device
            if device.name == DUCK_NAME:
                return device
    return found


# ---------------------------------------------------------------- setup ---

def ensure_master(song, log):
    master = song.master_track
    if find_device(master, GLUE + COMPRESSOR) is None:
        glue = insert(master, "Glue Compressor", 0, log)
        if glue is not None:
            set_params(glue, [("Threshold", -10.0), ("Ratio", "2"), ("Attack", "10"),
                              ("Release", "Auto"), ("Makeup", 2.0)], log)
        else:
            comp = insert(master, "Compressor", 0, log)
            if comp is not None:
                set_params(comp, [("Threshold", -12.0), ("Ratio", 2.0), ("Attack", 10.0),
                                  ("Release", 100.0)], log)
    if find_device(master, LIMITER) is None:
        limiter = insert(master, "Limiter", len(master.devices), log)
        if limiter is not None:
            set_params(limiter, [("Ceiling", -0.3)], log)


def ensure_space(song, loop_bus, log):
    """Find or make the Space return (delay into reverb), and return it."""
    space = None
    for r in song.return_tracks:
        if r.name.strip().lower() == SPACE_NAME.lower():
            space = r
    if space is None:
        others = [r for r in song.return_tracks if loop_bus is None or r != loop_bus]
        try:
            if others:
                space = others[0]  # e.g. Live's default "A-Reverb"
            elif len(song.return_tracks) < 2:
                song.create_return_track()
                space = song.return_tracks[-1]
            else:
                log("no free return for Space")
                return None
            while len(space.devices):
                space.delete_device(0)
            space.name = SPACE_NAME
        except Exception as e:
            log("couldn't make Space return: %r" % (e,))
            return None
    if find_device(space, DELAY) is None:
        delay = insert(space, "Delay", 0, log)
        if delay is not None:
            set_params(delay, [("Dry/Wet", 30.0), ("Feedback", 35.0)], log)
    if find_device(space, REVERB) is None:
        reverb = insert(space, "Reverb", len(space.devices), log)
        if reverb is not None:
            set_params(reverb, [("Dry/Wet", 100.0)], log)
    # Space must never feed the Loop Bus (loops record dry)
    if loop_bus is not None:
        bus_index = list(song.return_tracks).index(loop_bus)
        sends = space.mixer_device.sends
        if bus_index < len(sends):
            sends[bus_index].value = sends[bus_index].min
    return space


SATURATOR = ("Saturator",)


def ensure_drum_buss(track, log):
    """Drum glue: Drum Buss where available, else a Saturator (Lite has no Drum Buss)."""
    device = find_device(track, DRUM_BUSS + SATURATOR)
    if device is None:
        device = insert(track, "Drum Buss", len(track.devices), log)
    if device is None:
        device = insert(track, "Saturator", len(track.devices), log)
        if device is not None:
            set_params(device, [("Drive", 6.0)], log)
    return device


def ensure_kit_trim(track, log):
    """A Utility named Kit Trim straight after the kit, for per-genre level."""
    for device in track.devices:
        if device.name == KIT_TRIM_NAME:
            return device
    index = 0
    for i, device in enumerate(track.devices):
        if device.type == Live.Device.DeviceType.instrument:
            index = i + 1
    trim = insert(track, "Utility", index, log)
    if trim is not None:
        try:
            trim.name = KIT_TRIM_NAME
        except Exception:
            pass
    return trim


def ensure_duck(track, log):
    duck = find_duck(track)
    if duck is None:
        duck = insert(track, "Compressor", len(track.devices), log)
        if duck is None:
            return None
        try:
            duck.name = DUCK_NAME
        except Exception:
            pass
        # Listen to the sidechain, filtered down to the kick
        set_params(duck, [("S/C On", True), ("S/C EQ On", True), ("S/C EQ Type", "Low"),
                          ("S/C EQ Freq", 120.0), ("Attack", 1.0)], log)
    return duck


def apply_genre(song, tracks, loop_bus, genre, log):
    """Per-genre mix: drum glue amount, sidechain strength, Space size and sends.
    tracks maps role -> Track (guitar, pads, kit, keys, loops=[...])."""
    mix = genre.get("mix", {})
    ensure_master(song, log)
    space = ensure_space(song, loop_bus, log)

    for track in (tracks.get("pads"),):
        if track is not None:
            trim = ensure_kit_trim(track, log)
            if trim is not None:
                set_params(trim, [("Output", mix.get("kit_trim", 0.0))], log)  # Utility's Gain knob
            buss = ensure_drum_buss(track, log)
            if buss is not None:
                set_params(buss, [("Dry/Wet", mix.get("drum_glue", 30.0))], log)

    # Keys ducks live; each loop track has its own Duck, on for every loop
    # but the drum loops (LoopPad switches those on and off)
    for track in [tracks.get("keys")] + list(tracks.get("loops", [])):
        if track is not None:
            duck = ensure_duck(track, log)
            if duck is not None:
                set_params(duck, mix.get("duck", []), log)

    if space is not None:
        reverb = find_device(space, REVERB)
        if reverb is not None:
            set_params(reverb, [("Decay Time", mix.get("space_decay", 1800.0))], log)
        index = list(song.return_tracks).index(space)
        send_db = mix.get("space_send", -14.0)
        levels = [("guitar", send_db), ("keys", send_db),
                  ("pads", send_db - 6.0), ("sampler", send_db - 6.0)]
        for role, db in levels:
            track = tracks.get(role)
            if track is not None and index < len(track.mixer_device.sends):
                set_value(track.mixer_device.sends[index], db, "%s send" % track.name, log)
        for track in tracks.get("loops", []):
            if track is not None and index < len(track.mixer_device.sends):
                set_value(track.mixer_device.sends[index], send_db, "%s send" % track.name, log)


# ------------------------------------------------------------ sidechain ---

def set_enabled(device, enabled):
    """Switch a device on/off (only touches it when it changes)."""
    p = find_param(device, "Device On")
    if p is not None and (p.value > p.min) != enabled:
        p.value = p.max if enabled else p.min


def route_duck(duck, source_track, log, chain_name=None):
    """Point the Duck compressor's sidechain at source_track: at one of its
    Drum Rack chains when chain_name is given and Live offers it (e.g. just
    the kick), else post mixer (so a muted loop stops ducking). Returns True
    if it's now routed there."""
    try:
        current = duck.input_routing_type
        if current is None or current.display_name != source_track.name:
            for rt in duck.available_input_routing_types:
                if rt.display_name == source_track.name:
                    duck.input_routing_type = rt
                    break
            else:
                return False
        channels = list(duck.available_input_routing_channels)
        wanted = None
        if chain_name:
            wanted = next((ch for ch in channels
                           if chain_name.lower() in ch.display_name.lower()), None)
            if wanted is None and (source_track.name, chain_name) not in _missing_chains:
                _missing_chains.add((source_track.name, chain_name))
                log("no sidechain channel for chain %r on %s; options: %r" % (
                    chain_name, source_track.name, [ch.display_name for ch in channels]))
        if wanted is None:
            wanted = next((ch for ch in channels if "post mixer" in ch.display_name.lower()), None)
        current = duck.input_routing_channel
        if wanted is not None and (current is None or current.display_name != wanted.display_name):
            duck.input_routing_channel = wanted
        return True
    except Exception as e:
        log("sidechain routing error: %r" % (e,))
        return False


_missing_chains = set()  # (track, chain) pairs already reported, to log each once
