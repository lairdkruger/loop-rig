"""
PartyPad - Launchpad X karaoke / party controller for Ableton Live 12 Lite.

Runs the Launchpad X in Programmer mode on the "LPX MIDI" port (pad notes are
row*10 + col, row 1 = bottom; the round buttons send CCs with the same
numbering: right column = col 9, top row = row 9).

            col 1    2      3      4       5        6       7      8         round
  row 9   GENRE 1  GENRE 2 GENRE 3 GENRE 4  SONG     MIC IN  TUNE   BUILD (hold 2s)
  row 8   A#       .      C#     D#      .        F#      G#     .         CHOP REC (hold + pad)
  row 7   A        B      C      D       E        F       G      MAJ/MIN   CHOP CLEAR (hold + pad)
  row 6   CLEAN    AUTO   TRAVIS  CHIPMNK MONSTER  ROBOT   RADIO  BIG VERB  TAP TEMPO
  row 5   STUT 1/4 STUT 1/8 ECHO LPF     HPF      WASH    DROP   RESET     TEMPO +1
  row 4   drum     drum   drum   drum    chop     chop    chop   chop      TEMPO -1
  row 3   drum     drum   drum   drum    chop     chop    chop   chop      SONG TEMPO
  row 2   drum     drum   drum   drum    chop     chop    chop   chop
  row 1   drum     drum   drum   drum    chop     chop    chop   chop

Tracks (BUILD makes whichever are missing, leaving everything else alone):
  Song      audio: drop the song's audio file in any clip slot. Its tempo
            becomes the set's tempo (Live estimates it when it warps the file).
  Mic       audio: the vocal chain (styles below), monitored live.
  Chop Rec  audio: records the Mic track's output (after its effects) for the
            vocal chops. Silent, armed, never touch it.
  Pads      MIDI: the genre drum kit, played from the bottom-left 4x4.
  Chops     MIDI: a Drum Rack holding the 16 vocal chops (bottom-right 4x4).

KEY (rows 7-8, laid out like a keyboard from A): sets the key the auto-tune
  snaps to (and the song's key). MAJ/MIN switches major (yellow) / minor (purple).
STYLES (row 6): one vocal style at a time; BIG VERB adds a long reverb over it.
  TUNE switches the auto-tune off and on (styles still change the rest).
DJ (row 5): hold for the effect, on the whole mix (vocal included).
  STUTTER loops the last beat / half beat, ECHO throws a dotted-1/8 echo that
  rings out after you let go, LPF / HPF sweep while held, WASH is a huge
  reverb, DROP mutes the song while held, RESET puts every DJ effect back.
CHOPS: hold an empty (dim pink) pad and sing to record into it; let go to
  finish. Press a full (bright pink) pad to play it. To re-record a full pad,
  hold CHOP REC and hold the pad. Hold CHOP CLEAR and tap a pad to empty it
  (hold CHOP CLEAR alone for 2 s to empty all of them).
GENRE 1-4: loads that genre's drum kit (your saved "N-kit" presets, as in
  LoopPad) onto Pads.
SONG: start / stop the Song track. MIC IN: step through the audio inputs for
  the mic (it lights with the mic's level). SONG TEMPO: set the tempo from the
  song again.
"""

import Live
from _Framework.ControlSurface import ControlSurface
from LoopPad import shared
from LoopPad import mix
from LoopPad import phrases
from . import styles

# ---------------------------------------------------------------- tracks ---

SONG_TRACK = "Song"
MIC_TRACK = "Mic"
CHOP_REC_TRACK = "Chop Rec"
PADS_TRACK = shared.PADS_TRACK_NAME
CHOPS_TRACK = "Chops"
MAX_TRACKS = 8  # Live Lite
DEFAULT_MIC_INPUT = "1"

# ------------------------------------------------------------------ pads ---


def pad(row, col):
    return row * 10 + col


# Keys: white keys along row 7 from A, sharps above them on row 8
KEY_PADS = {pad(7, 1): 9, pad(7, 2): 11, pad(7, 3): 0, pad(7, 4): 2, pad(7, 5): 4,
            pad(7, 6): 5, pad(7, 7): 7,
            pad(8, 1): 10, pad(8, 3): 1, pad(8, 4): 3, pad(8, 6): 6, pad(8, 7): 8}
MODE_PAD = pad(7, 8)
STYLE_PADS = [pad(6, c) for c in range(1, len(styles.STYLES) + 1)]
BIG_VERB_PAD = pad(6, 8)
STUT4_PAD, STUT8_PAD, ECHO_PAD, LPF_PAD, HPF_PAD, WASH_PAD, DROP_PAD, RESET_PAD = (
    [pad(5, c) for c in range(1, 9)])
DJ_PADS = [STUT4_PAD, STUT8_PAD, ECHO_PAD, LPF_PAD, HPF_PAD, WASH_PAD, DROP_PAD, RESET_PAD]
TOP_NOTES = [pad(r, c) for r in range(5, 9) for c in range(1, 9)]

DRUM_PAD_NOTES = [pad(r, c) for r in range(1, 5) for c in range(1, 5)]
DRUM_RACK_FIRST_NOTE = 36  # C1
CHOP_PADS = [pad(r, c) for r in range(1, 5) for c in range(5, 9)]

