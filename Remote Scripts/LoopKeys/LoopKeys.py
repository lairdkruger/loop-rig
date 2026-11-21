"""
LoopKeys - Launchkey MK2 companion to LoopPad, for Ableton Live 12 Lite.

Runs on the "Launchkey InControl" port. The keys themselves arrive on the
separate "Launchkey MIDI" port and play the Keys track directly (except
while LoopPad's PITCH is on: then LoopPitch takes them to steer the chops).

  Top pad row, pads 1-4:  pick the current genre's keys sound (Bass, Pad, Lead, ...)
  Faders 1-8:             volumes of Guitar, Pads, Sampler, Keys, Loop 1-4
  Master fader:           Main volume

Unrecognised controls are logged once each to Live's Log.txt.
"""

import Live
from _Framework.ControlSurface import ControlSurface
from LoopPad import shared

# Everything on the InControl port uses MIDI channel 16 (zero-based 15)
CHANNEL = 15
NOTE_ON = 0x90 | CHANNEL
CC = 0xB0 | CHANNEL
INCONTROL_ON = (NOTE_ON, 0x0C, 0x7F)
INCONTROL_OFF = (NOTE_ON, 0x0C, 0x00)
# The drum pads have their own InControl switch (as used by Ableton's Launchkey_MK2 script)
PADS_INCONTROL_ON = (NOTE_ON, 0x0F, 0x7F)
PADS_INCONTROL_OFF = (NOTE_ON, 0x0F, 0x00)

TOP_PADS = list(range(96, 104))
BOTTOM_PADS = list(range(112, 120))
ROUND_PADS = [104, 120]
FADER_CCS = list(range(41, 49))
MASTER_FADER_CC = 7

FADER_TRACKS = [shared.GUITAR_TRACK_NAME, shared.PADS_TRACK_NAME, shared.SAMPLER_TRACK_NAME,
                shared.KEYS_TRACK_NAME] + shared.LOOP_TRACK_NAMES

OFF = 0


class LoopKeys(ControlSurface):

    def __init__(self, c_instance):
        ControlSurface.__init__(self, c_instance)
        self._tick = 0
        self._led_cache = {}
        self._seen_unknown = set()
        self._track_signature = None
        self._load_count = None
        self._enable_incontrol()
        self.log_message("LoopKeys: init")
        # Send again once the port has settled; the first message can arrive too early
        self.schedule_message(10, self._enable_incontrol)

    def disconnect(self):
        for note in TOP_PADS + BOTTOM_PADS + ROUND_PADS:
            self._send_midi((NOTE_ON, note, OFF))
        self._send_midi(PADS_INCONTROL_OFF)
        self._send_midi(INCONTROL_OFF)
        ControlSurface.disconnect(self)

    def refresh_state(self):
        ControlSurface.refresh_state(self)
        self._enable_incontrol()

    def _enable_incontrol(self):
        self._send_midi(INCONTROL_ON)
        self._send_midi(PADS_INCONTROL_ON)
        self._refresh_leds(force=True)

    def build_midi_map(self, midi_map_handle):
        handle = self._c_instance.handle()
        song = self.song()
        for i, name in enumerate(FADER_TRACKS):
            track = shared.find_track(song, name)
            if track is not None:
                Live.MidiMap.map_midi_cc(midi_map_handle, track.mixer_device.volume, CHANNEL,
                                         FADER_CCS[i], Live.MidiMap.MapMode.absolute, True)
        Live.MidiMap.map_midi_cc(midi_map_handle, song.master_track.mixer_device.volume, CHANNEL,
                                 MASTER_FADER_CC, Live.MidiMap.MapMode.absolute, True)
        # Grab every other note and CC on this port so we can use or log them
        for note in range(128):
            Live.MidiMap.forward_midi_note(handle, midi_map_handle, CHANNEL, note)
        for cc in range(128):
            if cc not in FADER_CCS and cc != MASTER_FADER_CC:
                Live.MidiMap.forward_midi_cc(handle, midi_map_handle, CHANNEL, cc)

    def receive_midi(self, midi_bytes):
        if len(midi_bytes) != 3:
            return
        status, number, value = midi_bytes
        kind = status & 0xF0
        try:
            if kind == 0x90 and value > 0 and number in TOP_PADS:
                self._select_sound(TOP_PADS.index(number))
            elif kind == 0x90 and value > 0:
                self._log_unknown(midi_bytes)
            elif kind == 0xB0 and value > 0:
                self._log_unknown(midi_bytes)
        except Exception as e:
            self.log_message("LoopKeys: error: %r" % (e,))

    def _log_unknown(self, midi_bytes):
        key = (midi_bytes[0], midi_bytes[1])
        if key not in self._seen_unknown:
            self._seen_unknown.add(key)
            self.log_message("LoopKeys: unassigned control %r" % (midi_bytes,))

    def update_display(self):
        ControlSurface.update_display(self)
        self._tick += 1
        if self._tick % 5 == 0:
            # Re-map faders when tracks are added or renamed
            signature = tuple(t.name for t in self.song().tracks)
            if signature != self._track_signature:
                self._track_signature = signature
                self.request_rebuild_midi_map()
            # LoopPad loaded a genre: pick up any new User Library presets too
            count = self.song().get_data(shared.LOAD_COUNT_KEY, 0)
            if count != self._load_count:
                if self._load_count is not None:
                    shared.refresh_user_presets()
                self._load_count = count
            self._refresh_leds()

    # ---------------------------------------------------------------- sounds ---

    def _select_sound(self, index):
        # Re-scan the User Library so a just-saved "1-keys-1" style preset is used
        shared.refresh_user_presets()
        keys = shared.resolve_genre(shared.current_genre(self.song()))["keys"]
        if index >= len(keys) or keys[index] is None:
            return
        log = lambda msg: self.log_message("LoopKeys: " + msg)
        if shared.load_keys_sound(self.song(), index, log):
            self.show_message("Keys: %s" % keys[index][0])
        self._refresh_leds()

    # ------------------------------------------------------------------ LEDs ---

    def _set_led(self, note, color, force=False):
        if not force and self._led_cache.get(note) == color:
            return
        self._led_cache[note] = color
        self._send_midi((NOTE_ON, note, color))

    def _refresh_leds(self, force=False):
        try:
            song = self.song()
            keys = shared.resolve_genre(shared.current_genre(song))["keys"]
            selected = shared.current_sound(song)
            for i, note in enumerate(TOP_PADS):
                if i < len(keys) and keys[i] is not None:
                    color = shared.KEY_COLORS[i]
                    self._set_led(note, color if i == selected else color + 2, force)
                else:
                    self._set_led(note, OFF, force)
            for note in BOTTOM_PADS + ROUND_PADS:
                self._set_led(note, OFF, force)
        except Exception as e:
            self.log_message("LoopKeys: LED error: %r" % (e,))
