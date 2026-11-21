"""
LoopPad - Launchpad X live-looping control surface for Ableton Live 12 Lite.

Runs the Launchpad X in Programmer mode on the "LPX MIDI" port.
Pad notes in Programmer mode are row*10 + col (row 1 = bottom, col 1 = left).

Grid pads are row*10 + col; the round buttons follow the same numbering
(right column = col 9, top row = row 9) but send CCs.

    col:   1     2     3     4     5         6     7     8       round
  row 9   .     .     .     .     .         .     .     .       BUILD SET (top right, hold 2s)
  row 8   REC   REC   REC   REC   1 bar     2 bars 4 bars 8 bars  TRANSPORT play/stop
  row 7   SYNC  SYNC  SYNC  SYNC  SYNC ALL  .     .     .       METRONOME
  row 6   CLEAR CLEAR CLEAR CLEAR CLEAR ALL .     .     .       TAP TEMPO
  row 5   QUANT QUANT QUANT QUANT AUTO-Q    .     .     .       TEMPO +1
  row 4   drum  drum  drum  drum  GENRE 1   GENRE 2 GENRE 3 GENRE 4  TEMPO -1
  row 3   drum  drum  drum  drum  SOURCE    SLICE SNAP  PITCH
  row 2   drum  drum  drum  drum  CHOP 5    CHOP 6 CHOP 7 CHOP 8  SAMPLE REC
  row 1   drum  drum  drum  drum  CHOP 1    CHOP 2 CHOP 3 CHOP 4  CLEAR SAMPLE (hold)
          Loop1 Loop2 Loop3 Loop4

Each loop row carries on to the right with its version for all loops (the
REC row with the recording length).
LENGTH: pick the fixed recording length. Tap the lit one again for free length.
GENRE 1-4: (see GENRES in shared.py) loads the genre's drum kit onto Pads,
        its first keys sound onto Keys, and its Guitar effects (after the
        Guitar track's Tuner, which always stays). Keys ducks from the kick.
SAMPLER: SAMPLE REC records the SOURCE for the LENGTH you've picked (or tap
        again to stop). Live Lite allows only 8 tracks, so the Guitar track
        borrows that input for the take (guitar is silent for those bars) and
        holds the sample clip. Or drag an audio file (spoken word, a record...)
        into Guitar's top clip slot instead. Either way the sample is split
        into 8 equal chops on the Sampler track's Drum Rack, played from CHOP 1-8 one at a time (a new
        chop cuts off the last). They stay through genre changes, and loop like
        anything else.
  SOURCE: what SAMPLE REC records: white = the session mix (everything you
        hear), magenta = the mic only (input 3, the AT2020 USB via an aggregate
        device).
  SLICE: how the sample is cut. Dim = 8 equal chops; yellow = phrases: the
        sample is split at its gaps of silence into whole phrases (or words,
        if there aren't 8 phrases), one per pad, so nothing starts halfway
        through a sound. Files that aren't WAVs fall back to Live's transient
        detection. Toggling re-chops the current sample straight away.
  PITCH: the Launchkey keys steer the chops' pitch (the LoopPitch script, on
        the "Launchkey MIDI" port): hold a key and the chops play at that note,
        C3 being the sample's own pitch, and with no key held at their own
        pitch. Tape-style, so higher is also faster. The keys don't play the
        Keys track while it's on.
  SNAP: Auto Shift after the chops snaps every note in them to the song's
        key (Live's Scale chooser), so a sample with its own melody lands in
        tune with the track. Works with or without PITCH (a transposed chop is
        snapped too). Best on a clean single voice; speech and full mixes can
        warble. Auto Shift delays the chops a little, so it's only on the
        track while SNAP is on.
CLEAR SAMPLE: hold to delete the sample and its chops.

Each loop is the clip in the first Session slot of its "Loop N" track
(Live Lite has no Looper device, so loops are Session clips).
  REC:   empty -> record a fixed-length loop (LENGTH column, default 8 bars) that
         closes and plays by itself. Press again while recording to close early.
  SYNC:  bar-synced mute. Tap to queue a mute/unmute; every queued change lands
         together on the next bar, and loops keep running so they never drift.
         Tap again before the bar to cancel. (On a stopped loop it relaunches it.)
  CLEAR: hold to delete the loop. Tap while recording to abort the take.
  SYNC ALL: mute every loop on the next bar, or bring them all back if they're
         all muted already.
  CLEAR ALL: hold 1s to delete every loop.
  AUTO-QUANTIZE (global): while on, every loop is quantized the moment its
         recording closes, so it plays back tight from the first repeat.
  QUANT: snap the loop's hits to a 1/16 grid (moves the audio's warp markers;
         Cmd+Z in Live undoes it). Lights bright once the loop is quantized.
Drum loops: a loop recorded while the Pads drums were sounding is marked
as a drum loop (its REC pad lights orange instead of red). The sidechain
follows the live drums while you're playing them (any hit in the last few
seconds), else the first playing, unmuted drum loop. It ducks the Keys track
and every loop that isn't a drum loop. Mix setup lives in mix.py.
Drum pads are NOT handled by this script: they pass straight through to the
"Pads" track (set the LPX MIDI port's Track switch On in Live's settings).
"""

import Live
from _Framework.ControlSurface import ControlSurface
from . import shared
from . import mix
from . import phrases
from .shared import (GENRES, GUITAR_TRACK_NAME, PADS_TRACK_NAME, KIT_TRACK_NAME,
                     SUB_TRACK_NAME, SAMPLER_TRACK_NAME, KEYS_TRACK_NAME, LOOP_TRACK_NAMES)

# ---------------------------------------------------------------- config ---

NUM_LOOPS = 4
LEGACY_DRUMS_TRACK_NAME = "Drums"  # earlier name of the Pads track
LOOP_BUS_NAME = "Loop Bus"
LOOP_SLOT = 0  # Session scene used for each loop

ROW_REC, ROW_PLAY, ROW_CLEAR, ROW_QUANTIZE = 8, 7, 6, 5
LOOP_ROWS = (ROW_REC, ROW_PLAY, ROW_CLEAR, ROW_QUANTIZE)

# Quantize pad: grid and strength (1.0 = fully on the grid)
QUANTIZE_GRID = Live.Song.RecordingQuantization.rec_q_sixtenth
QUANTIZE_AMOUNT = 1.0
AUTO_QUANT_KEY = "looppad_auto_quantize"
# Wait this many display ticks after a take closes before auto-quantizing,
# giving Live a moment to analyse the new recording's transients
AUTO_QUANT_DELAY_TICKS = 20  # ~2 s

# Column 5 of each loop row: the "all loops" version of that row
SYNC_ALL_PAD = ROW_PLAY * 10 + 5
CLEAR_ALL_PAD = ROW_CLEAR * 10 + 5
AUTO_QUANT_PAD = ROW_QUANTIZE * 10 + 5

# Loop length, along the REC row: pad -> bars. Tapping the selected length again = free length (None).
LENGTH_PADS = {85: 1, 86: 2, 87: 4, 88: 8}
DEFAULT_LOOP_LENGTH = 8

# Genres numbered 1-4 left to right, above the chops
GENRE_PADS = [45, 46, 47, 48]
# Retry a genre load this often while Live's browser hasn't listed a saved preset yet
GENRE_RETRY_TICKS = 30  # ~3 s
GENRE_RETRY_MAX = 5

# SOURCE: what SAMPLE REC records: the session mix (Resampling) or the mic
# only (input 3, the AT2020 USB via the Scarlett + AT2020 aggregate device)
SOURCE_PAD = 35
SOURCE_KEY = "looppad_sample_source"  # "mix" or "mic"
MIC_INPUT = "3"
# PITCH: the held Launchkey key transposes the chops (LoopPitch does the work)
PITCH_PAD = 38  # far right of its row, apart from SOURCE
PITCH_KEY = shared.PITCH_KEY
OLD_PITCH_DEVICE_NAME = "Pitch"  # the Auto Shift PITCH used before LoopPitch
# SLICE: equal chops, or each chop start moved to the nearest transient
# that Simpler detects (within half a chop of the equal position)
SLICE_PAD = 36
SLICE_KEY = "looppad_slice_transient"
SLICE_SENSITIVITY = 0.6  # Simpler's transient sensitivity, 0-1 (higher = more hits)
SLICE_RETRY_TICKS = 5    # transient analysis can lag a fresh sample: retry this often
SLICE_MAX_TRIES = 6      # then fall back to equal chops
SLICE_MIN_SECONDS = 0.25  # a transient chop plays at least this long
# SNAP: Auto Shift (audio mode, Quantizer on) after the chops, following the
# song's key and scale
SNAP_PAD = 37
SNAP_KEY = "looppad_snap"
SNAP_DEVICE_NAME = "Snap"
SNAP_PARAMS = [("Quantizer On", True), ("Scale Aware", True), ("Strength", 100.0),
               ("Smooth On", False), ("Formant Follow", True), ("Latch", False),
               ("Dry/Wet", 100.0)]