# Round buttons
GENRE_BUTTONS = [91, 92, 93, 94]
BTN_SONG, BTN_MIC, BTN_TUNE, BTN_BUILD = 95, 96, 97, 98
BTN_CHOP_REC, BTN_CHOP_CLEAR, BTN_TAP, BTN_TEMPO_UP, BTN_TEMPO_DOWN, BTN_SONG_TEMPO = (
    89, 79, 69, 59, 49, 39)
CC_BUTTONS = [row * 10 + 9 for row in range(1, 9)] + list(range(91, 99))

# ---------------------------------------------------------------- timing ---
# Ticks are Live's display updates, roughly every 100 ms

BUILD_HOLD_TICKS = 20
CLEAR_ALL_HOLD_TICKS = 20
MIN_REC_TICKS = 3       # a shorter press on an empty chop pad isn't a take
CHOP_DELAY_TICKS = 5    # after a take closes, before loading it into its pad
SONG_TEMPO_DELAY_TICKS = 10  # let Live warp a new song before reading its tempo
GENRE_RETRY_TICKS = 30
GENRE_RETRY_MAX = 5

CHOP_CHOKE_GROUP = 16   # chops cut each other off (one voice), clear of hat chokes
CHOP_SILENCE_DB = -30.0  # trims the quiet before / after a take
CHOP_PRE_WINDOWS = 2    # keep this many 10 ms windows before the first sound
CHOP_TAIL_WINDOWS = 10  # and after the last

# ---------------------------------------------------------------- colours ---

OFF = 0
WHITE_DIM, WHITE = 1, 3
RED, RED_DIM = 5, 7
ORANGE, ORANGE_DIM = 9, 11
YELLOW, YELLOW_DIM = 13, 15
LIME = 17
GREEN, GREEN_DIM = 21, 23
CYAN, CYAN_DIM = 37, 39
BLUE, BLUE_DIM = 45, 47
PURPLE, PURPLE_DIM = 49, 51
MAGENTA, MAGENTA_DIM = 53, 55
PINK, PINK_DIM = 57, 59
DRUM_ROW_COLORS = [ORANGE, YELLOW, LIME, PURPLE]
STATIC, FLASH, PULSE = 0, 1, 2

SYSEX_HEADER = (0xF0, 0x00, 0x20, 0x29, 0x02, 0x0C)
SYSEX_PROGRAMMER_MODE = SYSEX_HEADER + (0x0E, 0x01, 0xF7)
SYSEX_LIVE_MODE = SYSEX_HEADER + (0x0E, 0x00, 0xF7)
NOTE_ON, CC = 0x90, 0xB0
MONITOR_IN, MONITOR_AUTO, MONITOR_OFF = 0, 1, 2

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT_NAMES = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]

# Saved with the set
KEY_ROOT = "partypad_root"
KEY_MINOR = "partypad_minor"
KEY_STYLE = "partypad_style"
KEY_BIG_VERB = "partypad_big_verb"
KEY_TUNE = "partypad_tune"


class PartyPad(ControlSurface):

    def __init__(self, c_instance):
        # Set up state before ControlSurface.__init__: Live can build the MIDI
        # map (which reads it) while that runs, and an error there leaves
        # every button silently unmapped
        self._tick = 0
        self._pressed = {}
        self._hold_fired = set()
        self._led_cache = {}
        self._mod = None              # "rec" / "clear" while that button is held
        self._full_chops = set()      # chop pad notes holding a sample
        self._rec = None              # the chop take in progress
        self._dj = {}                 # held DJ pad -> tick pressed
        self._fades = {}              # (device name, param) -> (start tick, from %)
        self._sweep_raw = {}          # filter device name -> (open raw, swept raw)
        self._song_clips = None       # file paths in the Song track, to spot new ones
        self._song_tempo_due = None
        self._genre_retries = 0
        ControlSurface.__init__(self, c_instance)
        self.log_message("PartyPad: init")
        self._enter_programmer_mode()
        self._rescan()
        self.request_rebuild_midi_map()
        self._refresh_leds(force=True)
        self.show_message("PartyPad ready - hold the top-right button to build the set")

    # ------------------------------------------------------ live plumbing ---

    def _log(self, msg):
        self.log_message("PartyPad: " + msg)

    def disconnect(self):
        for note in range(11, 89):
            self._send_midi((NOTE_ON, note, 0))
        for button in CC_BUTTONS:
            self._send_midi((CC, button, 0))
        self._send_midi(SYSEX_LIVE_MODE)
        ControlSurface.disconnect(self)

    def refresh_state(self):
        ControlSurface.refresh_state(self)
        self._enter_programmer_mode()
        self._refresh_leds(force=True)

    def _enter_programmer_mode(self):
        self._send_midi(SYSEX_PROGRAMMER_MODE)
        self._led_cache = {}

    def _forwarded_chops(self):
        """Empty chop pads come to the script (hold to record); full ones pass
        straight through to the Chops track, so they play with no delay. While
        CHOP REC or CHOP CLEAR is held, all of them come here."""
        if self._mod is not None:
            return list(CHOP_PADS)
        return [n for n in CHOP_PADS if n not in self._full_chops]

    def build_midi_map(self, midi_map_handle):
        try:
            handle = self._c_instance.handle()
            for note in TOP_NOTES + self._forwarded_chops():
                Live.MidiMap.forward_midi_note(handle, midi_map_handle, 0, note)
            for button in CC_BUTTONS:
                Live.MidiMap.forward_midi_cc(handle, midi_map_handle, 0, button)
        except Exception as e:
            self.log_message("PartyPad: MIDI map error: %r" % (e,))

    def receive_midi(self, midi_bytes):
        if len(midi_bytes) != 3:
            return
        status, note, velocity = midi_bytes
        kind = status & 0xF0
        if kind == CC and note in CC_BUTTONS:
            pressed = velocity > 0
        elif kind in (0x90, 0x80) and (note in TOP_NOTES or note in CHOP_PADS):
            pressed = kind == 0x90 and velocity > 0
        else:
            return
        try:
            if pressed:
                self._pressed[note] = self._tick
                self._hold_fired.discard(note)
                self._on_press(note)
            else:
                held_since = self._pressed.pop(note, None)
                fired = note in self._hold_fired
                self._hold_fired.discard(note)
                if held_since is not None:
                    self._on_release(note, self._tick - held_since, fired)
        except Exception as e:
            self._log("button error: %r" % (e,))
        self._refresh_leds()

    def update_display(self):
        ControlSurface.update_display(self)
        self._tick += 1
        try:
            self._check_holds()
            self._update_rec()
            self._update_dj()
            self._watch_song()
            if self._tick % 10 == 0:
                self._rescan()
        except Exception as e:
            self._log("update error: %r" % (e,))
        self._refresh_leds()

    # ---------------------------------------------------------- discovery ---

    def _find_track(self, name):
        return shared.find_track(self.song(), name)

    def _device(self, track, name):
        if track is None:
            return None
        return next((d for d in track.devices if d.name == name), None)

    def _chops_rack(self):
        track = self._find_track(CHOPS_TRACK)
        return shared.find_drum_rack(track.devices) if track is not None else None

    def _rescan(self):
        try:
            pads_track = self._find_track(PADS_TRACK)
            if pads_track is not None:
                self._remap_drum_rack(pads_track)
            full = set()
            rack = self._chops_rack()
            if rack is not None:
                for note in CHOP_PADS:
                    if any(len(c.devices) for c in rack.drum_pads[note].chains):
                        full.add(note)
            if full != self._full_chops:
                self._full_chops = full
                self.request_rebuild_midi_map()
        except Exception as e:
            self._log("rescan error: %r" % (e,))

    def _remap_drum_rack(self, track):
        """Move the kit's bottom 16 pads (C1..D#2) onto the Launchpad's
        bottom-left 4x4 programmer-mode notes (as LoopPad does)."""
        rack = shared.find_drum_rack(track.devices)
        if rack is None:
            return
        pads = rack.drum_pads
        if any(len(pads[n].chains) for n in DRUM_PAD_NOTES[:12]):
            return  # already remapped
        moves = []
        for i, target in enumerate(DRUM_PAD_NOTES):
            for chain in pads[DRUM_RACK_FIRST_NOTE + i].chains:
                moves.append((chain, target))
        for chain, target in moves:
            chain.in_note = target
        if moves:
            self._log("remapped %d drum chains to Launchpad pads" % len(moves))

    # ------------------------------------------------------------- presses ---

    def _on_press(self, note):
        song = self.song()
        if note in KEY_PADS:
            song.set_data(KEY_ROOT, KEY_PADS[note])
            self._apply_key()
        elif note == MODE_PAD:
            song.set_data(KEY_MINOR, not self._minor())
            self._apply_key()
        elif note in STYLE_PADS:
            song.set_data(KEY_STYLE, STYLE_PADS.index(note))
            self._apply_style()
            self.show_message("PartyPad: %s vocal" % styles.STYLES[self._style()][0])
        elif note == BIG_VERB_PAD:
            song.set_data(KEY_BIG_VERB, not song.get_data(KEY_BIG_VERB, False))
            self._apply_style()
        elif note in DJ_PADS:
            self._dj_press(note)
        elif note in CHOP_PADS:
            if self._mod == "clear":
                self._clear_chop(note)
            elif self._mod == "rec" or note not in self._full_chops:
                self._start_chop(note)
        elif note in GENRE_BUTTONS:
            self._load_genre(GENRE_BUTTONS.index(note))
        elif note == BTN_SONG:
            self._toggle_song()
        elif note == BTN_MIC:
            self._next_mic_input()
        elif note == BTN_TUNE:
            song.set_data(KEY_TUNE, not self._tune_on())
            self._apply_style()
            self.show_message("PartyPad: auto-tune %s" % ("on" if self._tune_on() else "off"))
        elif note in (BTN_CHOP_REC, BTN_CHOP_CLEAR):
            self._mod = "rec" if note == BTN_CHOP_REC else "clear"
            self.request_rebuild_midi_map()
            self.show_message("PartyPad: hold a chop pad to record it" if self._mod == "rec"
                              else "PartyPad: tap a chop pad to empty it")
        elif note == BTN_TAP:
            song.tap_tempo()
        elif note == BTN_TEMPO_UP:
            song.tempo = min(999.0, round(song.tempo) + 1)
        elif note == BTN_TEMPO_DOWN:
            song.tempo = max(20.0, round(song.tempo) - 1)
        elif note == BTN_SONG_TEMPO:
            self._tempo_from_song()
        elif note == BTN_BUILD:
            self.show_message("PartyPad: keep holding to build the set...")

    def _on_release(self, note, held, hold_fired):
        if note in DJ_PADS:
            self._dj_release(note)
        elif note in CHOP_PADS:
            if self._rec is not None and self._rec["note"] == note and self._rec["stage"] == "recording":
                if held < MIN_REC_TICKS:
                    self._cancel_chop()
                    self.show_message("PartyPad: hold the pad while you sing to record it")
                else:
                    self._close_chop()
        elif note in (BTN_CHOP_REC, BTN_CHOP_CLEAR):
            self._mod = None
            self.request_rebuild_midi_map()

    def _check_holds(self):
        for note, since in list(self._pressed.items()):
            if note in self._hold_fired:
                continue
            held = self._tick - since
            if note == BTN_BUILD and held >= BUILD_HOLD_TICKS:
                self._hold_fired.add(note)
                self._log("BUILD held: building the set")
                self._build_set()
            elif note == BTN_CHOP_CLEAR and held >= CLEAR_ALL_HOLD_TICKS:
                if not any(n in self._pressed for n in CHOP_PADS):
                    self._hold_fired.add(note)
                    for n in CHOP_PADS:
                        self._clear_chop(n)
                    self.show_message("PartyPad: all chops cleared")

    # ---------------------------------------------------------------- key ---

    def _root(self):
        return int(self.song().get_data(KEY_ROOT, 0)) % 12

    def _minor(self):
        return bool(self.song().get_data(KEY_MINOR, False))

    def _apply_key(self):
        song = self.song()
        root, minor = self._root(), self._minor()
        scale = "Minor" if minor else "Major"
        try:
            song.root_note = root
            song.scale_name = scale
        except Exception as e:
            self._log("couldn't set the song's scale: %r" % (e,))
        mic = self._find_track(MIC_TRACK)
        for name in styles.TUNERS:
            tune = self._device(mic, name)
            if tune is not None:
                choose_option(tune, "Root", [NOTE_NAMES[root], FLAT_NAMES[root]], self._log)
                choose_option(tune, "Scale", [scale], self._log)
        self.show_message("PartyPad: key %s %s" % (NOTE_NAMES[root], scale.lower()))

    # ------------------------------------------------------------- styles ---

    def _style(self):
        index = int(self.song().get_data(KEY_STYLE, 1))
        return index if 0 <= index < len(styles.STYLES) else 1

    def _tune_on(self):
        return bool(self.song().get_data(KEY_TUNE, True))

    def _apply_style(self):
        mic = self._find_track(MIC_TRACK)
        if mic is None:
            return
        _, _, settings = styles.STYLES[self._style()]
        self._ensure_low_oct(mic, "Low Oct" in settings)
        for name, _, _ in styles.VOCAL_CHAIN + [styles.LOW_OCT]:
            device = self._device(mic, name)
            if device is None:
                continue
            if name == "Tune":
                on = self._tune_on()
            else:
                on = name in styles.ALWAYS_ON or name in settings
            mix.set_enabled(device, on)
            # Back to the defaults first, so one style's tweaks don't linger in the next
            self._set_params(device, styles.STYLE_DEFAULTS.get(name, []))
            self._set_params(device, settings.get(name, []))
        verb = self._device(mic, "Verb")
        if verb is not None and self.song().get_data(KEY_BIG_VERB, False):
            self._set_params(verb, styles.BIG_VERB)

    def _ensure_low_oct(self, mic, wanted):
        name, device_name, params = styles.LOW_OCT
        device = self._device(mic, name)
        if not wanted:
            if device is not None:
                mic.delete_device(list(mic.devices).index(device))
            return
        if device is not None:
            return
        tune = self._device(mic, "Tune")
        index = list(mic.devices).index(tune) + 1 if tune is not None else 0
        device = mix.insert(mic, device_name, index, self._log)
        if device is None:
            return
        device.name = name
        mix.set_params(device, params, self._log)
        root = self._root()
        choose_option(device, "Root", [NOTE_NAMES[root], FLAT_NAMES[root]], self._log)
        choose_option(device, "Scale", ["Minor" if self._minor() else "Major"], self._log)

    def _set_params(self, device, params):
        """mix.set_params, plus ("16ths", n) for a synced Delay's time."""
        for name, value in params:
            if name == "16ths":
                set_sixteenths(device, value, self._log)
            else:
                mix.set_param(device, name, value, self._log)

    # --------------------------------------------------------- DJ effects ---

    def _master_device(self, name):
        return self._device(self.song().master_track, name)

    def _dj_press(self, note):
        self._dj[note] = self._tick
        if note in (STUT4_PAD, STUT8_PAD):
            device = self._master_device("DJ Stutter")
            if device is not None:
                set_sixteenths(device, 4 if note == STUT4_PAD else 2, self._log)
                mix.set_params(device, [("Freeze", True), ("Dry/Wet", 100.0)], self._log)
        elif note == ECHO_PAD:
            self._fades.pop(("DJ Echo", "Dry/Wet"), None)
            device = self._master_device("DJ Echo")
            if device is not None:
                mix.set_param(device, "Dry/Wet", styles.ECHO_WET, self._log)
        elif note == WASH_PAD:
            self._fades.pop(("DJ Wash", "Dry/Wet"), None)
            device = self._master_device("DJ Wash")
            if device is not None:
                mix.set_param(device, "Dry/Wet", styles.WASH_WET, self._log)
        elif note in (LPF_PAD, HPF_PAD):
            name = "DJ LPF" if note == LPF_PAD else "DJ HPF"
            device = self._master_device(name)
            if device is not None:
                self._sweep_endpoints(name, device)
                mix.set_enabled(device, True)
        elif note == DROP_PAD:
            song_track = self._find_track(SONG_TRACK)
            if song_track is not None:
                song_track.mute = True
        elif note == RESET_PAD:
            self._reset_dj()

    def _dj_release(self, note):
        self._dj.pop(note, None)
        if note in (STUT4_PAD, STUT8_PAD):
            if STUT4_PAD in self._dj or STUT8_PAD in self._dj:
                return  # the other stutter is still held
            device = self._master_device("DJ Stutter")
            if device is not None:
                mix.set_params(device, [("Freeze", False), ("Dry/Wet", 0.0)], self._log)
        elif note == ECHO_PAD:
            self._fades[("DJ Echo", "Dry/Wet")] = (self._tick, styles.ECHO_WET)
        elif note == WASH_PAD:
            self._fades[("DJ Wash", "Dry/Wet")] = (self._tick, styles.WASH_WET)
        elif note in (LPF_PAD, HPF_PAD):
            name = "DJ LPF" if note == LPF_PAD else "DJ HPF"
            device = self._master_device(name)
            if device is not None and name in self._sweep_raw:
                mix.set_enabled(device, False)
                freq = mix.find_param(device, "Frequency")
                if freq is not None:
                    freq.value = self._sweep_raw[name][0]
        elif note == DROP_PAD:
            song_track = self._find_track(SONG_TRACK)
            if song_track is not None:
                song_track.mute = False

    def _sweep_endpoints(self, name, device):
        """Raw Frequency values for the filter open and fully swept. Moving the
        raw value evenly sweeps evenly by ear (Live's control is logarithmic)."""
        if name in self._sweep_raw:
            return
        freq = mix.find_param(device, "Frequency")
        if freq is None:
            return
        start, end = styles.LPF_RANGE if name == "DJ LPF" else styles.HPF_RANGE
        mix.set_value(freq, end, name, self._log)
        swept = freq.value
        mix.set_value(freq, start, name, self._log)
        self._sweep_raw[name] = (freq.value, swept)

    def _update_dj(self):
        for note, name in ((LPF_PAD, "DJ LPF"), (HPF_PAD, "DJ HPF")):
            if note not in self._dj or name not in self._sweep_raw:
                continue
            device = self._master_device(name)
            freq = mix.find_param(device, "Frequency") if device is not None else None
            if freq is None:
                continue
            amount = min(1.0, (self._tick - self._dj[note]) / float(styles.FILTER_SWEEP_TICKS))
            start, end = self._sweep_raw[name]
            freq.value = start + (end - start) * amount
        for key, (since, start) in list(self._fades.items()):
            name, param = key
            device = self._master_device(name)
            amount = (self._tick - since) / float(styles.TAIL_TICKS)
            if device is None or amount >= 1.0:
                if device is not None:
                    mix.set_param(device, param, 0.0, self._log)
                del self._fades[key]
                continue
            mix.set_param(device, param, start * (1.0 - amount), self._log)

    def _reset_dj(self):
        self._dj = {RESET_PAD: self._tick}
        self._fades = {}
        master = self.song().master_track
        for name, _, params in styles.DJ_CHAIN:
            device = self._device(master, name)
            if device is not None:
                mix.set_params(device, params, self._log)
                mix.set_enabled(device, name not in ("DJ LPF", "DJ HPF"))  # filters sit switched off
        song_track = self._find_track(SONG_TRACK)
        if song_track is not None:
            song_track.mute = False
        self.show_message("PartyPad: DJ effects reset")

    # --------------------------------------------------------------- chops ---

    def _fire_now(self, slot):
        """Fire a clip slot straight away, whatever the launch quantization."""
        try:
            slot.fire(launch_quantization=Live.Song.Quantization.q_no_q)
        except Exception:
            song = self.song()
            previous = song.clip_trigger_quantization
            song.clip_trigger_quantization = Live.Song.Quantization.q_no_q
            try:
                slot.fire()
            finally:
                song.clip_trigger_quantization = previous

    def _rec_slot(self):
        track = self._find_track(CHOP_REC_TRACK)
        if track is None or not len(track.clip_slots):
            return None, None
        return track, track.clip_slots[0]

    def _start_chop(self, note):
        if self._rec is not None:
            return
        track, slot = self._rec_slot()
        if slot is None or self._chops_rack() is None:
            self.show_message("PartyPad: hold the top-right button to build the set first")
            return
        if slot.has_clip:
            slot.delete_clip()
        track.arm = True  # exclusive arm may have taken it off
        self._fire_now(slot)
        self._rec = {"note": note, "stage": "recording", "due": None}
        self.show_message("PartyPad: recording chop - let go to finish")

    def _cancel_chop(self):
        _, slot = self._rec_slot()
        if slot is not None:
            slot.stop()
            if slot.has_clip:
                slot.delete_clip()
        self._rec = None

    def _close_chop(self):
        _, slot = self._rec_slot()
        if slot is None:
            self._rec = None
            return
        self._fire_now(slot)  # ends the take (the track is silent if it plays)
        self._rec["stage"] = "closing"
        self._rec["due"] = self._tick + CHOP_DELAY_TICKS

    def _update_rec(self):
        rec = self._rec
        if rec is None or rec["stage"] != "closing":
            return
        _, slot = self._rec_slot()
        if slot is not None and slot.has_clip and slot.clip.is_playing:
            slot.stop()
        if self._tick < rec["due"]:
            return
        self._rec = None
        if slot is None or not slot.has_clip:
            self._log("chop take vanished")
            return
        path = slot.clip.file_path
        try:
            self._load_chop(rec["note"], path)
        except Exception as e:
            self._log("chop load error: %r" % (e,))
            self.show_message("PartyPad: couldn't load the chop (%s)" % (e,))
            return
        slot.delete_clip()  # the Simpler keeps the recorded file
        self._rescan()

    def _load_chop(self, note, path):
        rack = self._chops_rack()
        drum_pad = rack.drum_pads[note]
        if not len(drum_pad.chains):
            rack.insert_chain(len(rack.chains))
            rack.chains[-1].in_note = note
        chain = drum_pad.chains[0]
        while len(chain.devices):
            chain.delete_device(0)
        chain.insert_device("Simpler", 0)
        simpler = chain.devices[0]
        simpler.replace_sample(path)
        simpler.playback_mode = Live.SimplerDevice.PlaybackMode.one_shot
        sample = simpler.sample
        sample.warping = False
        start, end = self._trim(path, sample.length)
        if start >= sample.end_marker:
            sample.end_marker = end
            sample.start_marker = start
        else:
            sample.start_marker = start
            sample.end_marker = end
        chain.choke_group = CHOP_CHOKE_GROUP
        try:
            chain.name = "Vox %d" % (CHOP_PADS.index(note) + 1)
        except Exception:
            pass
        self._log("chop on pad %d: frames %d-%d of %d" % (note, start, end, sample.length))
        self.show_message("PartyPad: chop ready - press the pad to play it")

    def _trim(self, path, length):
        """(start, end) frames without the silence either side of the take."""
        result = phrases.envelope(path)
        if result is None:
            return 0, length - 1
        _, frames, window, env = result
        top = max(env) if env else 0.0
        if top <= 0.0:
            return 0, length - 1
        threshold = top * 10 ** (CHOP_SILENCE_DB / 20.0)
        loud = [i for i, v in enumerate(env) if v >= threshold]
        start = max(0, (loud[0] - CHOP_PRE_WINDOWS) * window)
        end = min(length - 1, (loud[-1] + CHOP_TAIL_WINDOWS) * window)
        return start, max(end, start + 1)

    def _clear_chop(self, note):
        rack = self._chops_rack()
        if rack is None:
            return
        for chain in rack.drum_pads[note].chains:
            while len(chain.devices):
                chain.delete_device(0)
        self._rescan()

    # ---------------------------------------------------------------- song ---

    def _song_slots(self):
        track = self._find_track(SONG_TRACK)
        return list(track.clip_slots) if track is not None else []

    def _toggle_song(self):
        track = self._find_track(SONG_TRACK)
        if track is None:
            return
        slots = self._song_slots()
        if any(s.has_clip and (s.clip.is_playing or s.clip.is_triggered) for s in slots):
            track.stop_all_clips()
            return
        slot = next((s for s in slots if s.has_clip), None)
        if slot is None:
            self.show_message("PartyPad: drop the song's audio file on the Song track first")
            return
        self._fire_now(slot)

    def _watch_song(self):
        """A new audio file on the Song track sets the tempo, once Live has
        warped it."""
        paths = set()
        for slot in self._song_slots():
            if slot.has_clip and slot.clip.is_audio_clip:
                paths.add(slot.clip.file_path)
        if self._song_clips is not None and paths - self._song_clips:
            self._song_tempo_due = self._tick + SONG_TEMPO_DELAY_TICKS
        self._song_clips = paths
        if self._song_tempo_due is not None and self._tick >= self._song_tempo_due:
            self._song_tempo_due = None
            self._tempo_from_song()

    def _tempo_from_song(self):
        clip = next((s.clip for s in self._song_slots()
                     if s.has_clip and s.clip.is_audio_clip), None)
        if clip is None:
            return
        if not clip.warping:
            self.show_message("PartyPad: the song isn't warped, so its tempo is unknown "
                              "(switch Warp on in its clip view, or tap the tempo)")
            return
        bpm = None
        try:
            markers = list(clip.warp_markers)
            if len(markers) >= 2:
                first, last = markers[0], markers[-1]
                seconds = last.sample_time - first.sample_time
                if seconds > 0:
                    bpm = 60.0 * (last.beat_time - first.beat_time) / seconds
        except Exception as e:
            self._log("warp markers unavailable: %r" % (e,))
        if bpm is None:
            try:
                seconds = clip.sample_length / float(clip.sample_rate)
                bpm = 60.0 * (clip.end_marker - clip.start_marker) / seconds
            except Exception as e:
                self._log("couldn't work out the song's tempo: %r" % (e,))
                return
        if 20.0 <= bpm <= 999.0:
            self.song().tempo = round(bpm, 2)
            self.show_message("PartyPad: tempo %.1f from the song" % bpm)
            self._log("tempo %.2f from %s" % (bpm, clip.name))

    # ----------------------------------------------------------------- mic ---

    def _next_mic_input(self):
        mic = self._find_track(MIC_TRACK)
        if mic is None:
            return
        if "ext" not in mic.input_routing_type.display_name.lower():
            route_input(mic, "Ext. In", None, self._log)
        channels = list(mic.available_input_routing_channels)
        if not channels:
            return
        names = [c.display_name for c in channels]
        current = mic.input_routing_channel.display_name
        index = (names.index(current) + 1) % len(channels) if current in names else 0
        mic.input_routing_channel = channels[index]
        self.show_message("PartyPad: mic input %s" % names[index])

    # -------------------------------------------------------------- genres ---

    def _load_genre(self, index):
        song = self.song()
        song.set_data(shared.GENRE_KEY, index)
        shared.refresh_user_presets(song)
        kit = shared.resolve_genre(index)["kit"]
        track = self._find_track(PADS_TRACK)
        if track is None or kit is None:
            self._log("no Pads track or kit for genre %d" % (index + 1))
            return
        try:
            shared.replace_instrument(song, track, kit)
        except Exception as e:
            self._log("kit load error: %r" % (e,))
            return
        self.schedule_message(2, self._rescan)
        self.show_message("PartyPad: %s kit" % shared.GENRES[index]["name"])
        # Live's browser lags while it indexes the User Library: retry if a
        # saved kit hasn't shown up yet
        if shared.missing_presets(index) and self._genre_retries < GENRE_RETRY_MAX:
            self._genre_retries += 1

            def retry():
                if shared.current_genre(self.song()) == index:
                    self._load_genre(index)
            self.schedule_message(GENRE_RETRY_TICKS, retry)
        else:
            self._genre_retries = 0

    # ----------------------------------------------------------- build set ---

    def _build_set(self):
        song = self.song()
        wanted = [(SONG_TRACK, "audio"), (MIC_TRACK, "audio"), (CHOP_REC_TRACK, "audio"),
                  (PADS_TRACK, "midi"), (CHOPS_TRACK, "midi")]
        missing = [(name, kind) for name, kind in wanted if self._find_track(name) is None]
        if len(song.tracks) + len(missing) > MAX_TRACKS:
            self.show_message("PartyPad: needs %d new tracks (%s) but this set has %d of Lite's "
                              "%d - delete %d track(s), or use File > New Live Set" % (
                                  len(missing), ", ".join(n for n, _ in missing), len(song.tracks),
                                  MAX_TRACKS, len(song.tracks) + len(missing) - MAX_TRACKS))
            return
        try:
            for name, kind in missing:
                if kind == "audio":
                    song.create_audio_track(-1)
                else:
                    song.create_midi_track(-1)
                song.tracks[-1].name = name
        except Exception as e:
            self._log("build error: %r" % (e,))
            self.show_message("PartyPad: build error, see Log.txt (%s)" % (e,))
            return
        self.show_message("PartyPad: building...")
        # A new track's input list is only filled in a moment after it's made
        self.schedule_message(5, self._finish_build)

    def _finish_build(self):
        song = self.song()
        log = self._log
        try:
            mic = self._find_track(MIC_TRACK)
            if "ext" not in mic.input_routing_type.display_name.lower():
                route_input(mic, "Ext. In", DEFAULT_MIC_INPUT, log)
            mic.current_monitoring_state = MONITOR_IN
            self._ensure_chain(mic, styles.VOCAL_CHAIN)

            rec = self._find_track(CHOP_REC_TRACK)
            route_input(rec, MIC_TRACK, "Post FX", log, track_only=True)
            rec.current_monitoring_state = MONITOR_OFF
            rec.mixer_device.volume.value = rec.mixer_device.volume.min
            rec.arm = True

            for name in (PADS_TRACK, CHOPS_TRACK):
                track = self._find_track(name)
                route_input(track, "LPX MIDI", None, log)
                track.current_monitoring_state = MONITOR_IN
            chops = self._find_track(CHOPS_TRACK)
            if shared.find_drum_rack(chops.devices) is None:
                chops.insert_device("Drum Rack", 0)

            master = song.master_track
            self._ensure_chain(master, styles.DJ_CHAIN)
            for name in ("DJ LPF", "DJ HPF"):
                device = self._device(master, name)
                if device is not None:
                    mix.set_enabled(device, False)
            for name, sixteenths in (("DJ Echo", styles.ECHO_DJ_SIXTEENTHS),):
                device = self._device(master, name)
                if device is not None:
                    set_sixteenths(device, sixteenths, log)

            self._apply_key()
            self._apply_style()
            if shared.find_drum_rack(self._find_track(PADS_TRACK).devices) is None:
                self._load_genre(shared.current_genre(song))
            self._rescan()
            song.view.selected_track = mic
            self.show_message("PartyPad: set built - pick a key, a style, and sing!")
            log("build complete")
        except Exception as e:
            log("finish build error: %r" % (e,))
            self.show_message("PartyPad: build error, see Log.txt (%s)" % (e,))

    def _ensure_chain(self, track, chain):
        """Insert each (name, device, params) that the track doesn't have yet,
        in chain order; ones already there keep their settings."""
        index = 0
        for name, device_name, params in chain:
            device = self._device(track, name)
            if device is None:
                device = mix.insert(track, device_name, index, self._log)
                if device is None:
                    continue
                device.name = name
                mix.set_params(device, params, self._log)
            index = list(track.devices).index(device) + 1

    # ---------------------------------------------------------------- LEDs ---

    def _set_led(self, note, color, channel=STATIC, force=False):
        value = (channel, color)
        if not force and self._led_cache.get(note) == value:
            return
        self._led_cache[note] = value
        self._send_midi(((CC if note in CC_BUTTONS else NOTE_ON) | channel, note, color))

    def _refresh_leds(self, force=False):
        try:
            self._do_refresh_leds(force)
        except Exception as e:
            self._log("LED error: %r" % (e,))

    def _do_refresh_leds(self, force):
        song = self.song()
        led = lambda note, color, channel=STATIC: self._set_led(note, color, channel, force)
        root = self._root()
        for row in (7, 8):
            for col in range(1, 8):
                note = pad(row, col)
                if note not in KEY_PADS:
                    led(note, OFF)
                elif KEY_PADS[note] == root:
                    led(note, GREEN)
                else:
                    led(note, WHITE_DIM if row == 7 else BLUE_DIM)
        led(pad(8, 8), OFF)
        led(MODE_PAD, PURPLE if self._minor() else YELLOW)

        style = self._style()
        for i, note in enumerate(STYLE_PADS):
            color = styles.STYLES[i][1]
            led(note, color if i == style else color + 2)
        led(BIG_VERB_PAD, CYAN if song.get_data(KEY_BIG_VERB, False) else CYAN_DIM)

        for note in DJ_PADS:
            if note == RESET_PAD:
                led(note, WHITE if note in self._dj else WHITE_DIM)
            else:
                led(note, ORANGE if note in self._dj else ORANGE_DIM)

        for i, note in enumerate(DRUM_PAD_NOTES):
            led(note, DRUM_ROW_COLORS[i // 4])
        for note in CHOP_PADS:
            if self._rec is not None and self._rec["note"] == note:
                led(note, RED, PULSE)
            elif note in self._full_chops:
                led(note, PINK)
            else:
                led(note, PINK_DIM)

        genre = shared.current_genre(song)
        for i, button in enumerate(GENRE_BUTTONS):
            color = shared.GENRES[i]["color"]
            led(button, color if i == genre else color + 2)
        song_track = self._find_track(SONG_TRACK)
        playing = song_track is not None and song_track.playing_slot_index >= 0
        led(BTN_SONG, GREEN if playing else GREEN_DIM)
        mic = self._find_track(MIC_TRACK)
        level = mic.output_meter_level if mic is not None else 0.0
        led(BTN_MIC, RED if level > 0.9 else YELLOW if level > 0.5 else
            GREEN if level > 0.05 else GREEN_DIM if mic is not None else OFF)
        led(BTN_TUNE, GREEN if self._tune_on() else RED_DIM)
        led(BTN_BUILD, WHITE_DIM)
        led(BTN_CHOP_REC, RED if self._mod == "rec" else RED_DIM)
        led(BTN_CHOP_CLEAR, WHITE if self._mod == "clear" else WHITE_DIM)
        led(BTN_TAP, WHITE_DIM)
        led(BTN_TEMPO_UP, WHITE_DIM)
        led(BTN_TEMPO_DOWN, WHITE_DIM)
        led(BTN_SONG_TEMPO, GREEN_DIM)
        for button in (29, 19):
            led(button, OFF)


# ---------------------------------------------------------------- helpers ---

def route_input(track, type_contains, channel_name, log, track_only=False):
    """Set a track's input by name (an exact match first, then a partial one)."""
    if track is None:
        return
    try:
        types = list(track.available_input_routing_types)
        # Tracks are listed numbered ("2-Mic"), so match the name after the number too
        wanted = type_contains.lower()
        match = next((rt for rt in types
                      if rt.display_name.lower() == wanted
                      or rt.display_name.lower().split("-", 1)[-1] == wanted), None)
        if match is None and track_only:
            log("no track %r to take %s's input from; options: %r" % (
                type_contains, track.name, [r.display_name for r in types]))
            return
        if match is None:
            match = next((rt for rt in types
                          if type_contains.lower() in rt.display_name.lower()), None)
        if match is None:
            log("no input %r for %s; options: %r" % (
                type_contains, track.name, [r.display_name for r in types]))
            return
        track.input_routing_type = match
        if channel_name:
            channels = list(track.available_input_routing_channels)
            for ch in channels:
                if ch.display_name == channel_name:
                    track.input_routing_channel = ch
                    break
            else:
                log("no input channel %r for %s; options: %r" % (
                    channel_name, track.name, [c.display_name for c in channels]))
    except Exception as e:
        log("routing error on %s: %r" % (track.name, e))


def choose_option(device, param_name, names, log):
    """Pick a list parameter's option by name: an exact match to any of names
    first, then one starting with the first name."""
    p = mix.find_param(device, param_name)
    if p is None:
        log("%s has no parameter %r" % (device.name, param_name))
        return False
    items = [str(i) for i in p.value_items]
    for name in names:
        for i, item in enumerate(items):
            if item.lower() == name.lower():
                p.value = p.min + i
                return True
    for i, item in enumerate(items):
        if item.lower().startswith(names[0].lower()):
            p.value = p.min + i
            return True
    log("%s %s: none of %r in %r" % (device.name, param_name, names, items))
    return False


_logged_divisions = set()


def set_sixteenths(device, sixteenths, log):
    """Set a synced Delay's time to a number of 16th notes (both sides)."""
    for side in ("L", "R"):
        p = mix.find_param(device, "%s 16th" % side)
        if p is None:
            continue
        items = [str(i) for i in p.value_items] if p.is_quantized else []
        if items and device.class_name not in _logged_divisions:
            _logged_divisions.add(device.class_name)
            log("Delay divisions: %r" % items)
        fraction = {1: "1/16", 2: "1/8", 3: "3/16", 4: "1/4", 8: "1/2", 16: "1"}.get(sixteenths)
        names = [str(sixteenths)] + ([fraction] if fraction else [])
        if items and any(i in names for i in items):
            p.value = p.min + next(k for k, i in enumerate(items) if i in names)
        else:
            mix.set_value(p, float(sixteenths), "%s %s 16th" % (device.name, side), log)