# Sampler: 8 chop pads (bottom-right, chop 1 bottom-left), played straight
# into the Sampler track's Drum Rack (the Pads kit ignores those notes)
CHOP_PADS = [15, 16, 17, 18, 25, 26, 27, 28]
SAMPLE_PATH_KEY = "looppad_sample_path"
NUM_CHOPS = len(CHOP_PADS)
CHOP_DELAY_TICKS = 5  # after a sample closes, before chopping it
# All chops share one choke group, so a new chop cuts off the last (single voice).
# 16 is the highest group, clear of the hi-hat chokes kits use.
CHOP_CHOKE_GROUP = 16
# Chop level in dB: 0 plays it back as loud as it was sampled
CHOP_VOLUME_DB = 0.0

# Round buttons (CCs in Programmer mode)
BTN_TRANSPORT, BTN_METRO, BTN_TAP, BTN_TEMPO_UP, BTN_TEMPO_DOWN = 89, 79, 69, 59, 49
BTN_SAMPLE_REC, BTN_CLEAR_SAMPLE = 29, 19
BTN_BUILD = 98  # top-right
CC_BUTTONS = [row * 10 + 9 for row in range(1, 9)] + list(range(91, 99))

# Drum-loop detection: drum tracks louder than this (0-1 meter) for this many
# display ticks while a loop records make it a drum loop
DRUM_METER_THRESHOLD = 0.3
DRUM_LOOP_MIN_TICKS = 4
DRUM_LOOPS_KEY = "looppad_drum_loops"
DRY_LOOPS_KEY = "looppad_dry_loops"  # recorded with nothing ducking them
# The live drums drive the sidechain for this long after their last hit
# (over any drum loop), so playing along ducks from your kick
LIVE_DRUMS_TICKS = 40  # ~4 s

# Hold thresholds in display ticks (Live calls update_display roughly every 100ms)
CLEAR_HOLD_TICKS = 5
CLEAR_ALL_HOLD_TICKS = 10
BUILD_HOLD_TICKS = 20

# Novation palette indices
OFF = 0
WHITE_DIM, WHITE = 1, 3
RED, RED_DIM = 5, 7
ORANGE = 9
YELLOW, YELLOW_DIM = 13, 15
LIME = 17
GREEN, GREEN_DIM = 21, 23
CYAN, CYAN_DIM = 37, 39
BLUE, BLUE_DIM = 45, 47
PURPLE, PURPLE_DIM = 49, 51
MAGENTA, MAGENTA_DIM = 53, 55

# LED channels in Programmer mode (0-based MIDI channel)
STATIC, FLASH, PULSE = 0, 1, 2

# Bottom-left 4x4 drum pad colours, bottom row first
DRUM_ROW_COLORS = [ORANGE, YELLOW, LIME, PURPLE]

SYSEX_HEADER = (0xF0, 0x00, 0x20, 0x29, 0x02, 0x0C)
SYSEX_PROGRAMMER_MODE = SYSEX_HEADER + (0x0E, 0x01, 0xF7)
SYSEX_LIVE_MODE = SYSEX_HEADER + (0x0E, 0x00, 0xF7)

NOTE_ON = 0x90
CC = 0xB0

MONITOR_IN, MONITOR_AUTO, MONITOR_OFF = 0, 1, 2

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def pad(row, col):
    return row * 10 + col


# The 16 Launchpad notes of the bottom-left 4x4, in Drum Rack pad order (C1 upward)
DRUM_PAD_NOTES = [pad(r, c) for r in range(1, 5) for c in range(1, 5)]
DRUM_RACK_FIRST_NOTE = 36  # C1


class LoopPad(ControlSurface):

    def __init__(self, c_instance):
        self._handled_notes = self._build_handled_notes()
        ControlSurface.__init__(self, c_instance)
        self._tick = 0
        self._pressed = {}  # note -> tick when pressed
        self._hold_fired = set()
        self._led_cache = {}
        self._loop_tracks = [None] * NUM_LOOPS
        self._armed_by_us = [False] * NUM_LOOPS
        self._loop_length = DEFAULT_LOOP_LENGTH
        self._quantized = [False] * NUM_LOOPS
        self._auto_quantize = bool(self.song().get_data(AUTO_QUANT_KEY, False))
        self._auto_quant_due = [None] * NUM_LOOPS  # tick at which to quantize a new take
        try:
            self._drum_loops = set(int(x) for x in self.song().get_data(DRUM_LOOPS_KEY, []) or [])
        except Exception:
            self._drum_loops = set()
        try:
            self._dry_loops = set(int(x) for x in self.song().get_data(DRY_LOOPS_KEY, []) or [])
        except Exception:
            self._dry_loops = set()
        self._rec_drum_ticks = [0] * NUM_LOOPS
        self._rec_ducked_ticks = [0] * NUM_LOOPS
        self._prev_state = [None] * NUM_LOOPS
        self._duck_source = None
        self._kick_chain = None  # name of the Pads kit's kick chain, for the sidechain
        self._pending_mute = [None] * NUM_LOOPS  # target mute state, applied on the next bar
        self._pending_boundary = None  # song time (beats) of the bar line to apply at
        self._last_song_time = None
        self._song_time_delta = 0.0
        self._sample_prev_state = None
        self._guitar_input = None  # (routing type, channel) to restore after sampling
        self._chop_due = None
        self._rechop_due = None  # retry tick while transient analysis catches up
        self._slice_tries = 0
        self._chop_count = 0
        self._genre_retries = 0
        self._pads_played_tick = None  # last tick the live drums were heard
        self.log_message("LoopPad: init")
        self._enter_programmer_mode()
        self._rescan()
        self._refresh_leds(force=True)
        self.show_message("LoopPad ready")

    # ------------------------------------------------------ live plumbing ---

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

    def _build_handled_notes(self):
        # Grab every grid pad except the drum and chop pads, so unassigned pads
        # stay silent instead of passing through to the Pads track.
        return [pad(row, col) for row in range(1, 9) for col in range(1, 9)
                if pad(row, col) not in DRUM_PAD_NOTES + CHOP_PADS]

    def build_midi_map(self, midi_map_handle):
        # Only forward the notes we use. Everything else (the drum pads) is left
        # unforwarded so Live passes it through to tracks.
        handle = self._c_instance.handle()
        for note in self._handled_notes:
            Live.MidiMap.forward_midi_note(handle, midi_map_handle, 0, note)
        for button in CC_BUTTONS:
            Live.MidiMap.forward_midi_cc(handle, midi_map_handle, 0, button)

    def receive_midi(self, midi_bytes):
        if len(midi_bytes) != 3:
            return
        status, note, velocity = midi_bytes
        kind = status & 0xF0
        if kind == CC and note in CC_BUTTONS:
            pressed = velocity > 0  # round buttons: same numbering as the grid
        elif kind in (0x90, 0x80) and note in self._handled_notes:
            pressed = kind == 0x90 and velocity > 0
        else:
            return
        try:
            if pressed:
                self._pressed[note] = self._tick
                self._hold_fired.discard(note)
                self._on_press(note)
            else:
                held = self._pressed.pop(note, None)
                fired = note in self._hold_fired
                self._hold_fired.discard(note)
                if held is not None:
                    self._on_release(note, fired)
        except Exception as e:
            self.log_message("LoopPad: button error: %r" % (e,))
        self._refresh_leds()

    def update_display(self):
        ControlSurface.update_display(self)
        self._tick += 1
        self._check_holds()
        self._auto_disarm()
        self._check_pending_mutes()
        self._track_drum_loops()
        self._track_sample()
        if self._tick % 3 == 0:
            self._update_sidechain()
        if self._tick % 10 == 0:
            self._rescan()
        self._refresh_leds()

    def _enter_programmer_mode(self):
        self._send_midi(SYSEX_PROGRAMMER_MODE)
        self._led_cache = {}

    # ---------------------------------------------------- track discovery ---

    def _find_track(self, name):
        for track in self.song().tracks:
            if track.name.strip().lower() == name.lower():
                return track
        return None

    def _rescan(self):
        try:
            for i, name in enumerate(LOOP_TRACK_NAMES):
                self._loop_tracks[i] = self._find_track(name)
            pads_track = self._find_track(PADS_TRACK_NAME) or self._find_track(LEGACY_DRUMS_TRACK_NAME)
            if pads_track is not None:
                self._strip_saved_chops(pads_track)
                self._remap_drum_rack(pads_track)
            self._kick_chain = self._find_kick_chain()
            self._chop_count = self._count_chops()
        except Exception as e:
            self.log_message("LoopPad: rescan error: %r" % (e,))

    def _strip_saved_chops(self, track):
        """Chops live on the Sampler track now. A kit saved from Pads back when
        they lived there brings old "Chop N" pads with it: remove them."""
        rack = shared.find_drum_rack(track.devices)
        if rack is None:
            return
        removed = 0
        for i in reversed(range(len(rack.chains))):
            chain = rack.chains[i]
            if not chain.name.startswith("Chop ") or not len(chain.devices):
                continue  # already silenced (Live won't delete Drum Rack chains)
            try:
                rack.delete_chain(i)
            except Exception:
                while len(chain.devices):  # silence it instead
                    chain.delete_device(0)
            removed += 1
        if removed:
            self.log_message("LoopPad: removed %d old chop pads from the %s kit" % (removed, track.name))

    def _remap_drum_rack(self, track):
        """Make the Drum Rack's bottom 16 pads (C1..D#2) respond to the
        Launchpad's bottom-left 4x4 programmer-mode notes. Re-applied whenever
        a fresh kit is loaded onto the Pads track."""
        rack = shared.find_drum_rack(track.devices)
        if rack is None:
            return
        pads = rack.drum_pads
        # Notes 11-34 are never used by normal kits; if any hold chains we've
        # already remapped this rack.
        if any(len(pads[n].chains) for n in DRUM_PAD_NOTES[:12]):
            return
        moves = []
        for i, target in enumerate(DRUM_PAD_NOTES):
            for chain in pads[DRUM_RACK_FIRST_NOTE + i].chains:
                moves.append((chain, target))
        if not moves:
            return
        for chain, target in moves:  # ascending order, so targets 41-44 are vacated first
            chain.in_note = target
        self.log_message("LoopPad: remapped %d drum chains to Launchpad pads" % len(moves))
        self.show_message("LoopPad: Drum Rack mapped to Launchpad pads")

    # ----------------------------------------------------------- loop state ---

    def _slot(self, loop):
        track = self._loop_tracks[loop]
        if track is None or len(track.clip_slots) <= LOOP_SLOT:
            return None
        return track.clip_slots[LOOP_SLOT]

    def _loop_state(self, loop):
        """Returns one of 'none' (no track), 'empty', 'queued', 'recording',
        'playing', 'stopped'."""
        slot = self._slot(loop)
        if slot is None:
            return "none"
        if slot.is_recording:
            return "recording"
        if slot.is_triggered:
            return "queued"
        if not slot.has_clip:
            return "empty"
        if slot.is_playing:
            return "playing"
        return "stopped"

    def _auto_disarm(self):
        # Keep a loop's track armed only while it's queued or recording
        for loop in range(NUM_LOOPS):
            if not self._armed_by_us[loop]:
                continue
            track = self._loop_tracks[loop]
            if track is None:
                self._armed_by_us[loop] = False
                continue
            if self._loop_state(loop) not in ("queued", "recording"):
                track.arm = False
                self._armed_by_us[loop] = False

    def _clear_loop(self, loop):
        slot = self._slot(loop)
        if slot is None:
            return
        track = self._loop_tracks[loop]
        if slot.is_recording or slot.is_triggered or slot.is_playing:
            slot.stop()
        if slot.has_clip:
            slot.delete_clip()
        if self._armed_by_us[loop]:
            track.arm = False
            self._armed_by_us[loop] = False

    # ------------------------------------------------------------ buttons ---

    def _on_press(self, note):
        row, col = divmod(note, 10)
        song = self.song()
        if note in GENRE_PADS:
            index = GENRE_PADS.index(note)
            if index < len(GENRES):
                self._load_genre(index)
            return
        if note == BTN_SAMPLE_REC:
            self._sample_rec()
            return
        if note == SOURCE_PAD:
            source = "mix" if self._sample_source() == "mic" else "mic"
            song.set_data(SOURCE_KEY, source)
            self.show_message("LoopPad: SAMPLE REC records %s" % (
                "the mic only" if source == "mic" else "the session mix"))
            return
        if note == PITCH_PAD:
            self._toggle_pitch()
            return
        if note == SNAP_PAD:
            self._toggle_snap()
            return
        if note == SLICE_PAD:
            transient = not self._slice_transient()
            song.set_data(SLICE_KEY, transient)
            self.show_message("LoopPad: SLICE %s" % (
                "on transients - chops start on the nearest hit" if transient else "into 8 equal chops"))
            self._slice_tries = 0
            self._build_chops()
            return
        if note in LENGTH_PADS:
            bars = LENGTH_PADS[note]
            self._loop_length = None if self._loop_length == bars else bars
            self.show_message("LoopPad: loop length %s" % (
                "free" if self._loop_length is None else "%d bars" % self._loop_length))
            return
        if note == SYNC_ALL_PAD:
            self._queue_mute_all()
            return
        if note == AUTO_QUANT_PAD:
            self._auto_quantize = not self._auto_quantize
            song.set_data(AUTO_QUANT_KEY, self._auto_quantize)
            self.show_message("LoopPad: auto-quantize %s" % (
                "ON - new loops snap to 1/16" if self._auto_quantize else "off"))
            return
        if note == BTN_TRANSPORT:
            if song.is_playing:
                song.stop_playing()
            else:
                self._align_to_bar()
                song.continue_playing()  # from the bar line, not the insert marker
            return
        if note == BTN_TAP:
            song.tap_tempo()
            return
        if note == BTN_METRO:
            song.metronome = not song.metronome
            return
        if note in (BTN_TEMPO_UP, BTN_TEMPO_DOWN):
            step = 1 if note == BTN_TEMPO_UP else -1
            song.tempo = max(20.0, min(999.0, round(song.tempo) + step))
            self.show_message("LoopPad: tempo %d BPM" % round(song.tempo))
            return
        # CLEAR ALL, CLEAR SAMPLE and BUILD SET fire on hold (_check_holds)

        loop = col - 1
        if loop >= NUM_LOOPS:
            return
        track = self._loop_tracks[loop]
        if track is None:
            self.show_message("LoopPad: no track named '%s' (hold the top-right round button to build the set)"
                              % LOOP_TRACK_NAMES[loop])
            return
        if row not in LOOP_ROWS:
            return
        slot = self._slot(loop)
        if slot is None:
            return
        song.view.selected_track = track
        state = self._loop_state(loop)

        if row == ROW_REC:
            if state == "empty":
                self._align_to_bar()
                track.arm = True
                self._armed_by_us[loop] = True
                if self._loop_length is None:
                    slot.fire()    # starts recording at the next bar (or now if stopped)
                else:
                    slot.fire(record_length=self._loop_length * self._beats_per_bar())
            elif state == "recording":
                slot.fire()        # close the loop at the next bar and play it
            elif state in ("playing", "stopped"):
                self.show_message("LoopPad: Loop %d is full. Hold CLEAR to erase it, "
                                  "or layer on another loop" % col)
        elif row == ROW_PLAY:
            if state == "stopped":
                self._align_to_bar()
                slot.fire()
                self._pending_mute[loop] = None
                track.mute = False
            elif state in ("playing", "recording", "queued"):
                self._queue_mute_toggle(loop)
        elif row == ROW_QUANTIZE:
            if state in ("playing", "stopped"):
                self._quantize_loop(loop, slot.clip)
        # ROW_CLEAR is handled on release / hold

    def _quantize_loop(self, loop, clip):
        try:
            if clip.is_audio_clip and not clip.warping:
                clip.warping = True  # audio quantize works by moving warp markers
            if clip.is_audio_clip and loop in self._drum_loops:
                try:  # Beats mode keeps moved drum hits crisp; others smear them
                    clip.warp_mode = Live.Clip.WarpMode.beats
                except Exception as e:
                    self.log_message("LoopPad: couldn't set Beats warp mode: %r" % (e,))
            before = self._warp_marker_count(clip)
            clip.quantize(QUANTIZE_GRID, QUANTIZE_AMOUNT)
            self.log_message("LoopPad: Loop %d quantized: warp markers %s -> %s, warp mode %s, "
                             "%.2f beats long" % (loop + 1, before, self._warp_marker_count(clip),
                                                  getattr(clip, "warp_mode", "?"), clip.length))
            self._quantized[loop] = True
            self.show_message("LoopPad: Loop %d quantized to 1/16" % (loop + 1))
        except Exception as e:
            self.log_message("LoopPad: quantize error: %r" % (e,))
            self.show_message("LoopPad: couldn't quantize Loop %d (%s)" % (loop + 1, e))

    def _warp_marker_count(self, clip):
        try:
            return len(clip.warp_markers)
        except Exception:
            return "?"

    # ------------------------------------------------- drum loops / sidechain ---

    def _meter(self, track):
        try:
            return track.output_meter_level if track is not None else 0.0
        except Exception:
            return 0.0

    def _set_drum_loop(self, loop, is_drums):
        if (loop in self._drum_loops) == is_drums:
            return
        if is_drums:
            self._drum_loops.add(loop)
        else:
            self._drum_loops.discard(loop)
        self.song().set_data(DRUM_LOOPS_KEY, sorted(self._drum_loops))

    def _set_dry_loop(self, loop, is_dry):
        if (loop in self._dry_loops) == is_dry:
            return
        if is_dry:
            self._dry_loops.add(loop)
        else:
            self._dry_loops.discard(loop)
        self.song().set_data(DRY_LOOPS_KEY, sorted(self._dry_loops))

    def _drum_loop_playing(self, exclude=None):
        """The first playing, unmuted drum loop's track, or None."""
        for loop in sorted(self._drum_loops):
            track = self._loop_tracks[loop]
            if (loop != exclude and track is not None and self._loop_state(loop) == "playing"
                    and not track.mute and self._pending_mute[loop] is not True):
                return track
        return None

    def _track_drum_loops(self):
        pads = self._find_track(PADS_TRACK_NAME) or self._find_track(LEGACY_DRUMS_TRACK_NAME)
        drums_sounding = self._meter(pads) > DRUM_METER_THRESHOLD
        if drums_sounding:
            self._pads_played_tick = self._tick
        for loop in range(NUM_LOOPS):
            state = self._loop_state(loop)
            prev = self._prev_state[loop]
            if state == "recording":
                if prev != "recording":
                    bpb = self._beats_per_bar()
                    self.log_message("LoopPad: Loop %d recording from beat %.3f of the bar" % (
                        loop + 1, self.song().current_song_time % bpb))
                    self._rec_drum_ticks[loop] = 0
                    self._rec_ducked_ticks[loop] = 0
                    self._set_drum_loop(loop, False)
                    self._set_dry_loop(loop, False)
                if drums_sounding:
                    self._rec_drum_ticks[loop] += 1
                if self._drum_loop_playing(exclude=loop) is not None:
                    self._rec_ducked_ticks[loop] += 1  # Keys ducking got printed
            elif prev == "recording" and state in ("playing", "stopped"):
                if self._auto_quantize:
                    self._auto_quant_due[loop] = self._tick + AUTO_QUANT_DELAY_TICKS
                is_drums = self._rec_drum_ticks[loop] >= DRUM_LOOP_MIN_TICKS
                self._set_drum_loop(loop, is_drums)
                self._set_dry_loop(loop, not is_drums and self._rec_drum_ticks[loop] == 0
                                   and self._rec_ducked_ticks[loop] == 0)
            elif state in ("empty", "none"):
                self._set_drum_loop(loop, False)
                self._set_dry_loop(loop, False)
            self._prev_state[loop] = state
            due = self._auto_quant_due[loop]
            if due is not None and self._tick >= due:
                self._auto_quant_due[loop] = None
                slot = self._slot(loop)
                if state in ("playing", "stopped") and slot is not None and slot.has_clip:
                    self._quantize_loop(loop, slot.clip)

    def _update_sidechain(self):
        pads = self._find_track(PADS_TRACK_NAME) or self._find_track(LEGACY_DRUMS_TRACK_NAME)
        playing_live = (self._pads_played_tick is not None
                        and self._tick - self._pads_played_tick < LIVE_DRUMS_TICKS)
        source = None if playing_live else self._drum_loop_playing()
        if source is None:
            source = pads
        if source is None:
            return
        log = lambda msg: self.log_message("LoopPad: " + msg)
        # Live drums duck from the kick alone; a drum loop is mixed audio, so it
        # ducks from all of it (the Duck's 120 Hz sidechain filter favours the kick)
        kick = self._kick_chain if source.name == PADS_TRACK_NAME else None
        routed = False
        for name in (KEYS_TRACK_NAME,):
            track = self._find_track(name)
            duck = mix.find_duck(track) if track is not None else None
            if duck is not None and mix.route_duck(duck, source, log, kick):
                routed = True
        label = "%s (%s)" % (source.name, kick) if kick else source.name
        if routed and self._duck_source != label:
            self._duck_source = label
            log("sidechain follows %s" % label)
        # Loop Ducks: on for every loop but the drum loops, keyed from the same source
        for loop in range(NUM_LOOPS):
            track = self._loop_tracks[loop]
            loop_duck = mix.find_duck(track) if track is not None else None
            if loop_duck is None:
                continue
            active = loop not in self._drum_loops and track.name != source.name
            try:
                mix.set_enabled(loop_duck, active)
                if active:
                    mix.route_duck(loop_duck, source, log, kick)
            except Exception as e:
                log("loop duck error: %r" % (e,))

    # ------------------------------------------------------- synced mutes ---

    def _queue_mute_toggle(self, loop):
        track = self._loop_tracks[loop]
        current = self._pending_mute[loop]
        target = not (track.mute if current is None else current)
        self._pending_mute[loop] = None if target == track.mute else target
        song = self.song()
        if not song.is_playing:
            self._apply_pending_mutes()
            return
        if self._pending_boundary is None and self._pending_mute[loop] is not None:
            bpb = self._beats_per_bar()
            t = song.current_song_time
            self._pending_boundary = (int(t / bpb) + 1) * bpb

    def _sync_all_loops(self):
        """Loops SYNC ALL acts on: the ones holding a loop (or recording one)."""
        return [loop for loop in range(NUM_LOOPS)
                if self._loop_state(loop) in ("recording", "playing", "stopped")]

    def _will_be_muted(self, loop):
        pending = self._pending_mute[loop]
        return self._loop_tracks[loop].mute if pending is None else pending

    def _queue_mute_all(self):
        """Mute every loop on the next bar, or unmute them all if all are muted."""
        loops = self._sync_all_loops()
        if not loops:
            return
        target = not all(self._will_be_muted(loop) for loop in loops)
        for loop in loops:
            if self._will_be_muted(loop) != target:
                self._queue_mute_toggle(loop)
        if all(self._pending_mute[loop] is None for loop in loops) and self.song().is_playing:
            self.show_message("LoopPad: SYNC ALL cancelled")
        else:
            self.show_message("LoopPad: %s all loops on the next bar" % ("mute" if target else "unmute"))

    def _apply_pending_mutes(self):
        for loop, target in enumerate(self._pending_mute):
            track = self._loop_tracks[loop]
            if target is not None and track is not None:
                track.mute = target
        self._pending_mute = [None] * NUM_LOOPS
        self._pending_boundary = None

    def _check_pending_mutes(self):
        # Called from update_display (~10x a second). Live refuses mute changes
        # made from a song-time listener, so the bar line is predicted here and
        # the mutes applied on the update closest to it.
        song = self.song()
        t = song.current_song_time
        if self._last_song_time is not None:
            if t > self._last_song_time:
                self._song_time_delta = t - self._last_song_time
            elif t < self._last_song_time and self._pending_boundary is not None:
                # Song position jumped back (transport restarted): re-aim at the next bar
                bpb = self._beats_per_bar()
                self._pending_boundary = (int(t / bpb) + 1) * bpb
        self._last_song_time = t
        if self._pending_boundary is None:
            return
        if all(target is None for target in self._pending_mute):
            self._pending_boundary = None
            return
        if not song.is_playing or t + self._song_time_delta * 0.5 >= self._pending_boundary:
            self._apply_pending_mutes()

    def _align_to_bar(self):
        """Before anything starts the stopped transport: put the playhead on a
        bar line (it's left mid-bar after a stop, and a loop recorded from
        there would be out of step with every later one), and make sure clips
        launch on the next bar."""
        song = self.song()
        if song.clip_trigger_quantization != Live.Song.Quantization.q_bar:
            song.clip_trigger_quantization = Live.Song.Quantization.q_bar
            self.log_message("LoopPad: launch quantization reset to 1 bar")
        if not song.is_playing:
            bpb = self._beats_per_bar()
            bar = int(song.current_song_time / bpb + 1e-6) * bpb
            if abs(song.current_song_time - bar) > 1e-6:
                song.current_song_time = bar

    def _beats_per_bar(self):
        song = self.song()
        return song.signature_numerator * 4.0 / song.signature_denominator

    def _on_release(self, note, hold_fired):
        row, col = divmod(note, 10)
        if row == ROW_CLEAR and col <= NUM_LOOPS and not hold_fired:
            loop = col - 1
            if self._loop_state(loop) in ("recording", "queued"):
                self._clear_loop(loop)
                self.show_message("LoopPad: Loop %d take aborted" % col)
            elif self._loop_state(loop) in ("playing", "stopped"):
                self.show_message("LoopPad: hold CLEAR to erase Loop %d" % col)

    def _check_holds(self):
        for note, pressed_at in list(self._pressed.items()):
            if note in self._hold_fired:
                continue
            held = self._tick - pressed_at
            row, col = divmod(note, 10)
            if row == ROW_CLEAR and col <= NUM_LOOPS and held >= CLEAR_HOLD_TICKS:
                self._hold_fired.add(note)
                self._clear_loop(col - 1)
                self.show_message("LoopPad: Loop %d cleared" % col)
            elif note == CLEAR_ALL_PAD and held >= CLEAR_ALL_HOLD_TICKS:
                self._hold_fired.add(note)
                for loop in range(NUM_LOOPS):
                    self._clear_loop(loop)
                self.show_message("LoopPad: all loops cleared")
            elif note == BTN_CLEAR_SAMPLE and held >= CLEAR_HOLD_TICKS:
                self._hold_fired.add(note)
                self._clear_sample()
                self.show_message("LoopPad: sample cleared")
            elif note == BTN_BUILD and held >= BUILD_HOLD_TICKS:
                self._hold_fired.add(note)
                self._build_set()

    # --------------------------------------------------------------- LEDs ---

    def _set_led(self, note, color, channel=STATIC, force=False):
        value = (channel, color)
        if not force and self._led_cache.get(note) == value:
            return
        self._led_cache[note] = value
        self._send_midi(((CC if note in CC_BUTTONS else NOTE_ON) | channel, note, color))

    def _set_flash(self, note, base, flash, force=False):
        value = ("flash", base, flash)
        if not force and self._led_cache.get(note) == value:
            return
        self._led_cache[note] = value
        status = CC if note in CC_BUTTONS else NOTE_ON
        self._send_midi((status | STATIC, note, base))
        self._send_midi((status | FLASH, note, flash))

    def _refresh_leds(self, force=False):
        try:
            self._do_refresh_leds(force)
        except Exception as e:
            self.log_message("LoopPad: LED error: %r" % (e,))

    def _do_refresh_leds(self, force):
        song = self.song()
        for loop in range(NUM_LOOPS):
            col = loop + 1
            track = self._loop_tracks[loop]
            state = self._loop_state(loop)
            if state == "none":
                for row in LOOP_ROWS:
                    self._set_led(pad(row, col), OFF, force=force)
                continue
            has_content = state in ("recording", "playing", "stopped")

            rec = pad(ROW_REC, col)
            if state == "recording":
                self._set_led(rec, RED, PULSE, force)
            elif state == "queued":
                self._set_led(rec, RED, FLASH, force)
            elif has_content:
                self._set_led(rec, ORANGE if loop in self._drum_loops else RED, force=force)
            else:
                self._set_led(rec, RED_DIM, force=force)

            play = pad(ROW_PLAY, col)
            pending = self._pending_mute[loop]
            if pending is not None:
                # Flash towards the queued state: unmute -> dim/bright, mute -> bright/dim
                if pending:
                    self._set_flash(play, GREEN, GREEN_DIM, force)
                else:
                    self._set_flash(play, GREEN_DIM, GREEN, force)
            elif state in ("playing", "recording"):
                self._set_led(play, GREEN_DIM if track.mute else GREEN, force=force)
            elif state == "stopped":
                self._set_led(play, GREEN_DIM, force=force)
            else:
                self._set_led(play, OFF, force=force)

            clear = pad(ROW_CLEAR, col)
            if clear in self._pressed:
                self._set_led(clear, WHITE, force=force)
            else:
                self._set_led(clear, YELLOW if has_content else OFF, force=force)

            if state not in ("playing", "stopped"):
                self._quantized[loop] = False  # new or deleted loop starts unquantized
            quant = pad(ROW_QUANTIZE, col)
            if state in ("playing", "stopped"):
                self._set_led(quant, MAGENTA if self._quantized[loop] else MAGENTA_DIM, force=force)
            else:
                self._set_led(quant, OFF, force=force)


        for note, bars in LENGTH_PADS.items():
            self._set_led(note, YELLOW if self._loop_length == bars else YELLOW_DIM, force=force)

        # Column 5: the all-loops pads
        loops = self._sync_all_loops()
        if any(self._pending_mute[loop] is not None for loop in loops):
            if all(self._will_be_muted(loop) for loop in loops):
                self._set_flash(SYNC_ALL_PAD, GREEN, GREEN_DIM, force)
            else:
                self._set_flash(SYNC_ALL_PAD, GREEN_DIM, GREEN, force)
        elif loops:
            audible = any(not self._loop_tracks[loop].mute for loop in loops)
            self._set_led(SYNC_ALL_PAD, GREEN if audible else GREEN_DIM, force=force)
        else:
            self._set_led(SYNC_ALL_PAD, OFF, force=force)
        self._set_led(CLEAR_ALL_PAD, RED if CLEAR_ALL_PAD in self._pressed else RED_DIM, force=force)
        self._set_led(AUTO_QUANT_PAD, MAGENTA if self._auto_quantize else MAGENTA_DIM, force=force)

        # Round buttons
        on_beat = song.is_playing and (song.current_song_time % 1.0) < 0.25
        self._set_led(BTN_TRANSPORT, GREEN if song.is_playing else WHITE_DIM, force=force)
        self._set_led(BTN_METRO, CYAN if song.metronome else CYAN_DIM, force=force)
        self._set_led(BTN_TAP, WHITE if on_beat else WHITE_DIM, force=force)
        self._set_led(BTN_TEMPO_UP, WHITE if BTN_TEMPO_UP in self._pressed else BLUE, force=force)
        self._set_led(BTN_TEMPO_DOWN, WHITE if BTN_TEMPO_DOWN in self._pressed else BLUE_DIM, force=force)
        self._set_led(BTN_BUILD, PURPLE if BTN_BUILD in self._pressed else PURPLE_DIM, force=force)

        current = shared.current_genre(song)
        for i, genre in enumerate(GENRES[:len(GENRE_PADS)]):
            color = genre["color"]
            self._set_led(GENRE_PADS[i], color if i == current else color + 2, force=force)

        # SOURCE: magenta = mic, white = session mix. PITCH: cyan, SNAP: green,
        # pulsing when on
        self._set_led(SOURCE_PAD, MAGENTA if self._sample_source() == "mic" else WHITE, force=force)
        pitch = self._pitch_on()
        self._set_led(PITCH_PAD, CYAN if pitch else CYAN_DIM, PULSE if pitch else STATIC, force)
        transient = self._slice_transient()
        self._set_led(SLICE_PAD, YELLOW if transient else YELLOW_DIM, force=force)
        snap = self._snap_on()
        self._set_led(SNAP_PAD, GREEN if snap else GREEN_DIM, PULSE if snap else STATIC, force)

        # Sampler
        state = self._sample_state()
        if state == "recording":
            self._set_led(BTN_SAMPLE_REC, RED, PULSE, force)
        elif state == "queued":
            self._set_led(BTN_SAMPLE_REC, RED, FLASH, force)
        else:
            self._set_led(BTN_SAMPLE_REC, RED if state == "full" else RED_DIM, force=force)
        if BTN_CLEAR_SAMPLE in self._pressed:
            self._set_led(BTN_CLEAR_SAMPLE, WHITE, force=force)
        else:
            self._set_led(BTN_CLEAR_SAMPLE, YELLOW if state == "full" else OFF, force=force)
        for i, note in enumerate(CHOP_PADS):
            self._set_led(note, BLUE if i < self._chop_count else OFF, force=force)

        assigned = set(pad(row, col) for row in LOOP_ROWS for col in range(1, NUM_LOOPS + 1))
        assigned.update(GENRE_PADS[:len(GENRES)])
        assigned.update(LENGTH_PADS)
        assigned.update((SYNC_ALL_PAD, CLEAR_ALL_PAD, AUTO_QUANT_PAD, SOURCE_PAD, PITCH_PAD,
                         SNAP_PAD, SLICE_PAD))
        assigned.update((BTN_TRANSPORT, BTN_METRO, BTN_TAP, BTN_TEMPO_UP, BTN_TEMPO_DOWN, BTN_BUILD,
                         BTN_SAMPLE_REC, BTN_CLEAR_SAMPLE))
        for note in CC_BUTTONS:
            if note not in assigned:
                self._set_led(note, OFF, force=force)
        for note in self._handled_notes:
            if note not in assigned:
                self._set_led(note, OFF, force=force)

        for i, note in enumerate(DRUM_PAD_NOTES):
            self._set_led(note, DRUM_ROW_COLORS[i // 4], force=force)

    # ------------------------------------------------------------ sampler ---

    def _sample_slot(self):
        track = self._find_track(GUITAR_TRACK_NAME)
        if track is None or len(track.clip_slots) <= LOOP_SLOT:
            return None
        return track.clip_slots[LOOP_SLOT]

    def _sample_clip(self):
        slot = self._sample_slot()
        return slot.clip if slot is not None and slot.has_clip and not slot.is_recording else None

    def _sample_state(self):
        """'none', 'empty', 'queued', 'recording' or 'full'."""
        slot = self._sample_slot()
        if slot is None:
            return "none"
        if slot.is_recording:
            return "recording"
        if slot.is_triggered and not slot.has_clip:
            return "queued"
        return "full" if slot.has_clip else "empty"

    def _sample_rec(self):
        state = self._sample_state()
        slot = self._sample_slot()
        if state == "none":
            self.show_message("LoopPad: no '%s' track to sample with" % GUITAR_TRACK_NAME)
        elif state == "full":
            self.show_message("LoopPad: hold CLEAR SAMPLE first to take a new sample")
        elif state in ("recording", "queued"):
            slot.fire()  # close the sample at the next bar
        else:
            self._start_sample_recording()

    def _start_sample_recording(self):
        track = self._find_track(GUITAR_TRACK_NAME)
        slot = self._sample_slot()
        self._guitar_input = (track.input_routing_type, track.input_routing_channel)
        # Monitoring off first, so the master never feeds back into itself
        track.current_monitoring_state = MONITOR_OFF
        self._align_to_bar()
        if self._sample_source() == "mic":
            self._route_input(track, "Ext. In", MIC_INPUT)
        else:
            self._route_input(track, "Resampling", None)
        track.arm = True
        if self._loop_length is None:
            slot.fire()
        else:
            slot.fire(record_length=self._loop_length * self._beats_per_bar())
        self.show_message("LoopPad: sampling the %s from the next bar" % (
            "mic" if self._sample_source() == "mic" else "session mix"))

    def _restore_guitar(self):
        track = self._find_track(GUITAR_TRACK_NAME)
        if track is None or self._guitar_input is None:
            return
        routing_type, channel = self._guitar_input
        self._guitar_input = None
        try:
            track.arm = False
            track.input_routing_type = routing_type
            track.input_routing_channel = channel
            track.current_monitoring_state = MONITOR_IN
        except Exception as e:
            self.log_message("LoopPad: couldn't restore Guitar input: %r" % (e,))

    def _track_sample(self):
        state = self._sample_state()
        prev = self._sample_prev_state
        self._sample_prev_state = state
        if self._guitar_input is not None and state not in ("queued", "recording"):
            self._restore_guitar()
        # A take just closed, or an audio file was dragged into the empty slot
        if prev in ("recording", "empty") and state == "full":
            slot = self._sample_slot()
            if slot is not None and slot.clip.is_audio_clip:
                slot.stop()  # the sample lives on as chops; its clip needn't play
                self._chop_due = self._tick + CHOP_DELAY_TICKS
        if self._rechop_due is not None and self._tick >= self._rechop_due:
            self._rechop_due = None
            self._build_chops()
        if self._chop_due is not None and self._tick >= self._chop_due:
            self._chop_due = None
            self._chop_sample()

    def _clear_sample(self):
        slot = self._sample_slot()
        if slot is not None:
            if slot.is_recording or slot.is_triggered:
                slot.stop()
            if slot.has_clip:
                slot.delete_clip()
        self.song().set_data(SAMPLE_PATH_KEY, None)
        rack = self._sampler_rack()
        if rack is not None:
            for note in CHOP_PADS:
                for chain in rack.drum_pads[note].chains:
                    while len(chain.devices):
                        chain.delete_device(0)
        self._chop_count = 0

    def _sampler_rack(self):
        track = self._find_track(SAMPLER_TRACK_NAME)
        if track is None:
            return None
        return shared.find_drum_rack(track.devices)

    def _pads_rack(self):
        track = self._find_track(PADS_TRACK_NAME) or self._find_track(LEGACY_DRUMS_TRACK_NAME)
        if track is None:
            return None
        return shared.find_drum_rack(track.devices)

    def _find_kick_chain(self):
        """The Pads kit's kick: a chain named like a kick, else whatever sits
        on the bottom-left pad (the kit's C1)."""
        rack = self._pads_rack()
        if rack is None:
            return None
        chains = [c for c in rack.chains if not c.name.startswith("Chop ")]
        for chain in chains:
            name = chain.name.lower()
            if "kick" in name or name.startswith("bd") or " bd" in name:
                return chain.name
        for note in (DRUM_PAD_NOTES[0], DRUM_RACK_FIRST_NOTE):
            pad = rack.drum_pads[note]
            if len(pad.chains):
                return pad.chains[0].name
        return None

    def _count_chops(self):
        rack = self._sampler_rack()
        if rack is None:
            return 0
        return sum(1 for note in CHOP_PADS
                   if any(len(chain.devices) for chain in rack.drum_pads[note].chains))

    def _chop_sample(self):
        """Store the new sample's file and build the chop pads from it."""
        clip = self._sample_clip()
        if clip is None:
            return
        self.song().set_data(SAMPLE_PATH_KEY, clip.file_path)
        self._slice_tries = 0
        self._build_chops()

    def _slice_transient(self):
        return bool(self.song().get_data(SLICE_KEY, False))

    def _transients(self, simpler, log):
        """Frame positions of the hits Simpler finds in its sample (switching it
        to transient slicing to ask), or None if it hasn't analysed it yet."""
        sample = simpler.sample
        try:
            simpler.playback_mode = Live.SimplerDevice.PlaybackMode.slicing
            sample.slicing_style = Live.Sample.SlicingStyle.transient
            sample.slicing_sensitivity = SLICE_SENSITIVITY
            slices = [int(x) for x in sample.slices]
        except Exception as e:
            log("transient slicing unavailable: %r" % (e,))
            return []
        finally:
            simpler.playback_mode = Live.SimplerDevice.PlaybackMode.one_shot
        return slices or None

    def _chop_ranges(self, length, onsets, min_frames):
        """NUM_CHOPS (start, end) frame ranges. Without onsets: equal eighths.
        With them: each start is the onset nearest its equal position (within
        half a chop), and it ends at the next onset at least min_frames on."""
        last = length - 1
        size = last / float(NUM_CHOPS)
        onsets = sorted(set(x for x in onsets if 0 <= x < last))
        starts = []
        for i in range(NUM_CHOPS):
            target = size * i
            floor = starts[-1] + 1 if starts else 0
            near = [x for x in onsets if x >= floor and abs(x - target) <= size / 2]
            point = min(near, key=lambda x: abs(x - target)) if near else int(target)
            starts.append(max(point, floor))
        ranges = []
        for i, start in enumerate(starts):
            end = starts[i + 1] if i + 1 < NUM_CHOPS else last
            if start in onsets:
                after = [x for x in onsets if x >= start + min_frames]
                end = min(after[0], end) if after else end
            ranges.append((start, max(end, start + 1)))
        return ranges

    def _build_chops(self):
        """8 Simplers on the Sampler Drum Rack, each playing one eighth of the
        sample (with SLICE on, one hit each, from a transient to the next)."""
        path = self.song().get_data(SAMPLE_PATH_KEY, None)
        rack = self._sampler_rack()
        if not path or rack is None:
            self._chop_count = self._count_chops()
            return
        log = lambda msg: self.log_message("LoopPad: " + msg)
        ranges = None  # chop (start, end) frames, worked out from the first Simpler
        try:
            for i, note in enumerate(CHOP_PADS):
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
                sample.warping = False  # markers in raw sample frames
                if ranges is None and self._slice_transient():
                    ranges = phrases.find_phrases(path, NUM_CHOPS)
                    if ranges is not None and ranges[-1][1] >= sample.length:
                        ranges = None  # the file doesn't match what Simpler loaded
                    if ranges is not None:
                        log("phrases: %s" % ", ".join(
                            "%.1f-%.1fs" % (a / sample.sample_rate, b / sample.sample_rate)
                            for a, b in ranges))
                if ranges is None:
                    onsets = []
                    if self._slice_transient():
                        onsets = self._transients(simpler, log)
                        if onsets is None:  # not analysed yet: try again shortly
                            self._slice_tries += 1
                            if self._slice_tries < SLICE_MAX_TRIES:
                                self._rechop_due = self._tick + SLICE_RETRY_TICKS
                                return
                            log("no transients found; chopping equally")
                            onsets = []
                        log("%d transients found in %d frames: %r" % (
                            len(onsets), sample.length, onsets[:12]))
                    # markers are frame indexes, 0..length-1
                    min_frames = int(SLICE_MIN_SECONDS * sample.sample_rate)
                    ranges = self._chop_ranges(sample.length, onsets, min_frames)
                start, end = ranges[i]
                # Move whichever marker won't cross the other first
                if start >= sample.end_marker:
                    sample.end_marker = end
                    sample.start_marker = start
                else:
                    sample.start_marker = start
                    sample.end_marker = end
                log("chop %d: pad %d, chain note %d, frames %d-%d of %d" % (
                    i + 1, note, chain.in_note, sample.start_marker, sample.end_marker,
                    sample.length))
                chain.choke_group = CHOP_CHOKE_GROUP
                mix.set_param(simpler, "Volume", CHOP_VOLUME_DB, log)
                try:
                    chain.name = "Chop %d" % (i + 1)
                except Exception:
                    pass
        except Exception as e:
            log("chop error: %r" % (e,))
            self.show_message("LoopPad: chop failed, see Log.txt (%s)" % (e,))
        self._chop_count = self._count_chops()
        log("chopped sample into %d pads" % self._chop_count)
        if self._chop_count:
            self.show_message("LoopPad: sample chopped - play it on the blue pads")

    # ---------------------------------------------------------- build set ---

    def _build_set(self):
        """Create Guitar / Pads / Sampler / Keys / Loop 1-4 tracks and a Loop Bus return."""
        song = self.song()
        self.show_message("LoopPad: building set...")
        ours = set(n.lower() for n in [GUITAR_TRACK_NAME, PADS_TRACK_NAME, KIT_TRACK_NAME,
                                       SUB_TRACK_NAME, SAMPLER_TRACK_NAME, KEYS_TRACK_NAME,
                                       LEGACY_DRUMS_TRACK_NAME] + LOOP_TRACK_NAMES)

        def is_empty(track):
            if len(track.devices):
                return False
            if any(slot.has_clip for slot in track.clip_slots):
                return False
            try:
                if len(track.arrangement_clips):
                    return False
            except Exception:
                pass
            return True

        def delete_empty_foreign(keep_one):
            for i in reversed(range(len(song.tracks))):
                t = song.tracks[i]
                if t.name.strip().lower() in ours or not is_empty(t):
                    continue
                if keep_one and len(song.tracks) <= 1:
                    break
                song.delete_track(i)

        try:
            delete_empty_foreign(keep_one=True)
            self._ensure_loop_bus()

            if self._find_track(GUITAR_TRACK_NAME) is None:
                song.create_audio_track(-1)
                song.tracks[-1].name = GUITAR_TRACK_NAME

            pads_track = self._find_track(PADS_TRACK_NAME)
            if pads_track is None:
                pads_track = self._find_track(LEGACY_DRUMS_TRACK_NAME)
                if pads_track is not None:
                    pads_track.name = PADS_TRACK_NAME
            if pads_track is None:
                song.create_midi_track(-1)
                pads_track = song.tracks[-1]
                pads_track.name = PADS_TRACK_NAME

            self._setup_sampler()
            # Sampler and Keys go straight after Pads
            previous = pads_track
            for name in (SAMPLER_TRACK_NAME, KEYS_TRACK_NAME):
                track = self._find_track(name)
                if track is None:
                    index = list(song.tracks).index(previous) + 1
                    song.create_midi_track(index)
                    track = song.tracks[index]
                    track.name = name
                previous = track

            for name in LOOP_TRACK_NAMES:
                if self._find_track(name) is None:
                    song.create_audio_track(-1)
                    song.tracks[-1].name = name

            delete_empty_foreign(keep_one=False)
        except Exception as e:
            self.log_message("LoopPad: build error: %r" % (e,))
            self.show_message("LoopPad: build error, see Log.txt (%s)" % (e,))
            return
        # A new track's input list is only populated a moment after it's created
        self.schedule_message(5, self._finish_build)

    def _finish_build(self):
        song = self.song()
        try:
            bus = self._ensure_loop_bus()
            guitar = self._find_track(GUITAR_TRACK_NAME)
            if guitar is not None:
                self._route_input(guitar, "Ext. In", "1")
                guitar.current_monitoring_state = MONITOR_IN
            for name, source in ((PADS_TRACK_NAME, "LPX MIDI"),
                                 (SAMPLER_TRACK_NAME, "LPX MIDI"),
                                 (KEYS_TRACK_NAME, "Launchkey MIDI")):
                track = self._find_track(name)
                if track is not None:
                    self._route_input(track, source, None)
                    track.current_monitoring_state = MONITOR_IN
            for name in LOOP_TRACK_NAMES:
                track = self._find_track(name)
                if track is None:
                    continue
                if bus is not None:
                    self._route_input(track, LOOP_BUS_NAME, "Post FX")
                # Monitoring Off: the track records its input but only plays back
                # its clip. You already hear yourself live on the other tracks.
                track.current_monitoring_state = MONITOR_OFF
            if bus is not None:
                self._set_sends(bus)
            song.clip_trigger_quantization = Live.Song.Quantization.q_bar
            self._load_genre(shared.current_genre(song))
            self._rescan()
            self.show_message("LoopPad: set built. Save it as your default set!")
            self.log_message("LoopPad: build complete")
        except Exception as e:
            self.log_message("LoopPad: finish build error: %r" % (e,))
            self.show_message("LoopPad: build error, see Log.txt (%s)" % (e,))

    def _ensure_loop_bus(self):
        song = self.song()
        for r in song.return_tracks:
            if LOOP_BUS_NAME.lower() in r.name.lower():
                return r
        try:
            if len(song.return_tracks) < 2:
                song.create_return_track()
                bus = song.return_tracks[-1]
            else:
                # Lite allows 2 returns: repurpose the last one that isn't Space
                spare = [r for r in song.return_tracks
                         if r.name.strip().lower() != mix.SPACE_NAME.lower()]
                if not spare:
                    self.log_message("LoopPad: no free return for the Loop Bus")
                    return None
                bus = spare[-1]
                while len(bus.devices):
                    bus.delete_device(0)
            bus.name = LOOP_BUS_NAME
            # Silent to the Main mix; loops tap it "Post FX", before the fader
            bus.mixer_device.volume.value = bus.mixer_device.volume.min
            return bus
        except Exception as e:
            self.log_message("LoopPad: couldn't create Loop Bus: %r" % (e,))
            return None

    def _set_sends(self, bus):
        song = self.song()
        bus_index = list(song.return_tracks).index(bus)
        for track in song.tracks:
            sends = track.mixer_device.sends
            if bus_index >= len(sends):
                continue
            send = sends[bus_index]
            name = track.name.strip().lower()
            if name in (GUITAR_TRACK_NAME.lower(), PADS_TRACK_NAME.lower(),
                        SAMPLER_TRACK_NAME.lower(), KEYS_TRACK_NAME.lower()):
                send.value = send.max
            elif name in [n.lower() for n in LOOP_TRACK_NAMES]:
                send.value = send.min

    def _route_input(self, track, type_contains, channel_name):
        try:
            for rt in track.available_input_routing_types:
                if type_contains.lower() in rt.display_name.lower():
                    track.input_routing_type = rt
                    break
            else:
                self.log_message("LoopPad: no input %r for %s; options: %r" % (
                    type_contains, track.name,
                    [r.display_name for r in track.available_input_routing_types]))
                return
            if channel_name:
                channels = list(track.available_input_routing_channels)
                for ch in channels:
                    if ch.display_name == channel_name:
                        track.input_routing_channel = ch
                        break
                else:
                    self.log_message("LoopPad: no input channel %r for %s; options: %r" % (
                        channel_name, track.name, [c.display_name for c in channels]))
                    self.show_message("LoopPad: no input %s - is the aggregate device selected?" % channel_name)
        except Exception as e:
            self.log_message("LoopPad: routing error on %s: %r" % (track.name, e))

    # -------------------------------------------------------------- genres ---

    # ------------------------------------------------------- source / pitch ---

    def _sample_source(self):
        return "mic" if self.song().get_data(SOURCE_KEY, "mix") == "mic" else "mix"

    def _pitch_on(self):
        return bool(self.song().get_data(PITCH_KEY, False))

    def _toggle_pitch(self):
        on = not self._pitch_on()
        self.song().set_data(PITCH_KEY, on)
        if not on:
            shared.set_chop_transpose(self.song(), 0)
        self.show_message("LoopPad: PITCH %s" % (
            "on - hold a Launchkey key to set the chops' pitch (C3 = original)" if on else "off"))

    def _snap_on(self):
        return bool(self.song().get_data(SNAP_KEY, False))

    def _snap_device(self):
        track = self._find_track(SAMPLER_TRACK_NAME)
        if track is None:
            return None
        return next((d for d in track.devices if d.name == SNAP_DEVICE_NAME), None)

    def _toggle_snap(self):
        track = self._find_track(SAMPLER_TRACK_NAME)
        if track is None:
            return
        on = not self._snap_on()
        self.song().set_data(SNAP_KEY, on)
        self._ensure_snap(track, lambda msg: self.log_message("LoopPad: " + msg))
        song = self.song()
        key = "%s %s" % (NOTE_NAMES[song.root_note % 12], song.scale_name)
        self.show_message("LoopPad: SNAP %s" % (
            "on - chops snap to %s (set the key in Live's Scale chooser)" % key if on else "off"))

    def _ensure_snap(self, track, log):
        """Auto Shift named Snap at the end of the Sampler track while SNAP is
        on, and none while it's off: a switched-off device still delays the
        track by its latency, which makes the chop pads feel late."""
        device = self._snap_device()
        if not self._snap_on():
            if device is not None:
                track.delete_device(list(track.devices).index(device))
            return
        if device is None:
            device = mix.insert(track, "Auto Shift", len(track.devices), log)
            if device is None:
                return
            device.name = SNAP_DEVICE_NAME
            mix.set_params(device, SNAP_PARAMS, log)
        mix.set_enabled(device, True)

    def _remove_old_pitch(self, track, log):
        """Delete the Auto Shift the old PITCH put on Sampler, and switch the
        Keys instrument back on (that PITCH switched it off)."""
        for i in reversed(range(len(track.devices))):
            if track.devices[i].name == OLD_PITCH_DEVICE_NAME:
                track.delete_device(i)
                log("removed the old Auto Shift PITCH from %s" % track.name)
                keys = self._find_track(KEYS_TRACK_NAME)
                for device in (keys.devices if keys is not None else []):
                    if device.type == Live.Device.DeviceType.instrument:
                        mix.set_enabled(device, True)

    def _clear_guitar_effects(self, guitar):
        """Remove everything on Guitar but the Tuner."""
        for i in reversed(range(len(guitar.devices))):
            if guitar.devices[i].class_name != "Tuner":
                guitar.delete_device(i)

    def _ensure_tuner(self, guitar, log):
        # A Tuner always sits first on Guitar (it doesn't change the sound)
        if not any(d.class_name == "Tuner" for d in guitar.devices):
            mix.insert(guitar, "Tuner", 0, log)

    def _load_guitar_chain(self, genre, sounds, log):
        guitar = self._find_track(GUITAR_TRACK_NAME)
        if guitar is None:
            return
        song = self.song()
        try:
            # Clear the last genre's effects, keeping the Tuner
            self._clear_guitar_effects(guitar)
            if sounds["guitar"] is not None:
                song.view.selected_track = guitar
                Live.Application.get_application().browser.load_item(sounds["guitar"])
            else:
                for device_name, params in genre["guitar"]:
                    # Some effects aren't in Lite; skip those, keep the rest
                    device = mix.insert(guitar, device_name, len(guitar.devices), log)
                    if device is None:
                        continue
                    if isinstance(params, dict):  # raw parameter values
                        for param in device.parameters:
                            if param.name in params:
                                param.value = params[param.name]
                    else:  # [(name, displayed value)], as in mix.py
                        mix.set_params(device, params, log)
        except Exception as e:
            log("guitar effects error: %r" % (e,))
        self._ensure_tuner(guitar, log)

    def _setup_sampler(self):
        """Make sure the Sampler track exists (Live Lite allows only 8 tracks, so
        the old Sub, or Kit, track becomes it) with a Drum Rack for the chops."""
        log = lambda msg: self.log_message("LoopPad: " + msg)
        track = self._find_track(SAMPLER_TRACK_NAME)
        if track is None:
            old = self._find_track(SUB_TRACK_NAME) or self._find_track(KIT_TRACK_NAME)
            if old is None:
                return
            try:
                for i in reversed(range(len(old.devices))):
                    old.delete_device(i)
                for slot in old.clip_slots:
                    if slot.has_clip:
                        slot.delete_clip()
                old.name = SAMPLER_TRACK_NAME
                self._route_input(old, "LPX MIDI", None)
                old.current_monitoring_state = MONITOR_IN
                log("%s track turned into %s" % (SUB_TRACK_NAME, SAMPLER_TRACK_NAME))
            except Exception as e:
                log("couldn't make the Sampler track: %r" % (e,))
                return
            track = old
        try:
            if shared.find_drum_rack(track.devices) is None:
                track.insert_device("Drum Rack", 0)
            self._remove_old_pitch(track, log)
            self._ensure_snap(track, log)
        except Exception as e:
            log("sampler setup error: %r" % (e,))

    def _retry_missing_presets(self, index, log):
        """Live's browser lags while it re-indexes the User Library, so a saved
        preset can be missed: if any were, load the genre again shortly."""
        missing = shared.missing_presets(index)
        if not missing:
            self._genre_retries = 0
            return
        if self._genre_retries >= GENRE_RETRY_MAX:
            log("User Library presets still not in Live's browser: %s" % ", ".join(missing))
            self._genre_retries = 0
            return
        self._genre_retries += 1
        log("User Library still indexing (missing %s); reloading the genre shortly"
            % ", ".join(missing))
        self.show_message("LoopPad: waiting for Live to find your presets...")

        def retry():
            if shared.current_genre(self.song()) == index:
                self._load_genre(index)
        self.schedule_message(GENRE_RETRY_TICKS, retry)

    def _load_genre(self, index):
        song = self.song()
        genre = GENRES[index]
        song.set_data(shared.GENRE_KEY, index)
        log = lambda msg: self.log_message("LoopPad: " + msg)
        # Re-scan the User Library so newly saved "<Genre> - ..." presets are used
        shared.refresh_user_presets(song)
        sounds = shared.resolve_genre(index)
        self._setup_sampler()

        kit = sounds["kit"]
        if kit is None:
            log("kit not found: %s" % genre["kit"])
        for name in (PADS_TRACK_NAME,):
            track = self._find_track(name)
            if track is not None and kit is not None:
                try:
                    shared.replace_instrument(song, track, kit)
                except Exception as e:
                    log("kit load error on %s: %r" % (name, e))

        try:
            first = next((i for i, k in enumerate(sounds["keys"]) if k is not None), None)
            if first is None:
                log("no keys sounds found for %s" % genre["name"])
            else:
                shared.load_keys_sound(song, first, log)
        except Exception as e:
            log("keys load error: %r" % (e,))


        guitar = self._find_track(GUITAR_TRACK_NAME)
        self._load_guitar_chain(genre, sounds, log)

        try:
            tracks = {"guitar": guitar, "keys": self._find_track(KEYS_TRACK_NAME),
                      "pads": self._find_track(PADS_TRACK_NAME)
                              or self._find_track(LEGACY_DRUMS_TRACK_NAME),
                      "sampler": self._find_track(SAMPLER_TRACK_NAME),
                      "loops": [self._find_track(n) for n in LOOP_TRACK_NAMES]}
            mix.apply_genre(song, tracks, self._ensure_loop_bus(), genre, log)
            self._duck_source = None  # re-route the sidechain on the next update
        except Exception as e:
            log("mix setup error: %r" % (e,))

        # The new Pads kit needs remapping to the Launchpad's pads
        self.schedule_message(2, self._rescan)
        if self._count_chops() < NUM_CHOPS:
            self.schedule_message(4, self._build_chops)  # e.g. a newly made Sampler track
        self.show_message("LoopPad: genre %s" % genre["name"])
        self._retry_missing_presets(index, log)
        log("loaded genre %s (kit %s, keys %s)" % (
            genre["name"], kit.name if kit else "-",
            ", ".join(k[1].name for k in sounds["keys"] if k)))
